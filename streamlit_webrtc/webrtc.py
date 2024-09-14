import asyncio
import enum
import itertools
import logging
import queue
import threading
from typing import Callable, Generic, Literal, Optional, Union, cast

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer, MediaRecorder, MediaRelay
from aiortc.mediastreams import MediaStreamTrack

from streamlit_webrtc.shutdown import SessionShutdownObserver

from .eventloop import get_global_event_loop
from .models import (
    AudioFrameCallback,
    AudioProcessorBase,
    AudioProcessorFactory,
    AudioProcessorT,
    CallbackAttachableProcessor,
    MediaEndedCallback,
    MediaPlayerFactory,
    MediaRecorderFactory,
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

__all__ = [
    "AudioProcessorBase",
    "AudioProcessorFactory",
    "VideoTransformerBase",
    "VideoProcessorBase",
    "MediaPlayerFactory",
    "MediaRecorderFactory",
    "VideoProcessorFactory",
    "WebRtcMode",
    "TimeoutError",
    "WebRtcWorker",
]


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class WebRtcMode(enum.Enum):
    RECVONLY = enum.auto()
    SENDONLY = enum.auto()
    SENDRECV = enum.auto()


class TimeoutError(Exception):
    pass


TrackType = Literal["input:video", "input:audio", "output:video", "output:audio"]


async def _process_offer_coro(
    mode: WebRtcMode,
    pc: RTCPeerConnection,
    offer: RTCSessionDescription,
    relay: MediaRelay,
    source_video_track: Optional[MediaStreamTrack],
    source_audio_track: Optional[MediaStreamTrack],
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
):
    AudioTrack = AsyncAudioProcessTrack if async_processing else AudioProcessTrack
    VideoTrack = AsyncVideoProcessTrack if async_processing else VideoProcessTrack

    if mode == WebRtcMode.SENDRECV:

        @pc.on("track")
        def on_track(input_track: MediaStreamTrack):
            logger.info("Track %s received", input_track.kind)

            if input_track.kind == "video":
                on_track_created("input:video", input_track)
            elif input_track.kind == "audio":
                on_track_created("input:audio", input_track)

            if input_track.kind == "audio":
                if source_audio_track:
                    logger.info("Set %s as an input audio track", source_audio_track)
                    output_track = source_audio_track
                elif audio_processor:
                    logger.info(
                        "Set %s as an input audio track with audio_processor %s",
                        input_track,
                        AudioTrack,
                    )
                    output_track = AudioTrack(
                        track=relay.subscribe(input_track),
                        processor=audio_processor,
                    )
                else:
                    output_track = input_track  # passthrough
            elif input_track.kind == "video":
                if source_video_track:
                    logger.info("Set %s as an input video track", source_video_track)
                    output_track = source_video_track
                elif video_processor:
                    logger.info(
                        "Set %s as an input video track with video_processor %s",
                        input_track,
                        VideoTrack,
                    )
                    output_track = VideoTrack(
                        track=relay.subscribe(input_track),
                        processor=video_processor,
                    )
                else:
                    output_track = input_track
            else:
                raise Exception(f"Unknown track kind {input_track.kind}")

            if (output_track.kind == "video" and sendback_video) or (
                output_track.kind == "audio" and sendback_audio
            ):
                logger.info(
                    "Add a track %s of kind %s to %s",
                    output_track,
                    output_track.kind,
                    pc,
                )
                pc.addTrack(relay.subscribe(output_track))
            else:
                logger.info(
                    "Block a track %s of kind %s", output_track, output_track.kind
                )

            if out_recorder:
                logger.info("Track %s is added to out_recorder", output_track.kind)
                out_recorder.addTrack(relay.subscribe(output_track))
            if in_recorder:
                logger.info("Track %s is added to in_recorder", input_track.kind)
                in_recorder.addTrack(relay.subscribe(input_track))

            if output_track.kind == "video":
                on_track_created("output:video", output_track)
            elif output_track.kind == "audio":
                on_track_created("output:audio", output_track)

            @input_track.on("ended")
            async def on_ended():
                logger.info("Track %s ended", input_track.kind)
                if in_recorder:
                    await in_recorder.stop()
                if out_recorder:
                    await out_recorder.stop()

    elif mode == WebRtcMode.SENDONLY:

        @pc.on("track")
        def on_track(input_track: MediaStreamTrack):
            logger.info("Track %s received", input_track.kind)

            if input_track.kind == "video":
                on_track_created("input:video", input_track)
            elif input_track.kind == "audio":
                on_track_created("input:audio", input_track)

            if input_track.kind == "audio":
                if audio_receiver:
                    if audio_processor:
                        logger.info(
                            "Set %s as an input audio track with audio_processor %s",
                            input_track,
                            AudioTrack,
                        )
                        output_track = AudioTrack(
                            track=relay.subscribe(input_track),
                            processor=audio_processor,
                        )
                    else:
                        output_track = input_track  # passthrough
                    logger.info(
                        "Add a track %s to receiver %s", output_track, audio_receiver
                    )
                    audio_receiver.addTrack(relay.subscribe(output_track))
            elif input_track.kind == "video":
                if video_receiver:
                    if video_processor:
                        logger.info(
                            "Set %s as an input video track with video_processor %s",
                            input_track,
                            VideoTrack,
                        )
                        output_track = VideoTrack(
                            track=relay.subscribe(input_track),
                            processor=video_processor,
                        )
                    else:
                        output_track = input_track  # passthrough
                    logger.info(
                        "Add a track %s to receiver %s", output_track, video_receiver
                    )
                    video_receiver.addTrack(relay.subscribe(output_track))

            if in_recorder:
                logger.info("Track %s is added to in_recorder", input_track.kind)
                in_recorder.addTrack(relay.subscribe(input_track))

            @input_track.on("ended")
            async def on_ended():
                logger.info("Track %s ended", input_track.kind)
                if video_receiver:
                    video_receiver.stop()
                if audio_receiver:
                    audio_receiver.stop()
                if in_recorder:
                    await in_recorder.stop()

    await pc.setRemoteDescription(offer)
    if mode == WebRtcMode.RECVONLY:
        for t in pc.getTransceivers():
            output_track = None
            if t.kind == "audio":
                if source_audio_track:
                    if audio_processor:
                        logger.info(
                            "Set %s as an input audio track with audio_processor %s",
                            source_audio_track,
                            AudioTrack,
                        )
                        output_track = AudioTrack(
                            track=source_audio_track, processor=audio_processor
                        )
                    else:
                        output_track = source_audio_track  # passthrough
            elif t.kind == "video":
                if source_video_track:
                    if video_processor:
                        logger.info(
                            "Set %s as an input video track with video_processor %s",
                            source_video_track,
                            VideoTrack,
                        )
                        output_track = VideoTrack(
                            track=source_video_track, processor=video_processor
                        )
                    else:
                        output_track = source_video_track  # passthrough

            if output_track:
                logger.info("Add a track %s to %s", output_track, pc)
                pc.addTrack(relay.subscribe(output_track))
                # NOTE: Recording is not supported in this mode
                # because connecting player to recorder does not work somehow;
                # it generates unplayable movie files.

                if output_track.kind == "video":
                    on_track_created("output:video", output_track)
                elif output_track.kind == "audio":
                    on_track_created("output:audio", output_track)

    if video_receiver and video_receiver.hasTrack():
        video_receiver.start()
    if audio_receiver and audio_receiver.hasTrack():
        audio_receiver.start()

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
        source_video_track: Optional[MediaStreamTrack],
        source_audio_track: Optional[MediaStreamTrack],
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
    ) -> None:
        self._process_offer_thread: Union[threading.Thread, None] = None
        self.pc = RTCPeerConnection()
        self._answer_queue: queue.Queue = queue.Queue()

        self.mode = mode
        self.source_video_track = source_video_track
        self.source_audio_track = source_audio_track
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
        self._relayed_source_video_track: Optional[MediaRelay] = None
        self._relayed_source_audio_track: Optional[MediaRelay] = None

        self._session_shutdown_observer = SessionShutdownObserver(self.stop)

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

        loop = get_global_event_loop()
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
            video_receiver = VideoReceiver(queue_maxsize=self.video_receiver_size)
            audio_receiver = AudioReceiver(queue_maxsize=self.audio_receiver_size)

        self._video_processor = video_processor
        self._audio_processor = audio_processor
        self._video_receiver = video_receiver
        self._audio_receiver = audio_receiver

        relay = get_global_relay()

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

        @self.pc.on("iceconnectionstatechange")
        async def on_iceconnectionstatechange():
            logger.info("ICE connection state is %s", self.pc.iceConnectionState)
            iceConnectionState = self.pc.iceConnectionState
            if iceConnectionState == "closed" or iceConnectionState == "failed":
                self._unset_processors()
            if self.pc.iceConnectionState == "failed":
                await self.pc.close()

        process_offer_task = loop.create_task(
            _process_offer_coro(
                self.mode,
                self.pc,
                offer,
                relay=relay,
                source_video_track=source_video_track,
                source_audio_track=source_audio_track,
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
            )
        )

        def callback(done_task: asyncio.Task):
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
        self, sdp, type_, timeout: Union[float, None] = 10.0
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
            raise TimeoutError(
                "Processing offer and initializing the worker "
                f"has not finished in {timeout} seconds"
            )

        if isinstance(result, Exception):
            raise result

        return result

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
            raise TypeError("video_processor is None")
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
            raise TypeError("audio_processor is None")
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
        self._unset_processors()
        if self._process_offer_thread:
            self._process_offer_thread.join(timeout=timeout)
            self._process_offer_thread = None

        if self.pc and self.pc.connectionState != "closed":
            loop = get_global_event_loop()
            if loop.is_running():
                loop.create_task(self.pc.close())
            else:
                loop.run_until_complete(self.pc.close())

        self._session_shutdown_observer.stop()


def _test():
    # Mock functions that depend on Streamlit global server object
    global get_global_relay, get_global_event_loop

    loop = asyncio.get_event_loop()

    def get_global_event_loop_mock():
        return loop

    get_global_event_loop = get_global_event_loop_mock

    fake_global_relay = MediaRelay()

    def get_global_relay_mock():
        return fake_global_relay

    get_global_relay = get_global_relay_mock

    # Start the test
    client = RTCPeerConnection()
    client.createDataChannel("test")

    offer = loop.run_until_complete(client.createOffer())
    logger.debug("Offer for mock testing: %s", offer)

    def test_thread_fn():
        webrtc_worker = WebRtcWorker(mode=WebRtcMode.SENDRECV)
        localDescription = webrtc_worker.process_offer(offer.sdp, offer.type)

        logger.debug("localDescription:")
        logger.debug(localDescription)

        webrtc_worker.stop()

    test_thread = threading.Thread(target=test_thread_fn)
    test_thread.start()

    # HACK
    for _ in range(100):
        loop.run_until_complete(asyncio.sleep(0.01))


if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)

    _test()
