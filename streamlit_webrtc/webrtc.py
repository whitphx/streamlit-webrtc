import asyncio
import enum
import itertools
import logging
import queue
import threading
from typing import (
    TYPE_CHECKING,
    Callable,
    Dict,
    Generic,
    Literal,
    Optional,
    Set,
    Union,
    cast,
)

from aiortc import (
    RTCConfiguration,
    RTCIceCandidate,
    RTCPeerConnection,
    RTCSessionDescription,
)
from aiortc.contrib.media import MediaPlayer, MediaRecorder, MediaRelay
from aiortc.mediastreams import MediaStreamTrack
from aiortc.sdp import candidate_from_sdp

from streamlit_webrtc.shutdown import SessionShutdownObserver

from .eventloop import get_global_event_loop, loop_context
from .models import (
    AudioFrameCallback,
    AudioProcessorBase,
    AudioProcessorFactory,
    AudioProcessorT,
    CallbackAttachableProcessor,
    MediaEndedCallback,
    MediaPlayerFactory,
    MediaRecorderFactory,
    ProcessorBase,
    QueuedAudioFramesCallback,
    QueuedVideoFramesCallback,
    VideoFrameCallback,
    VideoProcessorBase,
    VideoProcessorFactory,
    VideoProcessorT,
    VideoTransformerBase,
)
from .process import (
    AsyncAudioProcessTrack,
    AsyncVideoProcessTrack,
    AudioProcessTrack,
    VideoProcessTrack,
)
from .receive import AudioReceiver, VideoReceiver
from .relay import get_global_relay
from .sink import MediaSink

if TYPE_CHECKING:
    import concurrent.futures

__all__ = [
    "AudioProcessorBase",
    "AudioProcessorFactory",
    "VideoTransformerBase",
    "VideoProcessorBase",
    "MediaPlayerFactory",
    "MediaRecorderFactory",
    "VideoProcessorFactory",
    "WebRtcMode",
    "SignallingTimeoutError",
    "WebRtcWorker",
]


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class WebRtcMode(enum.Enum):
    RECVONLY = enum.auto()
    SENDONLY = enum.auto()
    SENDRECV = enum.auto()


class SignallingTimeoutError(Exception):
    pass


TrackType = Literal["input:video", "input:audio", "output:video", "output:audio"]


def _wrap_with_processor(
    track: MediaStreamTrack,
    processor: Optional[ProcessorBase],
    *,
    async_processing: bool,
    relay: MediaRelay,
) -> MediaStreamTrack:
    """Wrap ``track`` in a kind-matched process track when a processor is given,
    otherwise return ``track`` unchanged."""
    if processor is None:
        return track
    # Wrap via the relay so the unwrapped input can still feed a recorder
    # (or another consumer) via its own `relay.subscribe()` call.
    relayed = relay.subscribe(track)
    if track.kind == "audio":
        audio_cls = AsyncAudioProcessTrack if async_processing else AudioProcessTrack
        return audio_cls(track=relayed, processor=cast(AudioProcessorBase, processor))
    if track.kind == "video":
        video_cls = AsyncVideoProcessTrack if async_processing else VideoProcessTrack
        return video_cls(track=relayed, processor=cast(VideoProcessorBase, processor))
    raise ValueError(f"Unknown track kind {track.kind}")


def _notify_track_created(
    callback: Callable[[TrackType, MediaStreamTrack], None],
    role: Literal["input", "output"],
    track: MediaStreamTrack,
) -> None:
    if track.kind in ("video", "audio"):
        callback(cast(TrackType, f"{role}:{track.kind}"), track)


async def _process_offer_coro(
    mode: WebRtcMode,
    pc: RTCPeerConnection,
    offer: RTCSessionDescription,
    relay: MediaRelay,
    source_video_track: Optional[MediaStreamTrack],
    source_audio_track: Optional[MediaStreamTrack],
    sink_video_track: Optional[MediaSink],
    sink_audio_track: Optional[MediaSink],
    in_recorder: Optional[MediaRecorder],
    out_recorder: Optional[MediaRecorder],
    video_processor: Optional[Union[VideoProcessorBase, CallbackAttachableProcessor]],
    audio_processor: Optional[Union[AudioProcessorBase, CallbackAttachableProcessor]],
    video_receiver: Optional[VideoReceiver],
    audio_receiver: Optional[AudioReceiver],
    async_processing: bool,
    sendback_video: bool,
    sendback_audio: bool,
    on_track_created: Callable[[TrackType, MediaStreamTrack], None],
    remote_description_set_event: asyncio.Event,
):
    def _source_for(kind: str) -> Optional[MediaStreamTrack]:
        return source_audio_track if kind == "audio" else source_video_track

    def _sink_for(kind: str) -> Optional[MediaSink]:
        return sink_audio_track if kind == "audio" else sink_video_track

    def _processor_for(kind: str) -> Optional[ProcessorBase]:
        return audio_processor if kind == "audio" else video_processor

    def _sendback_for(kind: str) -> bool:
        return sendback_video if kind == "video" else sendback_audio

    def _resolve_output(
        kind: str, input_track: Optional[MediaStreamTrack]
    ) -> Optional[MediaStreamTrack]:
        """Pick the track that should be sent back to the peer for ``kind``.

        Precedence: an explicit ``source_*_track`` wins (optionally wrapped
        with a processor). Otherwise, if a sink is configured for the kind,
        no output is produced — the sink is an explicit "consume only"
        signal and silently echoing the input would surprise users who
        chose the sink to avoid that. With neither, fall back to wrapping
        the input (legacy behavior).
        """
        source = _source_for(kind)
        if source is not None:
            return _wrap_with_processor(
                source,
                _processor_for(kind),
                async_processing=async_processing,
                relay=relay,
            )
        if _sink_for(kind) is not None:
            return None
        if input_track is None:
            return None
        return _wrap_with_processor(
            input_track,
            _processor_for(kind),
            async_processing=async_processing,
            relay=relay,
        )

    # Tracks which kinds the peer is actually sending. Populated by `on_track`
    # in SENDRECV mode and consulted after `setRemoteDescription` so we can
    # attach `source_*` for kinds the peer didn't send (e.g. audio-only input
    # paired with a server-side video source).
    peer_sending_kinds: Set[str] = set()

    if mode == WebRtcMode.SENDRECV:

        @pc.listens_to("track")
        def on_track(input_track: MediaStreamTrack):
            logger.info("Track %s received", input_track.kind)
            peer_sending_kinds.add(input_track.kind)
            _notify_track_created(on_track_created, "input", input_track)

            sink = _sink_for(input_track.kind)
            if sink is not None:
                logger.info("Add a track %s to sink %s", input_track, sink)
                sink.addTrack(relay.subscribe(input_track))

            output_track = _resolve_output(input_track.kind, input_track)
            if output_track is not None:
                if _sendback_for(output_track.kind):
                    logger.info("Add a track %s to %s", output_track, pc)
                    pc.addTrack(relay.subscribe(output_track))
                else:
                    logger.info("Block a track %s", output_track)

                if out_recorder:
                    out_recorder.addTrack(relay.subscribe(output_track))
                _notify_track_created(on_track_created, "output", output_track)

            if in_recorder:
                in_recorder.addTrack(relay.subscribe(input_track))

            @input_track.listens_to("ended")
            async def on_ended():
                logger.info("Track %s ended", input_track.kind)
                if in_recorder:
                    await in_recorder.stop()
                if out_recorder:
                    await out_recorder.stop()

    elif mode == WebRtcMode.SENDONLY:

        @pc.listens_to("track")
        def on_track(input_track: MediaStreamTrack):
            logger.info("Track %s received", input_track.kind)
            _notify_track_created(on_track_created, "input", input_track)

            sink = _sink_for(input_track.kind)
            if sink is not None:
                # An explicit sink replaces the auto-receiver path. The
                # processor doesn't apply here — that conflict is rejected
                # at the streamer level.
                logger.info("Add a track %s to sink %s", input_track, sink)
                sink.addTrack(relay.subscribe(input_track))
            else:
                receiver: Union[AudioReceiver, VideoReceiver, None] = (
                    audio_receiver if input_track.kind == "audio" else video_receiver
                )
                if receiver is not None:
                    output_track = _wrap_with_processor(
                        input_track,
                        _processor_for(input_track.kind),
                        async_processing=async_processing,
                        relay=relay,
                    )
                    logger.info("Add a track %s to receiver %s", output_track, receiver)
                    receiver.addTrack(relay.subscribe(output_track))

            if in_recorder:
                in_recorder.addTrack(relay.subscribe(input_track))

            @input_track.listens_to("ended")
            async def on_ended():
                logger.info("Track %s ended", input_track.kind)
                if video_receiver:
                    video_receiver.stop()
                if audio_receiver:
                    audio_receiver.stop()
                if sink_video_track:
                    sink_video_track.stop()
                if sink_audio_track:
                    sink_audio_track.stop()
                if in_recorder:
                    await in_recorder.stop()

    await pc.setRemoteDescription(offer)
    remote_description_set_event.set()

    if mode == WebRtcMode.RECVONLY:
        for t in pc.getTransceivers():
            # RECVONLY has no incoming peer track — the worker emits the
            # configured source (optionally wrapped in a processor).
            output_track = _resolve_output(t.kind, input_track=None)
            if output_track is None:
                continue
            logger.info("Add a track %s to %s", output_track, pc)
            pc.addTrack(relay.subscribe(output_track))
            # NOTE: Recording is not supported in this mode
            # because connecting player to recorder does not work somehow;
            # it generates unplayable movie files.
            _notify_track_created(on_track_created, "output", output_track)

    if mode == WebRtcMode.SENDRECV:
        # `on_track` only fires for kinds the peer is sending, so when the
        # peer offered a recvonly m-section for a kind (one-sided input,
        # e.g. audio-only) the configured `source_*` for that kind has not
        # been attached yet. Symmetric with the RECVONLY block above.
        for t in pc.getTransceivers():
            if t.kind in peer_sending_kinds:
                continue
            output_track = _resolve_output(t.kind, input_track=None)
            if output_track is None:
                continue
            if _sendback_for(t.kind):
                logger.info("Add a track %s to %s", output_track, pc)
                pc.addTrack(relay.subscribe(output_track))
            else:
                logger.info("Block a track %s", output_track)
            if out_recorder:
                out_recorder.addTrack(relay.subscribe(output_track))
            _notify_track_created(on_track_created, "output", output_track)

    if video_receiver and video_receiver.hasTrack():
        video_receiver.start()
    if audio_receiver and audio_receiver.hasTrack():
        audio_receiver.start()
    if sink_video_track is not None and sink_video_track.hasTrack():
        sink_video_track.start()
    if sink_audio_track is not None and sink_audio_track.hasTrack():
        sink_audio_track.start()

    if in_recorder:
        await in_recorder.start()
    if out_recorder:
        await out_recorder.start()

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return pc.localDescription


# See https://stackoverflow.com/a/42007659
process_offer_thread_id_generator = itertools.count()


class WebRtcWorker(Generic[VideoProcessorT, AudioProcessorT]):
    @property
    def video_processor(
        self,
    ) -> Optional[Union[VideoProcessorT, CallbackAttachableProcessor]]:
        return self._video_processor

    @property
    def audio_processor(
        self,
    ) -> Optional[Union[AudioProcessorT, CallbackAttachableProcessor]]:
        return self._audio_processor

    @property
    def video_receiver(self) -> Optional[VideoReceiver]:
        return self._video_receiver

    @property
    def audio_receiver(self) -> Optional[AudioReceiver]:
        return self._audio_receiver

    @property
    def input_video_track(self) -> Optional[MediaStreamTrack]:
        return self._input_video_track

    @property
    def input_audio_track(self) -> Optional[MediaStreamTrack]:
        return self._input_audio_track

    @property
    def output_video_track(self) -> Optional[MediaStreamTrack]:
        return self._output_video_track

    @property
    def output_audio_track(self) -> Optional[MediaStreamTrack]:
        return self._output_audio_track

    def __init__(
        self,
        mode: WebRtcMode,
        rtc_configuration: Optional[RTCConfiguration],
        source_video_track: Optional[MediaStreamTrack],
        source_audio_track: Optional[MediaStreamTrack],
        sink_video_track: Optional[MediaSink],
        sink_audio_track: Optional[MediaSink],
        player_factory: Optional[MediaPlayerFactory],
        in_recorder_factory: Optional[MediaRecorderFactory],
        out_recorder_factory: Optional[MediaRecorderFactory],
        video_frame_callback: Optional[VideoFrameCallback],
        audio_frame_callback: Optional[AudioFrameCallback],
        queued_video_frames_callback: Optional[QueuedVideoFramesCallback],
        queued_audio_frames_callback: Optional[QueuedAudioFramesCallback],
        on_video_ended: Optional[MediaEndedCallback],
        on_audio_ended: Optional[MediaEndedCallback],
        video_processor_factory: Optional[VideoProcessorFactory[VideoProcessorT]],
        audio_processor_factory: Optional[AudioProcessorFactory[AudioProcessorT]],
        async_processing: bool,
        video_receiver_size: int,
        audio_receiver_size: int,
        sendback_video: bool,
        sendback_audio: bool,
        *,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        relay: Optional[MediaRelay] = None,
    ) -> None:
        # Resolve runtime-bound dependencies once at construction so subsequent
        # methods can run without touching Streamlit's Runtime singleton.
        # Callers that own their own loop/relay (e.g. tests) can inject them;
        # if they do, they must have constructed the relay on the same loop.
        self._loop = loop if loop is not None else get_global_event_loop()
        self._relay = relay if relay is not None else get_global_relay()

        self._process_offer_thread: Union[threading.Thread, None] = None
        self.pc = RTCPeerConnection(rtc_configuration)
        self._answer_queue: queue.Queue = queue.Queue()

        with loop_context(self._loop):
            self._remote_description_set = asyncio.Event()

        self.mode = mode
        self.source_video_track = source_video_track
        self.source_audio_track = source_audio_track
        self.sink_video_track = sink_video_track
        self.sink_audio_track = sink_audio_track
        self.player_factory = player_factory
        self.in_recorder_factory = in_recorder_factory
        self.out_recorder_factory = out_recorder_factory
        self.video_frame_callback = video_frame_callback
        self.audio_frame_callback = audio_frame_callback
        self.queued_video_frames_callback = queued_video_frames_callback
        self.queued_audio_frames_callback = queued_audio_frames_callback
        self.on_video_ended = on_video_ended
        self.on_audio_ended = on_audio_ended
        self.video_processor_factory = video_processor_factory
        self.audio_processor_factory = audio_processor_factory
        self.async_processing = async_processing
        self.video_receiver_size = video_receiver_size
        self.audio_receiver_size = audio_receiver_size
        self.sendback_video = sendback_video
        self.sendback_audio = sendback_audio

        self._video_processor: Optional[
            Union[VideoProcessorT, CallbackAttachableProcessor]
        ] = None
        self._audio_processor: Optional[
            Union[AudioProcessorT, CallbackAttachableProcessor]
        ] = None
        self._video_receiver: Optional[VideoReceiver] = None
        self._audio_receiver: Optional[AudioReceiver] = None
        self._input_video_track: Optional[MediaStreamTrack] = None
        self._input_audio_track: Optional[MediaStreamTrack] = None
        self._output_video_track: Optional[MediaStreamTrack] = None
        self._output_audio_track: Optional[MediaStreamTrack] = None
        self._player: Optional[MediaPlayer] = None
        self._relayed_source_video_track: Optional[MediaStreamTrack] = None
        self._relayed_source_audio_track: Optional[MediaStreamTrack] = None

        self._added_ice_candidate_ids: Set[str] = set()

        self._session_shutdown_observer: Optional[SessionShutdownObserver] = (
            SessionShutdownObserver(self.stop)
        )

    def _run_process_offer_thread(
        self,
        sdp: str,
        type_: str,
    ):
        try:
            self._process_offer_thread_impl(
                sdp=sdp,
                type_=type_,
            )
        except Exception as e:
            logger.warn("An error occurred in the WebRTC worker thread: %s", e)
            self._answer_queue.put(e)  # Send the error object to the main thread

    def _process_offer_thread_impl(
        self,
        sdp: str,
        type_: str,
    ):
        logger.debug(
            "_process_offer_thread_impl starts",
        )

        loop = self._loop
        asyncio.set_event_loop(loop)

        offer = RTCSessionDescription(sdp, type_)

        def on_track_created(track_type: TrackType, track: MediaStreamTrack):
            if track_type == "input:video":
                self._input_video_track = track
            elif track_type == "input:audio":
                self._input_audio_track = track
            elif track_type == "output:video":
                self._output_video_track = track
            elif track_type == "output:audio":
                self._output_audio_track = track

        video_processor: Optional[
            Union[VideoProcessorT, CallbackAttachableProcessor]
        ] = None
        if (
            self.video_frame_callback
            or self.queued_video_frames_callback
            or self.on_video_ended
        ):
            video_processor = CallbackAttachableProcessor(
                frame_callback=self.video_frame_callback,
                queued_frames_callback=self.queued_video_frames_callback,
                ended_callback=self.on_video_ended,
            )
        elif self.video_processor_factory:
            video_processor = self.video_processor_factory()

        audio_processor: Optional[
            Union[AudioProcessorT, CallbackAttachableProcessor]
        ] = None
        if (
            self.audio_frame_callback
            or self.queued_audio_frames_callback
            or self.on_audio_ended
        ):
            audio_processor = CallbackAttachableProcessor(
                frame_callback=self.audio_frame_callback,
                queued_frames_callback=self.queued_audio_frames_callback,
                ended_callback=self.on_audio_ended,
            )
        elif self.audio_processor_factory:
            audio_processor = self.audio_processor_factory()

        in_recorder = None
        if self.in_recorder_factory:
            in_recorder = self.in_recorder_factory()

        out_recorder = None
        if self.out_recorder_factory:
            out_recorder = self.out_recorder_factory()

        video_receiver = None
        audio_receiver = None
        if self.mode == WebRtcMode.SENDONLY:
            # An explicit sink for a kind suppresses the auto-receiver for the
            # same kind; the two are alternative strategies for consuming the
            # peer input, and routing the same upstream to both would be
            # surprising.
            if self.sink_video_track is None:
                video_receiver = VideoReceiver(queue_maxsize=self.video_receiver_size)
            if self.sink_audio_track is None:
                audio_receiver = AudioReceiver(queue_maxsize=self.audio_receiver_size)

        self._video_processor = video_processor
        self._audio_processor = audio_processor
        self._video_receiver = video_receiver
        self._audio_receiver = audio_receiver

        relay = self._relay

        source_audio_track = None
        source_video_track = None
        if self.player_factory:
            player = self.player_factory()
            self._player = player
            if player.audio:
                source_audio_track = player.audio
            if player.video:
                source_video_track = player.video
        else:
            if self.source_audio_track:
                self._relayed_source_audio_track = relay.subscribe(
                    self.source_audio_track
                )
                source_audio_track = self._relayed_source_audio_track
            if self.source_video_track:
                self._relayed_source_video_track = relay.subscribe(
                    self.source_video_track
                )
                source_video_track = self._relayed_source_video_track

        @self.pc.listens_to("iceconnectionstatechange")
        async def on_iceconnectionstatechange():
            ice_state = self.pc.iceConnectionState
            logger.debug("ICE connection state is %s", ice_state)

            if ice_state in ("disconnected", "failed", "closed"):
                logger.debug("ICE state=%s -> stopping WebRTC worker", ice_state)

                self._unset_processors()

                if self.pc and self.pc.connectionState != "closed":
                    try:
                        await self.pc.close()
                    except Exception as e:
                        logger.debug(
                            "Error occurred while closing the peer connection", e
                        )
                self.stop()

        process_offer_task = asyncio.run_coroutine_threadsafe(
            _process_offer_coro(
                self.mode,
                self.pc,
                offer,
                relay=relay,
                source_video_track=source_video_track,
                source_audio_track=source_audio_track,
                sink_video_track=self.sink_video_track,
                sink_audio_track=self.sink_audio_track,
                in_recorder=in_recorder,
                out_recorder=out_recorder,
                video_processor=video_processor,
                audio_processor=audio_processor,
                video_receiver=video_receiver,
                audio_receiver=audio_receiver,
                async_processing=self.async_processing,
                sendback_video=self.sendback_video,
                sendback_audio=self.sendback_audio,
                on_track_created=on_track_created,
                remote_description_set_event=self._remote_description_set,
            ),
            loop=loop,
        )

        def callback(done_task: "concurrent.futures.Future"):
            e = done_task.exception()
            if e:
                logger.debug("Error occurred in process_offer")
                logger.debug(e)
                self._answer_queue.put(e)
                return

            localDescription = done_task.result()
            self._answer_queue.put(localDescription)

        process_offer_task.add_done_callback(callback)

    def process_offer(
        self, sdp, type_, timeout: Union[float, None] = None
    ) -> RTCSessionDescription:
        self._process_offer_thread = threading.Thread(
            target=self._run_process_offer_thread,
            kwargs={
                "sdp": sdp,
                "type_": type_,
            },
            daemon=True,
            name=f"process_offer_{next(process_offer_thread_id_generator)}",
        )
        self._process_offer_thread.start()

        try:
            result = self._answer_queue.get(block=True, timeout=timeout)
        except queue.Empty:
            self.stop(timeout=1)
            raise SignallingTimeoutError(
                "Processing offer and initializing the worker "
                f"has not finished in {timeout} seconds"
            )

        if isinstance(result, Exception):
            self.stop(timeout=1)
            raise result

        return result

    def set_ice_candidates_from_offerer(self, candidates: Dict[str, Dict]):
        logger.info("Setting ICE candidates from offerer: %s", candidates)
        for candidate_id, candidate_dict in candidates.items():
            if candidate_id in self._added_ice_candidate_ids:
                continue

            try:
                candidate = candidate_from_sdp(candidate_dict["candidate"])
            except Exception as e:
                logger.error(
                    "Error occurred while parsing candidate %s: %s",
                    candidate_dict["candidate"],
                    e,
                )
                continue
            candidate.sdpMid = candidate_dict.get("sdpMid")
            candidate.sdpMLineIndex = candidate_dict.get("sdpMLineIndex")
            # candidate.usernameFragment = candidate_dict.get("usernameFragment")

            self.add_ice_candidate(candidate)
            self._added_ice_candidate_ids.add(candidate_id)

    def add_ice_candidate(self, candidate: RTCIceCandidate):
        logger.info("Adding ICE candidate: %s", candidate)
        asyncio.run_coroutine_threadsafe(
            self._add_ice_candidate(candidate), loop=self._loop
        )

    async def _add_ice_candidate(self, candidate: RTCIceCandidate):
        # Wait until `setRemoteDescription` is called which sets up the transceiver
        # that `addIceCandidate` will add an ICE candidate to.
        try:
            await asyncio.wait_for(self._remote_description_set.wait(), timeout=10)
        except asyncio.TimeoutError:
            logger.error("Timeout while waiting for the remote description to be set.")
            raise
        await self.pc.addIceCandidate(candidate)

    def update_video_callbacks(
        self,
        frame_callback: Optional[VideoFrameCallback],
        queued_frames_callback: Optional[QueuedVideoFramesCallback],
        on_ended: Optional[MediaEndedCallback],
    ):
        self.video_frame_callback = frame_callback
        self.queued_video_frames_callback = queued_frames_callback
        self.on_video_ended = on_ended

        if not self.video_processor:
            # `update_video_callbacks` can be called before `process_offer` is called that sets up the video processor.
            return
        if type(self.video_processor).__name__ != CallbackAttachableProcessor.__name__:
            raise TypeError(
                f"video_processor has an invalid type: {type(self.video_processor)}"
            )
        video_callback_processor = cast(
            CallbackAttachableProcessor, self.video_processor
        )

        video_callback_processor.update_callbacks(
            frame_callback, queued_frames_callback, on_ended
        )

    def update_audio_callbacks(
        self,
        frame_callback: Optional[AudioFrameCallback],
        queued_frames_callback: Optional[QueuedAudioFramesCallback],
        on_ended: Optional[MediaEndedCallback],
    ):
        self.audio_frame_callback = frame_callback
        self.queued_audio_frames_callback = queued_frames_callback
        self.on_audio_ended = on_ended

        if not self.audio_processor:
            # `update_audio_callbacks` can be called before `process_offer` is called that sets up the audio processor.
            return
        if type(self.audio_processor).__name__ != CallbackAttachableProcessor.__name__:
            raise TypeError(
                f"audio_processor has an invalid type: {type(self.audio_processor)}"
            )
        audio_callback_processor = cast(
            CallbackAttachableProcessor, self.audio_processor
        )

        audio_callback_processor.update_callbacks(
            frame_callback, queued_frames_callback, on_ended
        )

    def _unset_processors(self):
        self._video_processor = None
        self._audio_processor = None

        if self._video_receiver:
            self._video_receiver.stop()
        self._video_receiver = None

        if self._audio_receiver:
            self._audio_receiver.stop()
        self._audio_receiver = None

        if self.sink_video_track is not None:
            self.sink_video_track.stop()
        self.sink_video_track = None
        if self.sink_audio_track is not None:
            self.sink_audio_track.stop()
        self.sink_audio_track = None

        # The player tracks are not automatically stopped when the WebRTC session ends
        # because these tracks are connected to the consumer via `MediaRelay` proxies
        # so `stop()` on the consumer is not delegated to the source tracks.
        # So the player is stopped manually here when the worker stops.
        if self._player:
            if self._player.video:
                self._player.video.stop()
            if self._player.audio:
                self._player.audio.stop()
        self._player = None

        # Same as above,
        # the source tracks are not automatically stopped when the WebRTC.
        # Only the relayed tracks are stopped here because
        # the upstream tracks may still be used by other consumers.
        if self._relayed_source_audio_track:
            logger.debug("Stopping the relayed source audio track")
            self._relayed_source_audio_track.stop()
        self.source_audio_track = None
        self._relayed_source_audio_track = None
        if self._relayed_source_video_track:
            logger.debug("Stopping the relayed source video track")
            self._relayed_source_video_track.stop()
        self.source_video_track = None
        self._relayed_source_video_track = None

    def stop(self, timeout: Union[float, None] = 1.0):
        logger.debug("Stopping WebRTC worker")

        self._unset_processors()

        if self._process_offer_thread:
            self._process_offer_thread.join(timeout=timeout)
            self._process_offer_thread = None

        if self.pc and self.pc.connectionState != "closed":
            loop = self._loop
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(self.pc.close(), loop=loop)
            else:
                loop.run_until_complete(self.pc.close())

        # 💡 Explicitly stop shutdown observer here
        if self._session_shutdown_observer:
            self._session_shutdown_observer.stop()
            self._session_shutdown_observer = None
