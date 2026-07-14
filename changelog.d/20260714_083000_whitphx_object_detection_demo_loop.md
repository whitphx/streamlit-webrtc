<!--
A new scriv changelog fragment.
-->

### Fixed

- Fixed the object-detection demo blocking the script thread on `result_queue.get()` without a timeout, which prevented the Streamlit process from shutting down on Ctrl-C (script threads are non-daemon and are only stopped cooperatively at Streamlit calls). The demo's label loop now polls with a timeout, bounds itself on `ctx.state.playing`, and makes a Streamlit call on every iteration so pending stop/rerun requests are honored. Apps that copied this loop pattern should apply the same change.
