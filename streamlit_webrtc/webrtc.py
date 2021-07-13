import asyncio
import enum
import itertools
import logging
import queue
import threading
from typing import Callable, Generic, Optional, TypeVar, Union

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer, MediaRecorder, MediaRelay

from .eventloop import get_server_event_loop
from .process import (
    AsyncAudioProcessTrack,
    AsyncVideoProcessTrack,
    AudioProcessorBase,
    AudioProcessTrack,
    VideoProcessorBase,
    VideoProcessTrack,
    VideoTransformerBase,
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


VideoProcessorT = TypeVar("VideoProcessorT", bound=VideoProcessorBase)
AudioProcessorT = TypeVar("AudioProcessorT", bound=AudioProcessorBase)

MediaPlayerFactory = Callable[[], MediaPlayer]
MediaRecorderFactory = Callable[[], MediaRecorder]
VideoProcessorFactory = Callable[[], VideoProcessorT]
AudioProcessorFactory = Callable[[], AudioProcessorT]


class WebRtcMode(enum.Enum):
    RECVONLY = enum.auto()
    SENDONLY = enum.auto()
    SENDRECV = enum.auto()


class TimeoutError(Exception):
    pass


async def _process_offer(
    mode: WebRtcMode,
    pc: RTCPeerConnection,
    offer: RTCSessionDescription,
    relay: MediaRelay,
    player_factory: Optional[MediaPlayerFactory],
    in_recorder_factory: Optional[MediaRecorderFactory],
    out_recorder_factory: Optional[MediaRecorderFactory],
    video_processor: Optional[VideoProcessorBase],
    audio_processor: Optional[AudioProcessorBase],
    video_receiver: Optional[VideoReceiver],
    audio_receiver: Optional[AudioReceiver],
    async_processing: bool,
    callback: Callable[[Union[RTCSessionDescription, Exception]], None],
):
    try:
        player = None
        if player_factory:
            player = player_factory()

        in_recorder = None
        if in_recorder_factory:
            in_recorder = in_recorder_factory()

        out_recorder = None
        if out_recorder_factory:
            out_recorder = out_recorder_factory()

        @pc.on("iceconnectionstatechange")
        async def on_iceconnectionstatechange():
            logger.info("ICE connection state is %s", pc.iceConnectionState)
            if pc.iceConnectionState == "failed":
                await pc.close()

        if mode == WebRtcMode.SENDRECV:

            @pc.on("track")
            def on_track(input_track):
                logger.info("Track %s received", input_track.kind)

                output_track = None

                if input_track.kind == "audio":
                    if player and player.audio:
                        logger.info("Add player to audio track")
                        output_track = player.audio
                    elif audio_processor:
                        AudioTrack = (
                            AsyncAudioProcessTrack
                            if async_processing
                            else AudioProcessTrack
                        )
                        logger.info(
                            "Add a input audio track %s to "
                            "output track with audio_processor %s",
                            input_track,
                            AudioTrack,
                        )
                        output_track = AudioTrack(
                            track=relay.subscribe(input_track),
                            processor=audio_processor,
                        )
                        logger.info("Add the audio track with processor to %s", pc)
                    else:
                        output_track = input_track  # passthrough
                elif input_track.kind == "video":
                    if player and player.video:
                        logger.info("Add player to video track")
                        output_track = player.video
                    elif video_processor:
                        VideoTrack = (
                            AsyncVideoProcessTrack
                            if async_processing
                            else VideoProcessTrack
                        )
                        logger.info(
                            "Add a input video track %s to "
                            "output track with video_processor %s",
                            input_track,
                            VideoTrack,
                        )
                        output_track = VideoTrack(
                            track=relay.subscribe(input_track),
                            processor=video_processor,
                        )
                        logger.info("Add the video track with processor to %s", pc)
                    else:
                        output_track = input_track

                if not output_track:
                    raise Exception(
                        "Neither a player nor a processor is created. "
                        "Either factory must be set."
                    )

                pc.addTrack(relay.subscribe(output_track))
                if out_recorder:
                    logger.info("Track %s is added to out_recorder", output_track.kind)
                    out_recorder.addTrack(relay.subscribe(output_track))
                if in_recorder:
                    logger.info("Track %s is added to in_recorder", input_track.kind)
                    in_recorder.addTrack(relay.subscribe(input_track))

                @input_track.on("ended")
                async def on_ended():
                    logger.info("Track %s ended", input_track.kind)
                    if in_recorder:
                        await in_recorder.stop()
                    if out_recorder:
                        await out_recorder.stop()

        elif mode == WebRtcMode.SENDONLY:

            @pc.on("track")
            def on_track(input_track):
                logger.info("Track %s received", input_track.kind)

                if input_track.kind == "audio":
                    if audio_receiver:
                        logger.info(
                            "Add a track %s to receiver %s", input_track, audio_receiver
                        )
                        audio_receiver.addTrack(input_track)
                elif input_track.kind == "video":
                    if video_receiver:
                        logger.info(
                            "Add a track %s to receiver %s", input_track, video_receiver
                        )
                        video_receiver.addTrack(input_track)

                if in_recorder:
                    logger.info("Track %s is added to in_recorder", input_track.kind)
                    in_recorder.addTrack(input_track)

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
                    if player and player.audio:
                        if audio_processor:
                            AudioTrack = (
                                AsyncAudioProcessTrack
                                if async_processing
                                else AudioProcessTrack
                            )
                            logger.info(
                                "Add a input audio track from a player %s to "
                                "output track with audio_processor %s",
                                player.audio,
                                AudioTrack,
                            )
                            output_track = AudioTrack(
                                track=player.audio, processor=audio_processor
                            )
                            logger.info("Add the audio track with processor to %s", pc)

                            @output_track.on("ended")
                            async def on_ended():
                                logger.info(
                                    "Track %s ended. Stop its input track %s",
                                    output_track.kind,
                                    player.audio,
                                )
                                player.audio.stop()

                        else:
                            output_track = player.audio  # passthrough
                elif t.kind == "video":
                    if player and player.video:
                        if video_processor:
                            VideoTrack = (
                                AsyncVideoProcessTrack
                                if async_processing
                                else VideoProcessTrack
                            )
                            logger.info(
                                "Add a input video track from a player %s to "
                                "output track with video_processor %s",
                                player.video,
                                VideoTrack,
                            )
                            output_track = VideoTrack(
                                track=player.video, processor=video_processor
                            )
                            logger.info("Add the video track with processor to %s", pc)

                            @output_track.on("ended")
                            async def on_ended():
                                logger.info(
                                    "Track %s ended. Stop its input track %s",
                                    output_track.kind,
                                    player.video,
                                )
                                player.video.stop()

                        else:
                            output_track = player.video  # passthrough

                if output_track:
                    pc.addTrack(output_track)
                    # NOTE: Recording is not supported in this mode
                    # because connecting player to recorder does not work somehow;
                    # it generates unplayable movie files.

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

        callback(pc.localDescription)
    except Exception as e:
        logger.debug("Error occurred in process_offer")
        logger.debug(e)
        callback(e)


# See https://stackoverflow.com/a/42007659
webrtc_thread_id_generator = itertools.count()


class WebRtcWorker(Generic[VideoProcessorT, AudioProcessorT]):
    _webrtc_thread: Union[threading.Thread, None]
    _answer_queue: queue.Queue
    _video_processor: Optional[VideoProcessorT]
    _audio_processor: Optional[AudioProcessorT]
    _video_receiver: Optional[VideoReceiver]
    _audio_receiver: Optional[AudioReceiver]

    @property
    def video_processor(self) -> Optional[VideoProcessorT]:
        return self._video_processor

    @property
    def audio_processor(self) -> Optional[AudioProcessorT]:
        return self._audio_processor

    @property
    def video_receiver(self) -> Optional[VideoReceiver]:
        return self._video_receiver

    @property
    def audio_receiver(self) -> Optional[AudioReceiver]:
        return self._audio_receiver

    def __init__(
        self,
        mode: WebRtcMode,
        player_factory: Optional[MediaPlayerFactory] = None,
        in_recorder_factory: Optional[MediaRecorderFactory] = None,
        out_recorder_factory: Optional[MediaRecorderFactory] = None,
        video_processor_factory: Optional[
            VideoProcessorFactory[VideoProcessorT]
        ] = None,
        audio_processor_factory: Optional[
            AudioProcessorFactory[AudioProcessorT]
        ] = None,
        async_processing: bool = True,
        video_receiver_size: int = 4,
        audio_receiver_size: int = 4,
    ) -> None:
        self._webrtc_thread = None
        self.pc = RTCPeerConnection()
        self._answer_queue = queue.Queue()

        self.mode = mode
        self.player_factory = player_factory
        self.in_recorder_factory = in_recorder_factory
        self.out_recorder_factory = out_recorder_factory
        self.video_processor_factory = video_processor_factory
        self.audio_processor_factory = audio_processor_factory
        self.async_processing = async_processing
        self.video_receiver_size = video_receiver_size
        self.audio_receiver_size = audio_receiver_size

        self._video_processor = None
        self._audio_processor = None
        self._video_receiver = None
        self._audio_receiver = None

    def _run_webrtc_thread(
        self,
        sdp: str,
        type_: str,
    ):
        try:
            self._webrtc_thread_impl(
                sdp=sdp,
                type_=type_,
            )
        except Exception as e:
            logger.warn("An error occurred in the WebRTC worker thread: %s", e)
            self._answer_queue.put(e)  # Send the error object to the main thread

    def _webrtc_thread_impl(
        self,
        sdp: str,
        type_: str,
    ):
        logger.debug(
            "_webrtc_thread_impl starts",
        )

        loop = get_server_event_loop()

        offer = RTCSessionDescription(sdp, type_)

        def callback(localDescription):
            self._answer_queue.put(localDescription)

        video_processor = None
        if self.video_processor_factory:
            video_processor = self.video_processor_factory()

        audio_processor = None
        if self.audio_processor_factory:
            audio_processor = self.audio_processor_factory()

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

        @self.pc.on("iceconnectionstatechange")
        async def on_iceconnectionstatechange():
            iceConnectionState = self.pc.iceConnectionState
            if iceConnectionState == "closed" or iceConnectionState == "failed":
                self._unset_processors()

        loop.create_task(
            _process_offer(
                self.mode,
                self.pc,
                offer,
                relay=relay,
                player_factory=self.player_factory,
                in_recorder_factory=self.in_recorder_factory,
                out_recorder_factory=self.out_recorder_factory,
                video_processor=video_processor,
                audio_processor=audio_processor,
                video_receiver=video_receiver,
                audio_receiver=audio_receiver,
                async_processing=self.async_processing,
                callback=callback,
            )
        )

    def process_offer(
        self, sdp, type_, timeout: Union[float, None] = 10.0
    ) -> RTCSessionDescription:
        self._webrtc_thread = threading.Thread(
            target=self._run_webrtc_thread,
            kwargs={
                "sdp": sdp,
                "type_": type_,
            },
            daemon=True,
            name=f"webrtc_worker_{next(webrtc_thread_id_generator)}",
        )
        self._webrtc_thread.start()

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

    def _unset_processors(self):
        self._video_processor = None
        self._audio_processor = None
        if self._video_receiver:
            self._video_receiver.stop()
        self._video_receiver = None
        if self._audio_receiver:
            self._audio_receiver.stop()
        self._audio_receiver = None

    def stop(self, timeout: Union[float, None] = 1.0):
        self._unset_processors()
        if self._webrtc_thread:
            self._webrtc_thread.join(timeout=timeout)


async def _test():
    client = RTCPeerConnection()
    client.createDataChannel("test")

    offer = await client.createOffer()

    webrtc_worker = WebRtcWorker(mode=WebRtcMode.SENDRECV)
    localDescription = webrtc_worker.process_offer(offer.sdp, offer.type)

    print("localDescription:")
    print(localDescription)

    webrtc_worker.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    asyncio.run(_test())
