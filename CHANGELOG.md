# Changelog
All notable changes to this project will be documented in this file.

## [0.6.3] - 2021-02-03
### Fix
- Set `aiortc` version to exactly `1.0.0`, as `1.1.0` and `1.1.1` cause an error. See https://github.com/whitphx/streamlit-webrtc/issues/37.

## [0.6.2] - 2021-02-01
### Fix
- Fix webrtc_worker thread not to block the main thread when an error occurs inside it.

## [0.6.1] - 2021-01-27
### Fix
- Update dependencies.

## [0.6.0] - 2021-01-21
### Added
- Recording input/output streams.
- Error messages in case `navigator.mediaDevices` or `getUserMedia` is not available.
- The object detection demo is updated to display the detected labels.

## [0.5.0] - 2021-01-18
### Added
- Error indication
