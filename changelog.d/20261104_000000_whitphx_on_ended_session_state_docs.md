## Chore

- The "Cleanup on Stop" docs no longer show `st.session_state.pop()` inside `on_video_ended`, which runs without a script run context and so never reaches the session's state. The example now closes over the resource, and the docs say that the session-end callbacks run on the event loop that serves every session, so blocking work belongs in a thread.
