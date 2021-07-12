from typing import List
import math

import av
import cv2
import numpy as np

from streamlit_server_state import server_state, server_state_lock

from streamlit_webrtc import ClientSettings, WebRtcMode, webrtc_streamer
from streamlit_webrtc.mux import MuxerBase
from streamlit_webrtc.factory import create_mux_track


class MultiWindowMuxer(MuxerBase):
    def on_update(self, frames: List[av.VideoFrame]) -> av.VideoFrame:
        buf_w = 640
        buf_h = 480
        buffer = np.zeros((buf_h, buf_w, 3), dtype=np.uint8)

        n_inputs = len(frames)

        n_cols = math.ceil(math.sqrt(n_inputs))
        n_rows = math.ceil(n_inputs / n_cols)
        grid_w = buf_w // n_cols
        grid_h = buf_h // n_rows

        for i in range(n_inputs):
            frame = frames[i]
            if frame is None:
                continue

            grid_x = (i % n_cols) * grid_w
            grid_y = (i // n_cols) * grid_h

            img = frame.to_ndarray(format="bgr24")
            src_h, src_w = img.shape[0:2]

            aspect_ratio = src_w / src_h

            window_w = min(grid_w, int(grid_h * aspect_ratio))
            window_h = min(grid_h, int(window_w / aspect_ratio))

            window_offset_x = (grid_w - window_w) // 2
            window_offset_y = (grid_h - window_h) // 2

            window_x0 = grid_x + window_offset_x
            window_y0 = grid_y + window_offset_y
            window_x1 = window_x0 + window_w
            window_y1 = window_y0 + window_h

            buffer[window_y0:window_y1, window_x0:window_x1, :] = cv2.resize(
                img, (window_w, window_h)
            )

        new_frame = av.VideoFrame.from_ndarray(buffer, format="bgr24")

        return new_frame


def main():
    if "webrtc_contexts" not in server_state:
        server_state["webrtc_contexts"] = []

    self_ctx = webrtc_streamer(
        key="self",
        mode=WebRtcMode.SENDRECV,
        client_settings=ClientSettings(
            rtc_configuration={
                "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
            },
            media_stream_constraints={"video": True, "audio": True},
        ),
        sendback_audio=False,
    )

    with server_state_lock["webrtc_contexts"]:
        webrtc_contexts = server_state["webrtc_contexts"]
        if self_ctx.state.playing and self_ctx not in webrtc_contexts:
            webrtc_contexts.append(self_ctx)
            server_state["webrtc_contexts"] = webrtc_contexts
        elif not self_ctx.state.playing and self_ctx in webrtc_contexts:
            webrtc_contexts.remove(self_ctx)
            server_state["webrtc_contexts"] = webrtc_contexts

    active_other_ctxs = [
        ctx for ctx in webrtc_contexts if ctx != self_ctx and ctx.state.playing
    ]

    mux_track = create_mux_track(
        kind="video", muxer_factory=MultiWindowMuxer, key="mux"
    )

    for ctx in active_other_ctxs:
        mux_track.add_input_track(ctx.output_video_track)
        webrtc_streamer(
            key=f"sound-{id(ctx)}",
            mode=WebRtcMode.RECVONLY,
            client_settings=ClientSettings(
                rtc_configuration={
                    "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
                },
                media_stream_constraints={"video": False, "audio": True},
            ),
            source_audio_track=ctx.output_audio_track,
            desired_playing_state=True,
        )

    if len(active_other_ctxs) > 0:
        webrtc_streamer(
            key="participants",
            mode=WebRtcMode.RECVONLY,
            client_settings=ClientSettings(
                rtc_configuration={
                    "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
                },
                media_stream_constraints={"video": True, "audio": False},
            ),
            source_video_track=mux_track,
            desired_playing_state=True,
        )


if __name__ == "__main__":
    main()
