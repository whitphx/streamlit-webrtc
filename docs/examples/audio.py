import av
import streamlit as st
from streamlit_webrtc import webrtc_streamer

# Simple volume control
volume = st.slider("Volume", 0.0, 2.0, 1.0, 0.1)


def audio_frame_callback(frame: av.AudioFrame) -> av.AudioFrame:
    # Apply volume control to audio samples
    samples = frame.to_ndarray()
    new_samples = (samples * volume).astype(samples.dtype)

    # Create new frame with processed audio
    new_frame = av.AudioFrame.from_ndarray(new_samples, layout=frame.layout.name)
    new_frame.sample_rate = frame.sample_rate
    return new_frame


webrtc_streamer(
    key="audio",
    audio_frame_callback=audio_frame_callback,
    media_stream_constraints={"video": False, "audio": True},
)
