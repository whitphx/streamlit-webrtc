# Changelog
All notable changes to this project will be documented in this file.

## [Unreleased]
### Fix
- Fix to use `MediaRelay`, #263.

## [0.22.1] - 2021-06-20
### Fix
- Fix to unset the worker when the state is not playing, #255.

## [0.22.0] - 2021-06-20
### Add
- Make processors effective in RECVONLY mode with a player, #254.

## [0.21.0] - 2021-06-17
### Add
- Support setting a complex `MediaStreamConstraints` object through `ClientSettings.media_stream_constraints`, #243.

## [0.20.1] - 2021-05-19
### Fix
- Fix to unset the answer SDP after a WebRTC session closed, #206.
- Fix `SessionState` to have a unique ID of this specific library to avoid conflicts with other SessionState instances, #210.

## [0.20.0] - 2021-05-09
### BREAKING CHANGES
- `VideoTransformer` is deprecated. Use `VideoProcessor` instead. Related method names has also been changed. `VideoTransformer` API will be maintained for some releases, but be removed in the future.

### Add
- Experimental audio support with `audio_processor` and `audio_receiver` of `webrtc_streamer()`.

## [0.12.0] - 2021-05-02
### Added
- Type annotations around `VideoTransformer` with generics, which enable type inference, for example, on `ctx.video_transformer`, #163.

### Fixed
- Hide unused media type from the device selector, #164.

## [0.11.0] - 2021-04-20
### Fixed
- Only necessary media elements are displayed, for example, in case of video streaming, only a video element is shown and an audio element is hidden, #146.
- Hide the "Select device" button when the mode is RECVONLY, #149.

## [0.10.0] - 2021-04-17
### Add
- Theming, #140.

## [0.9.0] - 2021-04-17
### Fix
- Fix SessionState to be bound to each session properly, #139

## [0.8.1] - 2021-04-11
### Fix
- Internal fix, #126.
- Set log level to `fsevents` logger, whose logs have been noisy, #129.

## [0.8.0] - 2021-04-09
### Fix
- Fix a sample app, `app.py` to avoid an infinate loop.
- Update to unset a worker attributes from a context object after stopping.
- Dependency updates.

## [0.7.2] - 2021-02-24
### Fix
- Dependency updates.

## [0.7.1] - 2021-02-16
### Fix
- Dependency updates.

## [0.7.0] - 2021-02-14
### Fix
- Add `VideoReceiver.get_frame()` and remove `VideoReceiver.frames_queue` attribute.

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
