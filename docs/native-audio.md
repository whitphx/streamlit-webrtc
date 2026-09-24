# Native audio backend

The experimental native backend connects audio callbacks to libwebrtc using the separately installed `streamlit-webrtc-native` companion. Build and install a wheel following the [companion instructions](https://github.com/whitphx/streamlit-webrtc/tree/main/packages/streamlit-webrtc-native#build-and-install), then select the backend:

```python
from streamlit_webrtc import webrtc_streamer

context = webrtc_streamer(
    key="native-audio",
    backend="native",
    audio_frame_callback=lambda frame: frame,
)
```

Audio callbacks run serially. A slow callback can cause older received frames to be dropped to limit latency. Stopping closes the transport while an already executing Python callback finishes; `on_audio_ended` runs afterward. Replacing or removing the callback on a Streamlit rerun takes effect during the active session.

For playback interruption, call `context.clear_audio_output()` from the Streamlit script or an asynchronous processing callback thread. It discards queued native output and the result of an in-flight callback, but cannot retract audio already sent to the browser. A callback running directly on the WebRTC event loop cannot call this blocking method.

Use the aiortc backend for video, modes other than `SENDRECV`, queued callbacks, processor factories, and source, sink, or recorder adapters. The native backend rejects these configurations before negotiation. Context track and receiver attributes are unavailable with this backend. Stop the stream before changing its backend, or use a different component key.

The native answer still waits for ICE gathering. Server-side Trickle ICE is separate work.
