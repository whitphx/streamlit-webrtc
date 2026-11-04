## Changed

- The "Cleanup on Stop" docs no longer suggest removing `st.session_state` entries in `on_video_ended` / `on_audio_ended`, which run without a script run context and so never reach the session's state. The example closes over the resource instead, and the docs say these callbacks run on the event loop that serves every session, so blocking work belongs in a thread. They also note that a page closed before its connection is set up may not trigger these callbacks until Streamlit discards the session.
