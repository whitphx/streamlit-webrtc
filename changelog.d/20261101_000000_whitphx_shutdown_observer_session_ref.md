## Fixed

- Sessions that used `webrtc_streamer()` or the `create_*_track()` factories are released after they disconnect. The shutdown observer's polling thread kept a strong reference to its `AppSession`, and Streamlit discards a disconnected session whose reconnect window lapses without shutting it down, so each such session stayed in memory with its session state, its tracks and whatever their callbacks referenced, and its polling thread kept running.
