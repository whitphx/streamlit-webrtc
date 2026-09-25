use libwebrtc::{
    audio_frame::AudioFrame,
    audio_source::{AudioSourceOptions, native::NativeAudioSource},
    audio_stream::native::NativeAudioStream,
    ice_candidate::IceCandidate,
    media_stream_track::MediaStreamTrack,
    peer_connection::{AnswerOptions, IceGatheringState, PeerConnection, PeerConnectionState},
    peer_connection_factory::{
        ContinualGatheringPolicy, IceServer, PeerConnectionFactory, RtcConfiguration,
        native::PeerConnectionFactoryExt,
    },
    session_description::{SdpType, SessionDescription},
    stats::RtcStats,
};
use parking_lot::Mutex;
use pyo3::{
    exceptions::{PyRuntimeError, PyValueError},
    prelude::*,
    types::PyBytes,
};
use pyo3_async_runtimes::tokio::future_into_py;
use std::{
    collections::HashMap,
    sync::{
        Arc,
        atomic::{AtomicU64, Ordering},
    },
    time::Duration,
};
use tokio::sync::{Mutex as AsyncMutex, mpsc, watch};
use tokio_stream::StreamExt;
use tokio_util::sync::CancellationToken;

fn error(e: impl std::fmt::Display) -> PyErr {
    PyRuntimeError::new_err(e.to_string())
}
struct Receiver {
    tracks: mpsc::Receiver<NativeAudioStream>,
    stream: Option<NativeAudioStream>,
}
struct Inner {
    pc: Mutex<Option<PeerConnection>>,
    factory: Mutex<Option<PeerConnectionFactory>>,
    source: Mutex<Option<NativeAudioSource>>,
    receiver: AsyncMutex<Receiver>,
    writer: AsyncMutex<()>,
    generation: AtomicU64,
    gathering: watch::Receiver<IceGatheringState>,
    closed: CancellationToken,
}
impl Inner {
    fn peer(&self) -> PyResult<PeerConnection> {
        self.pc
            .lock()
            .clone()
            .ok_or_else(|| error("peer is closed"))
    }
    fn source(&self) -> PyResult<NativeAudioSource> {
        self.source
            .lock()
            .clone()
            .ok_or_else(|| error("peer is closed"))
    }
    fn stop(&self) {
        self.closed.cancel();
        if let Some(pc) = self.pc.lock().take() {
            pc.on_track(None);
            pc.on_ice_gathering_state_change(None);
            pc.on_connection_state_change(None);
            pc.close();
        }
        if let Some(source) = self.source.lock().take() {
            source.clear_buffer();
        }
        self.factory.lock().take();
    }
}
impl Drop for Inner {
    fn drop(&mut self) {
        self.stop();
    }
}
#[pyclass]
struct AudioPeer {
    inner: Arc<Inner>,
}
#[pymethods]
impl AudioPeer {
    #[new]
    #[pyo3(signature = (ice_servers=Vec::new()))]
    fn new(py: Python<'_>, ice_servers: Vec<(Vec<String>, String, String)>) -> PyResult<Self> {
        py.detach(move || {
            let factory = PeerConnectionFactory::default();
            let mut config = RtcConfiguration::default();
            config.continual_gathering_policy = ContinualGatheringPolicy::GatherOnce;
            config.ice_servers = ice_servers
                .into_iter()
                .map(|(urls, username, password)| IceServer {
                    urls,
                    username,
                    password,
                })
                .collect();
            let pc = factory.create_peer_connection(config).map_err(error)?;
            // Headless audio follows LiveKit's native source and stream APIs:
            // https://github.com/livekit/rust-sdks/blob/c9445106eec8fe437d8e8d0ff4ba6158698c6bb4/libwebrtc/src/audio_stream.rs
            // Upstream permits twice queue_size_ms of buffered audio.
            // https://github.com/livekit/rust-sdks/blob/c9445106eec8fe437d8e8d0ff4ba6158698c6bb4/webrtc-sys/src/audio_track.cpp#L203-L207
            let source = NativeAudioSource::new(AudioSourceOptions::default(), 48000, 1, 50);
            pc.add_track(
                factory.create_audio_track("output", source.clone()).into(),
                &["native-audio"],
            )
            .map_err(error)?;
            let (tracks_tx, tracks) = mpsc::channel(1);
            pc.on_track(Some(Box::new(move |event| {
                if let MediaStreamTrack::Audio(track) = event.track {
                    let _ = tracks_tx.try_send(NativeAudioStream::new(track, 48000, 1));
                }
            })));
            let (gather_tx, gathering) = watch::channel(IceGatheringState::New);
            pc.on_ice_gathering_state_change(Some(Box::new(move |state| {
                gather_tx.send_replace(state);
            })));
            let closed = CancellationToken::new();
            let connection_closed = closed.clone();
            pc.on_connection_state_change(Some(Box::new(move |state| {
                if matches!(
                    state,
                    PeerConnectionState::Disconnected
                        | PeerConnectionState::Failed
                        | PeerConnectionState::Closed
                ) {
                    // NetEq keeps producing concealment after transport closure.
                    // Signal async readers instead of closing inside the locked handler.
                    // https://github.com/livekit/rust-sdks/blob/c9445106eec8fe437d8e8d0ff4ba6158698c6bb4/libwebrtc/src/native/peer_connection.rs#L545-L549
                    connection_closed.cancel();
                }
            })));
            Ok(Self {
                inner: Arc::new(Inner {
                    pc: Mutex::new(Some(pc)),
                    factory: Mutex::new(Some(factory)),
                    source: Mutex::new(Some(source)),
                    receiver: AsyncMutex::new(Receiver {
                        tracks,
                        stream: None,
                    }),
                    writer: AsyncMutex::new(()),
                    generation: AtomicU64::new(0),
                    gathering,
                    closed,
                }),
            })
        })
    }
    fn answer<'py>(&self, py: Python<'py>, sdp: String) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        future_into_py(py, async move {
            let pc = inner.peer()?;
            let negotiate = async {
                let offer = SessionDescription::parse(&sdp, SdpType::Offer).map_err(error)?;
                let media: Vec<_> = sdp.lines().filter(|line| line.starts_with("m=")).collect();
                if media.len() != 1 || !media[0].starts_with("m=audio ") {
                    return Err(PyValueError::new_err(
                        "the prototype requires one audio media section",
                    ));
                }
                pc.set_remote_description(offer).await.map_err(error)?;
                let answer = pc
                    .create_answer(AnswerOptions::default())
                    .await
                    .map_err(error)?;
                pc.set_local_description(answer).await.map_err(error)?;
                let mut gathering = inner.gathering.clone();
                gathering
                    .wait_for(|s| *s == IceGatheringState::Complete)
                    .await
                    .map_err(error)?;
                pc.current_local_description()
                    .map(|s| s.to_string())
                    .ok_or_else(|| error("missing answer"))
            };
            tokio::select! {
                _ = inner.closed.cancelled() => Err(error("peer is closed")),
                result = tokio::time::timeout(Duration::from_secs(20), negotiate) => result.map_err(error)?,
            }
        })
    }
    fn add_ice_candidate<'py>(
        &self,
        py: Python<'py>,
        mid: String,
        index: i32,
        candidate: String,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        future_into_py(py, async move {
            let pc = inner.peer()?;
            let candidate = IceCandidate::parse(&mid, index, &candidate).map_err(error)?;
            tokio::select! {
                _ = inner.closed.cancelled() => Err(error("peer is closed")),
                result = pc.add_ice_candidate(candidate) => result.map_err(error),
            }
        })
    }
    fn recv<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        future_into_py(py, async move {
            let receive = async {
                let mut receiver = inner.receiver.lock().await;
                if receiver.stream.is_none() {
                    receiver.stream = Some(
                        receiver
                            .tracks
                            .recv()
                            .await
                            .ok_or_else(|| error("audio track ended"))?,
                    );
                }
                let frame = receiver
                    .stream
                    .as_mut()
                    .unwrap()
                    .next()
                    .await
                    .ok_or_else(|| error("audio track ended"))?;
                let bytes: Vec<u8> = frame
                    .data
                    .iter()
                    .flat_map(|sample| sample.to_le_bytes())
                    .collect();
                Ok(Python::attach(|py| PyBytes::new(py, &bytes).unbind()))
            };
            tokio::select! {
                _ = inner.closed.cancelled() => Err(error("peer is closed")),
                result = receive => if inner.closed.is_cancelled() { Err(error("peer is closed")) } else { result },
            }
        })
    }
    fn send<'py>(&self, py: Python<'py>, pcm: &[u8]) -> PyResult<Bound<'py, PyAny>> {
        if pcm.is_empty() || !pcm.len().is_multiple_of(2) || pcm.len() > 4800 {
            return Err(PyValueError::new_err(
                "send requires 1 to 2400 s16 mono samples",
            ));
        }
        let data: Vec<i16> = pcm
            .chunks_exact(2)
            .map(|b| i16::from_le_bytes([b[0], b[1]]))
            .collect();
        let inner = self.inner.clone();
        let expected = inner.generation.load(Ordering::Acquire);
        // Python task cancellation must not release the writer while the native
        // completion callback is still outstanding. The capture owns this task.
        let task = pyo3_async_runtimes::tokio::get_runtime().spawn(async move {
            let _writer = inner.writer.lock().await;
            if inner.closed.is_cancelled() {
                return Err(error("peer is closed"));
            }
            if inner.generation.load(Ordering::Acquire) != expected {
                return Err(error("output interrupted"));
            }
            let source = inner.source()?;
            let frame = AudioFrame {
                samples_per_channel: data.len() as u32,
                data: data.into(),
                sample_rate: 48000,
                num_channels: 1,
            };
            source.capture_frame(&frame).await.map_err(error)?;
            if inner.closed.is_cancelled() {
                return Err(error("peer is closed"));
            }
            if inner.generation.load(Ordering::Acquire) != expected {
                return Err(error("output interrupted"));
            }
            Ok(())
        });
        future_into_py(py, async move { task.await.map_err(error)? })
    }
    fn clear_output<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        // clear_buffer leaves the upstream completion callback pending until the next
        // audio tick. Keep the writer locked until capture_frame acknowledges it.
        // https://github.com/livekit/rust-sdks/blob/c9445106eec8fe437d8e8d0ff4ba6158698c6bb4/webrtc-sys/src/audio_track.cpp#L180-L184
        inner.generation.fetch_add(1, Ordering::AcqRel);
        inner.source()?.clear_buffer();
        future_into_py(py, async move {
            let _writer = inner.writer.lock().await;
            inner.source()?.clear_buffer();
            Ok(())
        })
    }
    fn stats<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        future_into_py(py, async move {
            let pc = inner.peer()?;
            let mut values = HashMap::<String, f64>::new();
            let stats = tokio::select! {
                _ = inner.closed.cancelled() => return Err(error("peer is closed")),
                stats = pc.get_stats() => stats.map_err(error)?,
            };
            for stat in stats {
                if let RtcStats::InboundRtp(s) = stat {
                    if s.stream.kind != "audio" {
                        continue;
                    }
                    for (name, value) in [
                        ("packets_received", s.received.packets_received as f64),
                        ("packets_lost", s.received.packets_lost as f64),
                        ("jitter_seconds", s.received.jitter),
                        ("concealed_samples", s.inbound.concealed_samples as f64),
                        ("concealment_events", s.inbound.concealment_events as f64),
                        ("jitter_buffer_delay_seconds", s.inbound.jitter_buffer_delay),
                        (
                            "jitter_buffer_emitted_count",
                            s.inbound.jitter_buffer_emitted_count as f64,
                        ),
                        ("samples_received", s.inbound.total_samples_received as f64),
                    ] {
                        values.insert(name.into(), value);
                    }
                }
            }
            Ok(values)
        })
    }
    fn close<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        inner.closed.cancel();
        if let Some(source) = inner.source.lock().as_ref() {
            source.clear_buffer();
        }
        future_into_py(py, async move {
            let _writer = inner.writer.lock().await;
            inner.stop();
            let mut receiver = inner.receiver.lock().await;
            if let Some(mut stream) = receiver.stream.take() {
                stream.close();
            }
            receiver.tracks.close();
            while receiver.tracks.try_recv().is_ok() {}
            Ok(())
        })
    }
}
#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<AudioPeer>()?;
    Ok(())
}
