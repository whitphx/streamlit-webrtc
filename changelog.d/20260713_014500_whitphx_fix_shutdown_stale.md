<!--
A new scriv changelog fragment.
-->

### Fixed

- Fixed the Streamlit process stalling on Ctrl-C shutdown while WebRTC streams are (or recently were) active. Two independent causes were addressed:
  - aiortc's per-receiver decoder threads are non-daemon and exit only when `pc.close()` runs; when Streamlit's event loop teardown won the race against this library's session-shutdown observer, those threads were left blocked forever and prevented interpreter exit. `WebRtcWorker.stop()` now force-stops the decoder threads unconditionally (covering failed close attempts as well as closes interrupted mid-flight, which leave the connection "closed" with live decoder threads), and an interpreter-exit hook covers workers whose `stop()` never ran.
  - The object-detection demo's label loop blocked the (non-daemon) script thread on `result_queue.get()` without a timeout, which also prevented interpreter exit. The demo now polls with a timeout, bounds the loop on `ctx.state.playing`, and makes a Streamlit call on every iteration so pending stop/rerun requests are honored. Apps that copied this loop pattern should apply the same change.
