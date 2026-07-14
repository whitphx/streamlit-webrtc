<!--
A new scriv changelog fragment.
-->

### Fixed

- Fixed the Streamlit process stalling on Ctrl-C shutdown while WebRTC streams are (or recently were) active. aiortc's per-receiver decoder threads are non-daemon and exit only when `pc.close()` runs; when Streamlit's event loop teardown won the race against this library's session-shutdown observer, those threads were left blocked forever and prevented interpreter exit. `WebRtcWorker.stop()` now force-stops the decoder threads unconditionally (covering failed close attempts as well as closes interrupted mid-flight, which leave the connection "closed" with live decoder threads), and an interpreter-exit hook covers workers whose `stop()` never ran.
