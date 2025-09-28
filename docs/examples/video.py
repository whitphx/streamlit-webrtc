import av
import streamlit as st
from streamlit_webrtc import webrtc_streamer

# Simple video flip control
flip = st.checkbox("Flip")


def video_frame_callback(frame):
    # Convert video frame to numpy array
    img = frame.to_ndarray(format="bgr24")

    # Apply flip transformation if enabled
    img = img[::-1, :, :] if flip else img

    # Create new frame with processed video
    return av.VideoFrame.from_ndarray(img, format="bgr24")


webrtc_streamer(
    key="video",
    video_frame_callback=video_frame_callback,
    media_stream_constraints={"video": True, "audio": False},
)
