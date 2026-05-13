# 06 — Refactor `_process_offer_coro` in `webrtc.py`

## Goal

`_process_offer_coro` is currently 225 lines (`streamlit_webrtc/webrtc.py:92-317`) made up of three large `if mode == ...` branches with substantial duplication. Goal: cut it to roughly 100 lines by extracting two helpers and unifying the per-track logic.

**Do this only after item 05 lands** — without the loopback tests, a behavior-preserving refactor is much harder to verify.

## What's duplicated

Looking across SENDRECV / SENDONLY / RECVONLY:

1. **"Given an input track or a source track and an optional processor, build the output track."** This shape appears five times:
   - SENDRECV audio (with `source_audio_track` or `audio_processor`)
   - SENDRECV video (with `source_video_track` or `video_processor`)
   - SENDONLY audio (only `audio_processor` path)
   - SENDONLY video (only `video_processor` path)
   - RECVONLY for both kinds (only `source_*_track` path)

2. **"Wire a track to a recorder via the relay."** Appears 4 times: `in_recorder` for SENDRECV input, `out_recorder` for SENDRECV output, `in_recorder` for SENDONLY input. Each call is `recorder.addTrack(relay.subscribe(track))`.

3. **The `on_track_created` dispatcher**. Same `if track.kind == "video" ... elif "audio"` shape repeated for input and output sides.

## Proposed extractions

### Helper 1: `_build_output_track`

```python
def _build_output_track(
    *,
    kind: Literal["video", "audio"],
    input_track: Optional[MediaStreamTrack],
    source_track: Optional[MediaStreamTrack],
    processor: Optional[ProcessorBase],
    async_processing: bool,
    relay: MediaRelay,
) -> Optional[MediaStreamTrack]:
    """Return the track that should be sent back / handed to the receiver / recorded.

    Precedence: source_track > processor-wrapped input > raw input > None.
    Raises if neither input_track nor source_track is provided when a processor exists.
    """
```

This single function replaces the inner `if input_track.kind == "audio" / "video"` ladders in `on_track` and the per-transceiver loop in RECVONLY.

### Helper 2: `_notify_track_created`

Trivial — wraps the four-branch dispatcher into one call:

```python
def _notify_track_created(
    callback: Callable[[TrackType, MediaStreamTrack], None],
    role: Literal["input", "output"],
    track: MediaStreamTrack,
) -> None:
    if track.kind == "video":
        callback(f"{role}:video", track)
    elif track.kind == "audio":
        callback(f"{role}:audio", track)
```

### Mode-specific orchestrators (kept inline or pulled out)

After extraction, each mode branch becomes a clear sequence:

```python
if mode == WebRtcMode.SENDRECV:
    @pc.listens_to("track")
    def on_track(input_track):
        _notify_track_created(on_track_created, "input", input_track)
        output_track = _build_output_track(
            kind=input_track.kind,
            input_track=input_track,
            source_track=source_audio_track if input_track.kind == "audio" else source_video_track,
            processor=audio_processor if input_track.kind == "audio" else video_processor,
            async_processing=async_processing,
            relay=relay,
        )
        if _should_sendback(output_track.kind, sendback_video, sendback_audio):
            pc.addTrack(relay.subscribe(output_track))
        if out_recorder:
            out_recorder.addTrack(relay.subscribe(output_track))
        if in_recorder:
            in_recorder.addTrack(relay.subscribe(input_track))
        _notify_track_created(on_track_created, "output", output_track)
        # ...ended handler unchanged
```

That on_track callback shrinks from ~75 lines to ~15.

## Other tidy-ups in the same PR (optional)

- **Collapse `update_video_callbacks` and `update_audio_callbacks`** (lines 666-714) into one `_update_callbacks(kind, ...)` and two thin public wrappers. Both methods are character-identical apart from attribute names.
- **Split `_unset_processors`** (lines 716-752) into `_stop_receivers`, `_stop_source_tracks`, `_stop_player`, called in order from `stop()`. Makes the ICE-state-change handler's call easier to follow.

## What to *not* change

- The order of operations inside `on_track` matters for aiortc — keep the original sequence: input notification → output build → addTrack → recorders → output notification → ended handler.
- The `RECVONLY` branch uses `pc.getTransceivers()` after `setRemoteDescription` — that timing is load-bearing. Don't move it earlier.
- `remote_description_set_event.set()` placement is load-bearing for `add_ice_candidate`.

## Verification

- Every test from item 05 must pass unchanged.
- Run the example apps (`home.py`, `pages/*.py`) locally to sanity-check across all three modes. UI-level smoke testing is required because frame flow is hard to assert in unit tests for visual correctness.

## Acceptance criteria

- `_process_offer_coro` reduced to ≤120 lines.
- `_build_output_track` and `_notify_track_created` extracted with clear docstrings.
- No behavior change observable in pytest layer 3 or in manual smoke testing.
- `uv run pytest` green; `pre-commit run --all-files` green.

## Risk notes

- Medium-risk. The refactor preserves order-of-operations that aiortc depends on; getting this wrong produces silent failures (frames don't flow, no exception raised).
- Strongly prefer landing this *after* item 05 so the loopback test suite catches regressions.
