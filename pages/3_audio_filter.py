import av
import numpy as np
import pydub
import streamlit as st
from streamlit_webrtc import WebRtcMode, webrtc_streamer

from sample_utils.turn import get_ice_servers

gain = st.slider("Gain", -10.0, +20.0, 1.0, 0.05)


def process_audio(frame: av.AudioFrame) -> av.AudioFrame:
    raw_samples = frame.to_ndarray()
    sound = pydub.AudioSegment(
        data=raw_samples.tobytes(),
        sample_width=frame.format.bytes,
        frame_rate=frame.sample_rate,
        channels=len(frame.layout.channels),
    )

    sound = sound.apply_gain(gain)

    # Ref: https://github.com/jiaaro/pydub/blob/master/API.markdown#audiosegmentget_array_of_samples  # noqa
    channel_sounds = sound.split_to_mono()
    channel_samples = [s.get_array_of_samples() for s in channel_sounds]
    new_samples: np.ndarray = np.array(channel_samples).T
    new_samples = new_samples.reshape(raw_samples.shape)

    new_frame = av.AudioFrame.from_ndarray(new_samples, layout=frame.layout.name)
    new_frame.sample_rate = frame.sample_rate
    return new_frame


webrtc_streamer(
    key="audio-filter",
    mode=WebRtcMode.SENDRECV,
    rtc_configuration={"iceServers": get_ice_servers()},
    audio_frame_callback=process_audio,
    async_processing=True,
)
