import streamlit as st
from streamlit_webrtc import webrtc_streamer, VideoProcessorBase
import av
import cv2
from threading import Thread
import queue
import numpy as np
from pypylon import pylon

# Create a queue to hold frames
frame_queue = queue.Queue(maxsize=1)

# Background thread to continuously grab frames from the Basler camera
def camera_loop():
    try:
        camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
        camera.Open()
        camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
        
        while camera.IsGrabbing():
            grab_result = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)

            if grab_result.GrabSucceeded():
                frame = grab_result.Array  # NumPy array
                if not frame_queue.full():
                    frame_queue.queue.clear()  # Drop old frame if any
                    frame_queue.put(frame)
            grab_result.Release()
    except Exception as e:
        print(f"[Camera Loop Error] {e}")

# Start the camera loop in the background
Thread(target=camera_loop, daemon=True).start()

# Define the WebRTC video processor
class BaslerVideoProcessor(VideoProcessorBase):
    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        try:
            image = frame_queue.get_nowait()
        except queue.Empty:
            return frame  # return original frame if no camera frame available

        # Optional: you can apply OpenCV operations here
        image = cv2.putText(
            image.copy(),
            "From Basler",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )

        return av.VideoFrame.from_ndarray(image, format="bgr24")

# Streamlit UI
st.title("Basler Camera Stream via streamlit-webrtc")

webrtc_streamer(
    key="basler",
    video_processor_factory=BaslerVideoProcessor,
    media_stream_constraints={"video": True, "audio": False},
    async_processing=True,
)
