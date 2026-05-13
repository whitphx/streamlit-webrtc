# 03 — Fix `_added_ice_candidate_ids` class-level mutable

## Goal

Fix a latent correctness bug: `WebRtcWorker._added_ice_candidate_ids` is declared as a class attribute, so it is shared across every `WebRtcWorker` instance in the process. ICE candidate IDs from one session can suppress add attempts in a re-created session, including across different users on a multi-tenant deployment.

## Current code

**File**: `streamlit_webrtc/webrtc.py:627`

```python
class WebRtcWorker(Generic[VideoProcessorT, AudioProcessorT]):
    ...
    _added_ice_candidate_ids: Set[str] = set()   # ← class-level shared mutable

    def set_ice_candidates_from_offerer(self, candidates: Dict[str, Dict]):
        ...
        for candidate_id, candidate_dict in candidates.items():
            if candidate_id in self._added_ice_candidate_ids:
                continue
            ...
            self._added_ice_candidate_ids.add(candidate_id)
```

## Fix

Move the initialisation into `__init__`:

```python
def __init__(self, ...):
    ...
    self._added_ice_candidate_ids: Set[str] = set()
```

And delete the class-level declaration on line 627.

## Why this matters

Candidate IDs are produced by the frontend per session, so collisions across sessions are *probably* rare but not impossible — and the failure mode (silently skipping `addIceCandidate`) is hard to diagnose. The fix is one-line and doesn't need explanation in user-facing docs.

## Test to add

Lightweight: instantiate two workers, simulate adding the same candidate ID to both, assert both actually call through. Can be a unit test that doesn't need a real `RTCPeerConnection` — mock `add_ice_candidate` and `candidate_from_sdp`.

Sketch:

```python
def test_each_worker_tracks_its_own_added_candidate_ids(monkeypatch):
    monkeypatch.setattr(
        "streamlit_webrtc.webrtc.candidate_from_sdp",
        lambda sdp: object(),
    )
    w1 = make_worker_without_starting()
    w2 = make_worker_without_starting()
    calls1, calls2 = [], []
    w1.add_ice_candidate = lambda c: calls1.append(c)
    w2.add_ice_candidate = lambda c: calls2.append(c)
    cand = {"id1": {"candidate": "candidate:...", "sdpMid": "0", "sdpMLineIndex": 0}}
    w1.set_ice_candidates_from_offerer(cand)
    w2.set_ice_candidates_from_offerer(cand)
    assert len(calls1) == 1
    assert len(calls2) == 1  # would be 0 with the bug
```

`make_worker_without_starting()` may need a helper that bypasses the `RTCPeerConnection`-touching parts of `__init__`. If that's awkward, ship the fix without the test and pick up coverage in item 05.

## Acceptance criteria

- `_added_ice_candidate_ids` initialised per-instance in `__init__`.
- Class-level attribute deleted.
- Existing tests still pass.
- (Optional) regression test added.

## Risk notes

- Pure bugfix, no API change. No changelog fragment needed unless you want to flag it under `Fixed`.
- Independent of every other item — can ship alone.
