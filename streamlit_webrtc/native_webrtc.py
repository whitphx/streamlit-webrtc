from __future__ import annotations

import asyncio
import concurrent.futures
import importlib
import logging
import threading
from typing import Any

import av
from aiortc import RTCConfiguration, RTCSessionDescription

from .eventloop import get_global_event_loop
from .models import AudioFrameCallback, CallbackAttachableProcessor, MediaEndedCallback
from .shutdown import SessionShutdownObserver
from .webrtc import SignallingTimeoutError

logger = logging.getLogger(__name__)


def load_native_peer() -> Any:
    try:
        return importlib.import_module("streamlit_webrtc_native").AudioPeer
    except ImportError as exc:
        raise ImportError(
            'backend="native" requires the experimental streamlit-webrtc-native '
            "companion. Install a wheel built from packages/streamlit-webrtc-native; "
            "see packages/streamlit-webrtc-native/README.md."
        ) from exc


class NativeAudioWorker:
    backend = "native"
    video_processor = None
    video_receiver = None
    audio_receiver = None
    source_video_track = None
    source_audio_track = None
    sink_video_track = None
    sink_audio_track = None
    input_video_track = None
    input_audio_track = None
    output_video_track = None
    output_audio_track = None

    def __init__(
        self,
        *,
        rtc_configuration: RTCConfiguration | None,
        audio_frame_callback: AudioFrameCallback | None,
        on_audio_ended: MediaEndedCallback | None,
        async_processing: bool,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self._peer_class = load_native_peer()
        self._loop = loop if loop is not None else get_global_event_loop()
        self.audio_processor = CallbackAttachableProcessor[av.AudioFrame](
            audio_frame_callback, None, on_audio_ended
        )
        self.local_description: RTCSessionDescription | None = None
        self._async_processing = async_processing
        self._ice_servers = (
            [
                (
                    [server.urls] if isinstance(server.urls, str) else server.urls,
                    server.username or "",
                    server.credential or "",
                )
                for server in (rtc_configuration.iceServers or [])
            ]
            if rtc_configuration
            else []
        )
        self._peer: Any = None
        self._run_task: asyncio.Task | None = None
        self._callback_task: asyncio.Task | None = None
        self._close_lock = asyncio.Lock()
        self._transport_closed = False
        self._finishing = False
        self._stopped = threading.Event()
        self._generation = 0
        self._candidate_ids: set[str] = set()
        self._candidate_tasks: set[asyncio.Task] = set()
        self._answer: concurrent.futures.Future[RTCSessionDescription] = (
            concurrent.futures.Future()
        )
        self._session_shutdown_observer = SessionShutdownObserver(self.stop)

    def process_offer(
        self, sdp: str, type_: str, timeout: float = 10
    ) -> RTCSessionDescription:
        if type_ != "offer":
            self.stop()
            raise ValueError("The native backend requires an SDP offer")
        if self._on_loop():
            raise RuntimeError("process_offer() must run outside the WebRTC event loop")
        asyncio.run_coroutine_threadsafe(self._run(sdp), self._loop)
        try:
            return self._answer.result(timeout)
        except concurrent.futures.TimeoutError as exc:
            self.stop()
            raise SignallingTimeoutError("Native WebRTC negotiation timed out") from exc
        except BaseException:
            self.stop()
            raise

    async def _run(self, sdp: str) -> None:
        self._run_task = asyncio.current_task()
        try:
            if self._stopped.is_set():
                return
            self._peer = self._peer_class(ice_servers=self._ice_servers)
            answer = await self._peer.answer(sdp)
            if self._stopped.is_set():
                return
            self.local_description = RTCSessionDescription(sdp=answer, type="answer")
            self._answer.set_result(self.local_description)
            while not self._stopped.is_set():
                frame = await self._peer.recv()
                generation = self._generation
                pts, time_base = frame.pts, frame.time_base
                if self._async_processing:
                    self._callback_task = asyncio.create_task(
                        asyncio.to_thread(self.audio_processor.recv, frame)
                    )
                    # Cancellation cannot stop a Python callback already running in
                    # a thread. Keep its task so on_ended runs after it finishes.
                    output = await asyncio.shield(self._callback_task)
                    self._callback_task = None
                else:
                    output = self.audio_processor.recv(frame)
                if self._stopped.is_set() or generation != self._generation:
                    continue
                if not isinstance(output, av.AudioFrame):
                    raise TypeError("audio_frame_callback must return an av.AudioFrame")
                output.pts, output.time_base = pts, time_base
                try:
                    await self._peer.send(output)
                except RuntimeError:
                    if generation == self._generation and not self._stopped.is_set():
                        raise
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            if not self._answer.done():
                self._answer.set_exception(exc)
            elif not self._stopped.is_set():
                logger.exception("Native audio processing stopped")
        finally:
            self._finishing = True
            self._stopped.set()
            if not self._answer.done():
                self._answer.set_exception(RuntimeError("Native WebRTC worker stopped"))
            await self._close_transport()
            await asyncio.to_thread(self._session_shutdown_observer.stop)
            if self._callback_task is not None:
                try:
                    await self._callback_task
                except Exception:
                    logger.exception("Native audio callback failed during shutdown")
            try:
                await asyncio.to_thread(self.audio_processor.on_ended)
            except Exception:
                logger.exception("Native audio ended callback failed")

    async def _close_transport(self) -> None:
        async with self._close_lock:
            if self._transport_closed:
                return
            for task in self._candidate_tasks:
                task.cancel()
            if self._peer is not None:
                await self._peer.close()
            self._transport_closed = True

    async def _shutdown(self) -> None:
        # A callback can call stop() and let _run enter cleanup before this runs.
        if (
            not self._finishing
            and self._run_task is not None
            and not self._run_task.done()
        ):
            self._run_task.cancel()
        await self._close_transport()

    def _on_loop(self) -> bool:
        try:
            return asyncio.get_running_loop() is self._loop
        except RuntimeError:
            return False

    def stop(self, timeout: float = 1.0) -> None:
        if self._stopped.is_set():
            return
        self._stopped.set()
        self._session_shutdown_observer.stop()
        if self._loop.is_closed() or not self._loop.is_running():
            return
        if self._on_loop():
            self._loop.create_task(self._shutdown())
            return
        future = asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop)
        try:
            future.result(timeout)
        except concurrent.futures.TimeoutError:
            logger.warning("Native audio shutdown is still pending")

    async def _clear_audio_output(self) -> None:
        if self._stopped.is_set() or self._peer is None:
            return
        self._generation += 1
        await self._peer.clear_output()

    def clear_audio_output(self, timeout: float = 1.0) -> None:
        if self._stopped.is_set():
            return
        if self._on_loop():
            raise RuntimeError(
                "clear_audio_output() must run outside the WebRTC event loop"
            )
        future = asyncio.run_coroutine_threadsafe(
            self._clear_audio_output(), self._loop
        )
        future.result(timeout)

    def update_audio_callbacks(
        self,
        frame_callback: AudioFrameCallback | None,
        queued_frames_callback: Any,
        on_ended: MediaEndedCallback | None,
    ) -> None:
        self.audio_processor.update_callbacks(frame_callback, None, on_ended)

    def set_ice_candidates_from_offerer(self, candidates: dict) -> None:
        for candidate_id, candidate in candidates.items():
            if candidate_id in self._candidate_ids:
                continue
            if not isinstance(candidate, dict):
                continue
            mid = candidate.get("sdpMid")
            index = candidate.get("sdpMLineIndex")
            value = candidate.get("candidate")
            if (
                not isinstance(mid, str)
                or not isinstance(index, int)
                or not isinstance(value, str)
            ):
                continue
            self._candidate_ids.add(candidate_id)
            self._loop.call_soon_threadsafe(self._schedule_candidate, mid, index, value)

    def _schedule_candidate(self, mid: str, index: int, value: str) -> None:
        if self._stopped.is_set():
            return
        task = self._loop.create_task(self._add_candidate(mid, index, value))
        self._candidate_tasks.add(task)
        task.add_done_callback(self._candidate_tasks.discard)

    async def _add_candidate(self, mid: str, index: int, value: str) -> None:
        try:
            await asyncio.wrap_future(self._answer)
            if not self._stopped.is_set():
                await self._peer.add_ice_candidate(mid, index, value)
        except Exception:
            logger.exception("Native ICE candidate failed")
