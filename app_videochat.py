from streamlit_server_state import server_state, server_state_lock

from streamlit_webrtc import ClientSettings, WebRtcMode, webrtc_streamer


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
            media_stream_constraints={
                "video": True,
                "audio": True,
            },
        ),
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

    for ctx in active_other_ctxs:
        webrtc_streamer(
            key=id(ctx),
            mode=WebRtcMode.RECVONLY,
            client_settings=ClientSettings(
                rtc_configuration={
                    "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
                },
                media_stream_constraints={
                    "video": True,
                    "audio": True,
                },
            ),
            source_audio_track=ctx.output_audio_track,
            source_video_track=ctx.output_video_track,
            desired_playing_state=ctx.state.playing,
        )


if __name__ == "__main__":
    main()
