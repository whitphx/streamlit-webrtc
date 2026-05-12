# 05 — Add pytest layers for real WebRTC behavior

## Goal

Replace the `_test()` block (deleted in item 02) with a proper test pyramid. The principle: make tests as small as the layer being tested, all the way down to one-frame-through-one-track. The aiortc loopback pattern lets us validate signaling and frame flow without a network.

This work depends on [04-decouple-worker-from-streamlit-runtime.md](./04-decouple-worker-from-streamlit-runtime.md) being done first.

## The four layers

### Layer 1 — Pure functions, no asyncio

Plain pytest. One module per cluster.

| Module under test | What to assert |
|---|---|
| `models.CallbackAttachableProcessor` | `recv`, `recv_queued`, `on_ended` call the registered callbacks; `update_callbacks` is thread-safe under the lock; no callback means passthrough |
| `component.compile_state` | `playing`/`signalling` derived correctly from various component-value shapes |
| `config.compile_rtc_configuration`, `compile_ice_servers`, `compile_rtc_ice_server` | Valid shapes pass; missing `urls` raises; `None` username/credential survive |
| `component.generate_frontend_component_key` | Idempotent; collision-resistant for the obvious inputs |
| `webrtc.WebRtcWorker.set_ice_candidates_from_offerer` (parsing only) | Skips duplicates; tolerates invalid SDP; preserves `sdpMid`/`sdpMLineIndex` |

### Layer 2 — Track unit tests with stub MediaStreamTrack

Same pattern as the existing `tests/source_test.py` (which uses `asyncio.run`). Build a `StubVideoTrack` / `StubAudioTrack` that yields a fixed sequence of frames, hand it to the class under test, drive `recv()` via `asyncio.run`.

| Class under test | What to assert |
|---|---|
| `process.VideoProcessTrack` / `AudioProcessTrack` (sync) | One-in-one-out; processor exception propagates; `pts`/`time_base` preserved |
| `process.AsyncVideoProcessTrack` / `AsyncAudioProcessTrack` | Drops intermediate frames under load (the key invariant of the async path); worker exception surfaces on next `recv()`; `on_ended` fires on stop |
| `mix.MediaStreamMixTrack` | Mixer callback receives N inputs; output cadence ≈ `mixer_output_interval`; adding/removing input tracks updates the mix |
| `source.VideoSourceTrack` | pts/time_base correct at video clock rate; warns when callback is too slow (existing audio test covers the audio case) |

### Layer 3 — Loopback integration (the unlock)

This is what `_test()` was reaching for. With item 04 done, the test looks like:

```python
import asyncio
from aiortc import RTCPeerConnection
from aiortc.contrib.media import MediaRelay
from streamlit_webrtc.webrtc import WebRtcWorker, WebRtcMode
from streamlit_webrtc.source import VideoSourceTrack

class _NoopShutdownObserver:
    def stop(self, timeout=1.0): pass

def _noop_observer_factory(_cb):
    return _NoopShutdownObserver()

async def test_worker_processes_frames_in_sendonly_mode(make_video_frame):
    loop = asyncio.get_running_loop()
    relay = MediaRelay()

    client = RTCPeerConnection()
    client.addTrack(VideoSourceTrack(make_video_frame, fps=10))
    offer = await client.createOffer()
    await client.setLocalDescription(offer)

    received: list = []
    def cb(frame):
        received.append(frame)
        return frame

    worker = WebRtcWorker(
        mode=WebRtcMode.SENDONLY,
        rtc_configuration=None,
        ...,
        video_frame_callback=cb,
        loop=loop,
        relay=relay,
        session_shutdown_observer_factory=_noop_observer_factory,
    )
    answer = worker.process_offer(client.localDescription.sdp, client.localDescription.type, timeout=5)
    await client.setRemoteDescription(answer)

    # Pump frames for a few seconds
    deadline = loop.time() + 5
    while loop.time() < deadline and len(received) < 3:
        await asyncio.sleep(0.1)
    assert len(received) >= 3

    worker.stop()
    await client.close()
```

Cases to cover, one test per case:

| Case | Mode | What to assert |
|---|---|---|
| Passthrough video | SENDRECV | Client receives back the same frames it sent (modulo timing) |
| Processor mutates video | SENDRECV | Client receives the processed frames |
| Receive-only with source track | RECVONLY | Worker pushes frames from `source_video_track` to client |
| Audio frame callback | SENDONLY | Audio callback observes frames at the configured ptime |
| `process_offer` timeout | SENDRECV | `SignallingTimeoutError` raised when the SDP exchange stalls (force by injecting a broken offer) |
| ICE candidate trickle | SENDRECV | Candidates added before vs after `setRemoteDescription` both work |
| `update_video_callbacks` mid-flight | SENDRECV | Callback hot-swap takes effect on next frame |

### Layer 4 — Streamlit-level smoke (low priority)

Streamlit's `AppTest` (≥1.24) renders a script and inspects state. Not for frame-level behavior — for the orchestration logic in `webrtc_streamer()` after the split in item 07. Defer until item 07 lands.

## File layout

```
tests/
  conftest.py               # existing — keep
  import_test.py            # existing — keep
  session_info_test.py      # existing — keep (touched by item 01)
  source_test.py            # existing — keep
  config_test.py            # NEW — layer 1
  models_test.py            # NEW — layer 1 (CallbackAttachableProcessor)
  component_pure_test.py    # NEW — layer 1 (compile_state, generate_frontend_component_key)
  process_test.py           # NEW — layer 2
  mix_test.py               # NEW — layer 2
  webrtc_loopback_test.py   # NEW — layer 3
```

## Acceptance criteria

- All four layers exist as separate files (except layer 4, which is optional in this item).
- `uv run pytest` green on Python 3.10–3.14 in CI.
- Each new test file runs in <10 seconds in CI (layer 3 may need careful timeouts).
- The deleted `_test()` block has no resurrection point.

## Risk notes

- Layer 3 is async-heavy and aiortc-loopback is timing-sensitive. Use `pytest-asyncio` (already implicit via `asyncio.run`) and generous timeouts (5s). If tests turn flaky in CI, prefer increasing timeout over disabling.
- Layer 3 may need `pytest-asyncio` as a dev-dep. Confirm whether the project already has it; if not, add it under `[dependency-groups].dev`.
- Don't try to test against multiple Streamlit versions in layer 3 — the worker is decoupled from Streamlit by item 04.

## Estimated impact

~600-800 lines of new test code. Real coverage of the previously-untested core.
