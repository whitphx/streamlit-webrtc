# Changelog
All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.63.0] - 2025-06-21

### Added

- Add `AudioSourceTrack` that allows to send programatically generated audio data from the server side, [#2101](https://github.com/whitphx/streamlit-webrtc/pull/2101).

## [0.62.4] - 2025-04-12

### Fixed

- Refine the message of the "taking too long" warning and set the timeout to 10 seconds display it, [#2034](https://github.com/whitphx/streamlit-webrtc/pull/2034).

## [0.62.3] - 2025-04-12

### Fixed

- Refactoring, [#2033](https://github.com/whitphx/streamlit-webrtc/pull/2033).

## [0.62.2] - 2025-04-12

### Fixed

- Fix a bug that the answer SDP is not sent to the worker, [#2032](https://github.com/whitphx/streamlit-webrtc/pull/2032).

## [0.62.1] - 2025-04-12

### Fixed

- Fix a bug that the answer SDP is not sent to the worker, [#2030](https://github.com/whitphx/streamlit-webrtc/pull/2030).

## [0.62.0] - 2025-04-11

### Changed

- Cache `get_available_ice_servers()`, [#2028](https://github.com/whitphx/streamlit-webrtc/pull/2028).

## [0.61.3] - 2025-04-11

### Fixed

- Fix a bug that the worker can be created multiple times, [#2026](https://github.com/whitphx/streamlit-webrtc/pull/2026).
- Update `aioice` to `>=0.10.0`, which should fix the issue that the entire ICE candidate gathering fails when at least one candidate fails to connect, [#2027](https://github.com/whitphx/streamlit-webrtc/pull/2027).

## [0.61.2] - 2025-04-11

### Fixed

- Fix a bug that the ID of the ICE candidate sent from the frontend to the backend may not be unique, [#2025](https://github.com/whitphx/streamlit-webrtc/pull/2025).

## [0.61.1] - 2025-04-10

### Fixed

- Fix a bug that the stop button is hidden when the "taking too long" warning is shown, [#2022](https://github.com/whitphx/streamlit-webrtc/pull/2022).

## [0.61.0] - 2025-04-09

### Added

- Show a warning message when the connection takes too long, [#2017](https://github.com/whitphx/streamlit-webrtc/pull/2017).

## [0.60.3] - 2025-04-08

### Fixed

- Handle the error raised from `candidate_from_sdp`, [#2016](https://github.com/whitphx/streamlit-webrtc/pull/2016).

## [0.60.2] - 2025-04-08

### Fixed

- Fix the instantiation of `asyncio.Event` in `WebRtcWorker`, [#2012](https://github.com/whitphx/streamlit-webrtc/pull/2012).

## [0.60.1] - 2025-04-08

### Fixed

- Avoid duplicated worker creations, [#2011](https://github.com/whitphx/streamlit-webrtc/pull/2011).

## [0.60.0] - 2025-04-07

### Changed

- Revert the change to use the patched version of `aioice`, [#2009](https://github.com/whitphx/streamlit-webrtc/pull/2009).
- Keep the playing state when the iceConnectionState becomes `disconnected` because the connection can be recovered, [#2008](https://github.com/whitphx/streamlit-webrtc/pull/2008).

### Fixed

- Make `add_ice_candidate()` to wait until the remote description is set, [#2010](https://github.com/whitphx/streamlit-webrtc/pull/2010).

## [0.59.0]: Skipped

### Changed

- Cache the helper functions to retrieve ICE servers info in `credentials` module, [#1999](https://github.com/whitphx/streamlit-webrtc/pull/1999).

## [0.58.0]: Skipped

### Changed

- Use a patched version of `aioice` to address the issue that the entire ICE candidate gathering fails when at least one candidate fails to connect, [#2005](https://github.com/whitphx/streamlit-webrtc/pull/2005).

## [0.57.0] - 2025-04-04

### Changed

- Manage the frontend playing state based on the `onconnectionstatechange` event, [#1998](https://github.com/whitphx/streamlit-webrtc/pull/1998).

## [0.56.0] - 2025-04-02

### Changed

- Set the default ICE servers automatically on frontend as well, [#1946](https://github.com/whitphx/streamlit-webrtc/pull/1946).
- The frontend app sends the offer SDP to the server immediately after creating it and sends the gathered ICE candidates following it asynchronously (Trickle ICE). It's more efficient than the previous approach (Vanilla ICE) that the server waits for the ICE candidates to be gathered and then sends the SDP answer back to the frontend, [#1993](https://github.com/whitphx/streamlit-webrtc/pull/1993).
- `rtc_configuration` is restored as a shorthand to configure both frontend and server, [#1996](https://github.com/whitphx/streamlit-webrtc/pull/1996).

## [0.55.0] - 2025-04-01

### Changed

- Unset the timeout waiting for `process_offer()` to be completed, [#1963](https://github.com/whitphx/streamlit-webrtc/pull/1963).

## [0.54.0] - 2025-04-01

### Changed

- Rename `TimeoutError` to `SignallingTimeoutErorr`, [#1983](https://github.com/whitphx/streamlit-webrtc/pull/1983).

### Fixed

- Fix the shutdown observer to work correctly and the stop method is called just once, [#1980](https://github.com/whitphx/streamlit-webrtc/pull/1980).
- Use `asyncio.run_coroutine_threadsafe()` instead of `loop.create_task()`, [#1982](https://github.com/whitphx/streamlit-webrtc/pull/1982).

## [0.53.11] - 2025-04-01

### Fixed

- Update `aiortc` to 1.11.0, [#1988](https://github.com/whitphx/streamlit-webrtc/pull/1988).
- Refactoring, [#1987](https://github.com/whitphx/streamlit-webrtc/pull/1987).
- Internal dependencies updates.

## [0.53.10] - 2025-03-27

### Fixed

- Call `stop()` on the server when an error occurs during `process_offer(),` [#1977](https://github.com/whitphx/streamlit-webrtc/pull/1977).

## [0.53.9] - 2025-03-26

### Fixed

- Internal dependencies updates.

## [0.53.8] - 2025-03-25

### Fixed

- Internal dependencies updates.

## [0.53.7] - 2025-03-23

### Fixed

- Fix the CI/CD workflow.

## [0.53.6] - 2025-03-23

### Fixed

- Internal package updates.

## [0.53.5] - 2025-03-23

### Fixed

- Fix CI/CD, [#1957](https://github.com/whitphx/streamlit-webrtc/pull/1957), [#1958](https://github.com/whitphx/streamlit-webrtc/pull/1958), [#1959](https://github.com/whitphx/streamlit-webrtc/pull/1959), [#1960](https://github.com/whitphx/streamlit-webrtc/pull/1960).

## [0.53.4]

Skipped

## [0.53.3] - 2025-03-19

### Fixed

- Fix a bug that frontend RTC configuration is not refreshed when the component is stopped, [#1952](https://github.com/whitphx/streamlit-webrtc/pull/1952).

## [0.53.2] - 2025-03-19

### Fixed

- Remove `import importlib_metadata` that is no longer needed since dropping Python 3.8 support, [#1949](https://github.com/whitphx/streamlit-webrtc/pull/1949).

## [0.53.1] - 2025-03-19

### Fixed

- Set the package version dynamically, [#1947](https://github.com/whitphx/streamlit-webrtc/pull/1947).

## [0.53.0] - 2025-03-18

### Changed

- `server_rtc_configuration` option is added to `webrtc_streamer()`, [#1944](https://github.com/whitphx/streamlit-webrtc/pull/1944).
- The `rtc_configuration` option of `webrtc_streamer()` is renamed to `frontend_rtc_configuration` and `rtc_configuration` is marked as deprecated, [#1944](https://github.com/whitphx/streamlit-webrtc/pull/1944).

## [0.52.0] - 2025-03-18

### Changed

- [BREAKING] The `client_settings` option of `webrtc_streamer()` has been removed. Use `rtc_configuration` and `media_stream_constraints` instead, [#1943](https://github.com/whitphx/streamlit-webrtc/pull/1943).
- [BREAKING] The `rtc_configuration` option of `webrtc_streamer()` is used to configure the connection from the server side peer, [#1943](https://github.com/whitphx/streamlit-webrtc/pull/1943).

## [0.51.3] - 2025-03-18

### Fix

- Internal refactoring on the auto-configuring of STUN/TURN servers, [#1942](https://github.com/whitphx/streamlit-webrtc/pull/1942).

## [0.51.2] - 2025-03-18

### Fix

- Fix a bug on `streamlit_webrtc.credentials.get_hf_ice_servers()` that it always returns `None`, [#1939](https://github.com/whitphx/streamlit-webrtc/pull/1939).
- Add type hints on `streamlit_webrtc.credentials.get_hf_ice_servers()` and `streamlit_webrtc.credentials.get_twilio_ice_servers()`, [#1940](https://github.com/whitphx/streamlit-webrtc/pull/1940).

## [0.51.1] - 2025-03-18

### Fix

- Fix internal type annotations, [#1938](https://github.com/whitphx/streamlit-webrtc/pull/1938).

## [0.51.0] - 2025-03-17

### Added

- `streamlit_webrtc.credentials` module for getting TURN/STUN server credentials from Hugging Face and Twilio, [#1927](https://github.com/whitphx/streamlit-webrtc/pull/1927).

### Changed

- Set the STUN/TURN server configs automatically if the credentials are available, [#1927](https://github.com/whitphx/streamlit-webrtc/pull/1927).

## [0.50.1] - 2025-03-17

### Changed

- Update type annotations, [#1936](https://github.com/whitphx/streamlit-webrtc/pull/1936).
- Switch to uv, [#1936](https://github.com/whitphx/streamlit-webrtc/pull/1936).
- Update the release workflow, [#1937](https://github.com/whitphx/streamlit-webrtc/pull/1937).

## [0.49.4] - 2025-03-14

### Fix

- Internally switch the frontend package manager from npm to pnpm, [#1932](https://github.com/whitphx/streamlit-webrtc/pull/1932).

## [0.49.3] - 2025-03-13

### Fix

- Set the base theme type correctly, [#1931](https://github.com/whitphx/streamlit-webrtc/pull/1931).

## [0.49.2] - 2025-03-13

### Fix

- Internal package updates.

## [0.49.1] - 2025-03-13

### Fix

- Internal package updates.

## [0.49.0] - 2025-03-12

### Change

- Drop support for Python 3.8, [#1913](https://github.com/whitphx/streamlit-webrtc/pull/1913).

## [0.48.2] - 2025-03-12

### Fix

- Internal updates of frontend build setup from Webpack to Vite, [#1909](https://github.com/whitphx/streamlit-webrtc/pull/1909).
- Dependencies updates.

## [0.48.1] - 2025-03-12

### Fix

- Bundle frontend files correctly, [#1904](https://github.com/whitphx/streamlit-webrtc/pull/1904).
- Internal package updates.

## [0.48.0] - 2025-03-12 (Yanked)

### Change

- Use the `on_change` handler instead of `components_callbacks.register_callback` for Streamlit 1.36.0 and later, [#1901](https://github.com/whitphx/streamlit-webrtc/pull/1901).

## [0.47.9] - 2024-09-14

### Fix

- Internal package updates.
- Remove `typing_extensions`, [#1798](https://github.com/whitphx/streamlit-webrtc/pull/1798).
- Fix `author` and `description` in `pyproject.toml`, [#1799](https://github.com/whitphx/streamlit-webrtc/pull/1799).

## [0.47.8] - 2024-09-14

### Fix

- Internal package updates.

## [0.47.7] - 2024-05-24

### Fix

- Support Streamlit 1.34.0, #1627.

## [0.47.6] - 2024-03-05

### Fix

- CI/CD pipeline, #1530.

## [0.47.5] - 2024-03-05

Skipped.

## [0.47.4] - 2024-03-05

### Fix

- Internal package updates.

## [0.47.3] - 2024-03-05

### Fix

- Logging information, by @ya0guang, #1507.
- Internal package updates.

## [0.47.2]

Skipped.

## [0.47.1] - 2023-09-26

### Fix

- Compatibility with streamlit>=1.27.0, #1393.

## [0.47.0] - 2023-08-23

### Add

- Frame callbacks for the SENDONLY mode, #1347.

## [0.46.0] - 2023-08-21

### Add

- Programmable video source, #1349.

## [0.45.2] - 2023-08-21

### Fix

- Fix `get_session_info` to use `SessionManager.get_session_info()` instead of `.get_active_session_info()` because the session info sometimes can be inactive when accessed from this library, #1355.
- Warning messages, #1348.
- Internal package updates.

## [0.45.1] - 2023-06-06

### Fix

- Internal package updates.

## [0.45.0] - 2023-03-02

### Change

- Add support for Python 3.11 and drop 3.7, #1195.

## [0.44.7] - 2023-03-01

### Fix

- Introduce custom error classes, #1198.

## [0.44.6] - 2023-02-15

### Fix

- Internal refactoring, #1194.

## [0.44.5] - 2023-02-12

### Fix

- Internal changes for more reliable device selection, #1180.

## [0.44.4] - 2023-02-12

### Fix

- Specify a higher version of `aiortc` dependency to avoid the cryptography problem that was worked around in 0.44.1, #1193.

## [0.44.3] - 2023-02-11

### Fix

- Compatibility with streamlit>=1.18.0, #1189.
- Refactoring on the object detection demo code, #1191.

## [0.44.2] - 2023-01-07

### Fix

- Some security updates.

## [0.44.1] - 2023-01-07

### Fix

- Specify the version of `cryptography` to avoid the bug reported at [#1164](https://github.com/whitphx/streamlit-webrtc/issues/1164), #1167.

## [0.44.0] - 2022-10-17

### Fix

- Use `MediaRelay` at the track connections in the SENDONLY mode, #1089.

## [0.43.4] - 2022-09-03

### Fix
- `poetry-core` version, #1049.

## [0.43.3] - 2022-09-01

### Fix

- Catch `ReferenceError` during searching the server object , #1042.

## [0.43.2] - 2022-08-27

### Fix
- Refactoring, #1033.

## [0.43.1] - 2022-08-26

### Fix
- Compatibility with streamlit>=1.12.1, #1026.

## [0.43.0] - 2022-08-15

### Fix
- Escape-hatch to access the running Streamlit server object for the new web server design with streamlit>=1.12.0, #1005.

## [0.42.0] - 2022-07-02

### Fix
- Callback type definitions, #950.
- Update `create_process_track()` to accept callback functions instead of a class object, #951.

## [0.41.0] - 2022-06-28

### Fix
- `create_mix_track()` has been modified to accept a callback function instead of a class object, #940.

## [0.40.0] - 2022-06-07

### Add
- Class-less callback, #747.

### Fix
- Internal package updates.

## [0.37.0] - 2022-05-04

### Add
- `on_change` callback, #695.
- `translations` option, #733.

## [0.36.1] - 2022-03-25

### Fix
- Rename internal imports to be compatible with streamlit>=1.8.0, #760.

## [0.36.0] - 2022-03-14

### Add
- Export `DEFAULT_*` values, #723.

### Fix
- Deprecated warning messages, #732.

## [0.35.2] - 2022-03-01
### Fix
- Fix an internal attribute access to be compatible with streamlit>=1.6.0, #710.

## [0.35.1] - 2022-02-23
### Fix
- Internal package updates.

## [0.35.0] - 2022-02-13
### Add
- PEP-561 compatibility, #671.

## [0.34.2] - 2022-01-15
### Fix
- Internal package updates.

## [0.34.1] - 2022-01-15
### Fix
- Rename internal imports to be compatible with streamlit>=1.4.0, #598.

## [0.34.0] - 2022-01-14
### Fix
- New device selector, #594.

## [0.33.0] - 2021-12-30
### Fix
- Internal type annotations to be compatible with streamlit>=1.3, #581.
- Set the frontend signalling timeout as 3 sec, #568.
- Drop Python 3.6 support, #527.
- Internal package updates.

## [0.32.0] - 2021-11-28
### Fix
- Stop players when the worker stops, #533.
- Stop the worker when the Streamlit session ends, which makes it possible to terminate the server process by pressing ctrl-c during WebRTC session alive, #535.
- Stop the client-side process when disconnected, #539.

## [0.31.5] - 2021-11-24
### Fix
- Refactoring, #525, #526

## [0.31.4] - 2021-11-24
### Fix
- Refactoring, #520

## [0.31.3] - 2021-11-23
### Fix
- Refactoring, #517.

## [0.31.2] - 2021-11-16
### Fix
- Mark async processor's threads as daemon, #492.

## [0.31.1] - 2021-10-24
### Fix
- Internal package updates.

## [0.31.0] - 2021-10-13
### Add
- Include [`adapter.js`](https://github.com/webrtcHacks/adapter) for WebRTC interoperability, #455.

## [0.30.0] - 2021-10-12
### Add
- Session state compatibility - the context objects became accessible via `st.session_state` and internally, workers and states are all changed to be managed in the session state, #452.
  - [BREAKING CHANGE] Stop supporting `streamlit<0.84.1`.

## [0.29.1] - 2021-09-21
### Fix
- Refactoring, #428 and #429.

## [0.29.0] - 2021-09-21
### Fix
- Fix samples not to use deprecated arguments, #425.
- Fix to use React hooks and function-based components, #424

## [0.28.1] - 2021-09-10
### Fix
- Initialize the component value when the component is mounted, #413.

## [0.28.0] - 2021-09-01
### Add
- `on_ended()` callback, #405.

## [0.27.1] - 2021-08-24
### Fix
- Rename `types` module to `models`, #390.
- Use `loop.create_task()` instead of `asyncio.ensure_future`, #391.

## [0.27.0] - 2021-08-22
### Add
- Add `mixer-output-interval` property to `MediaStreamMixTrack`, #388.

## [0.26.0] - 2021-08-08
### Fix
- Type hints, #366.
- [BREAKING CHANGE] `client_settings` argument is marked as deprecated and `rtc_configuration` and `media_stream_constraints` became the top level arguments, #371.

## [0.25.1] - 2021-07-30
### Fix
- Fix to be compatible with `multiprocessing.Process`, #355.

## [0.25.0] - 2021-07-30
### Add
- Add `video_html_attrs` and `audio_html_attrs` options, #272.

## [0.24.1] - 2021-07-22
### Fix
- Export `WebRtcStreamerContext` and `WebRtcStreamerState` from the package, #342.
- Fix `app_videochat.py`, #342.

## [0.24.0] - 2021-07-16
### Add
- Support forking and mixing streams, #318.

## [0.23.12] - 2021-07-15
### Fix
- Remove `MediaTrackConstraintSet.deviceId` option, which has no effect, #328.

## [0.23.11] - 2021-07-13
### Fix
- Internal fix about event loop management, #323.

## [0.23.10] - 2021-07-10
### Fix
- Fix type annotations on `VideoProcessTrack`, #317.

## [0.23.9] - 2021-07-06
### Fix
- Fix CI error, #307.

## [0.23.8] - 2021-07-06
### Fix
- Internal fix about component value management, #305.
- Internal fix about SDP offer handling, #304.

## [0.23.7] - 2021-07-05
### Fix
- Revert a change in v0.23.3, #301.

## [0.23.6] - 2021-07-05
### Fix
- Fix SessionState, #299.

## [0.23.5] - 2021-07-04
### Fix
- Make the identity of a context object consistent over the session, #298.

## [0.23.4] - 2021-07-03
### Fix
- Internal fix about event loop management, #282.
- Hotfix for marshalling the component value, #290.

## [0.23.3] - 2021-06-30
### Fix
- Fix internal code on signalling, #278.

## [0.23.2] - 2021-06-28
### Fix
- Fix internal state management, #274.

## [0.23.1] - 2021-06-27
### Fix
- Fix to call super methods from the frontend component to adjust iframe height propery, #273.

## [0.23.0] - 2021-06-27
### Add
- Add `desired_playing_state` argument to control the playing state programatically, #266.

## [0.22.3] - 2021-06-26
### Fix
- Fix frontend to handle errors from promises properly, #267.
- Fix to stop `AsyncMediaProcessTrack` when its input track stops, #269.
  - A bug introduced in v0.22.2 (#268) has been fixed.

## [0.22.2] - 2021-06-26
### Fix
- Fix to use `MediaRelay`, #263.
- Fix to use the event loop attached to the Tornado app, #260.
- Add `app_record.py` as an example of `MediaRecorder`, #264.

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
