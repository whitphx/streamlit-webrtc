## Added

- `webrtc_streamer()` can open WebRTC data channels (`data_channels`, `on_data_channel_message`, `ctx.data_channels`) and run app-supplied JavaScript in the browser (`frontend_script`) that receives the channels, the peer connection, the component's media elements, an element to draw into, and JSON data from Python (`frontend_data`) that it can keep receiving on reruns without restarting the session.
