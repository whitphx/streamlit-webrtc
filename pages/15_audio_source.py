import fractions

import av
import numpy as np
import streamlit as st
from streamlit_webrtc import WebRtcMode, create_audio_source_track, webrtc_streamer

st.title("Audio Source Track Demo")
st.write(
    "This demo shows how to programmatically generate audio using AudioSourceTrack."
)

# Audio generation parameters
frequency = st.slider("Frequency (Hz)", 200, 2000, 440, 10)
volume = st.slider("Volume", 0.0, 1.0, 0.5, 0.1)
wave_type = st.selectbox("Wave Type", ["sine", "square", "triangle", "sawtooth"])

# Audio settings
sample_rate = 48000
channels = 1
ptime = 0.020  # 20ms packets
samples_per_frame = int(sample_rate * ptime)


def audio_source_callback(pts: int, time_base: fractions.Fraction) -> av.AudioFrame:
    """Generate audio frames with the selected waveform."""
    pts_sec = pts * time_base

    # Generate time array for this frame
    t_start = float(pts_sec)
    t_end = t_start + ptime
    t = np.linspace(t_start, t_end, samples_per_frame, False)

    # Generate waveform based on selected type
    if wave_type == "sine":
        audio_data = np.sin(2 * np.pi * frequency * t)
    elif wave_type == "square":
        audio_data = np.sign(np.sin(2 * np.pi * frequency * t))
    elif wave_type == "triangle":
        audio_data = 2 * np.arcsin(np.sin(2 * np.pi * frequency * t)) / np.pi
    elif wave_type == "sawtooth":
        audio_data = 2 * (frequency * t - np.floor(frequency * t + 0.5))
    else:
        audio_data = np.sin(2 * np.pi * frequency * t)

    # Apply volume and ensure proper range
    audio_data = audio_data * volume

    # Convert to int16 format
    audio_data = (audio_data * 32767).astype(np.int16)

    # Create audio frame
    frame = av.AudioFrame.from_ndarray(
        audio_data.reshape(1, -1),  # Shape: (channels, samples)
        format="s16",
        layout="mono",
    )
    frame.sample_rate = sample_rate

    return frame


# Create audio source track
audio_source_track = create_audio_source_track(
    audio_source_callback,
    key="audio_source_track",
    sample_rate=sample_rate,
    ptime=ptime,
)


def on_change():
    """Handle state changes."""
    ctx = st.session_state["audio_player"]
    stopped = not ctx.state.playing and not ctx.state.signalling
    if stopped:
        audio_source_track.stop()  # Manually stop the track


st.write("Click 'START' to begin audio generation. You should hear the generated tone.")
st.warning(
    "⚠️ Make sure your speakers/headphones are at a reasonable volume before starting!"
)

# WebRTC streamer in RECVONLY mode to output the generated audio
webrtc_streamer(
    key="audio_player",
    mode=WebRtcMode.RECVONLY,
    source_audio_track=audio_source_track,
    media_stream_constraints={"video": False, "audio": True},
    on_change=on_change,
)

# Display current settings
st.subheader("Current Settings")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Frequency", f"{frequency} Hz")
with col2:
    st.metric("Volume", f"{volume:.1f}")
with col3:
    st.metric("Wave Type", wave_type)

st.subheader("Audio Parameters")
st.write(f"Sample Rate: {sample_rate} Hz")
st.write(f"Packet Time: {ptime * 1000} ms")
st.write(f"Samples per Frame: {samples_per_frame}")
st.write(f"Channels: {channels} (mono)")
