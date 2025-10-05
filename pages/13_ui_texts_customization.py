import streamlit as st
from streamlit_webrtc import webrtc_streamer

# Page title and introduction
st.title("UI Text Customization")
st.markdown("""
Customize the **user interface text and labels** in the WebRTC streamer component. 
This demo shows how to internationalize or customize button labels and messages.

**Features:**
- Custom button text (Start/Stop)
- Customizable status messages
- Internationalization support
- UI text localization

**Instructions:** See how the WebRTC component uses custom text labels below!
""")

st.markdown("---")

webrtc_streamer(
    key="custom_ui_texts",
    translations={
        "start": "開始",
        "stop": "停止",
        "select_device": "デバイス選択",
        "media_api_not_available": "Media APIが利用できない環境です",
        "device_ask_permission": "メディアデバイスへのアクセスを許可してください",
        "device_not_available": "メディアデバイスを利用できません",
        "device_access_denied": "メディアデバイスへのアクセスが拒否されました",
    },
)
