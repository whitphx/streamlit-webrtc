from streamlit_webrtc import webrtc_streamer

# webrtc_streamer(
#     key="custom_ui_texts",
#     rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
#     translations={
#         "start": "開始",
#         "stop": "停止",
#         "select_device": "デバイス選択",
#         "media_api_not_available": "Media APIが利用できない環境です",
#         "device_ask_permission": "メディアデバイスへのアクセスを許可してください",
#         "device_not_available": "メディアデバイスを利用できません",
#         "device_access_denied": "メディアデバイスへのアクセスが拒否されました",
#     },
# )

webrtc_streamer(key="key", video_processor_factory=VideoProcessor,
				rtc_configuration=RTCConfiguration(
					{"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
					)
	)
