# 08 — Clean up `WebRtcStreamerContext` and the `@overload` chain

## Goal

`WebRtcStreamerContext` has 11 pass-through properties of the same shape, and `webrtc_streamer()` has four `@overload`s × ~45 args each. Goal: reduce duplication without breaking the public API.

This item is independent of items 04-07. Best landed after item 01 (which removes some kwargs from the overload signatures).

## Part A — `WebRtcStreamerContext` pass-through properties

**File**: `streamlit_webrtc/component.py:127-207`

Every property has the same shape:

```python
@property
def output_audio_track(self) -> Optional[MediaStreamTrack]:
    worker = self._get_worker()
    return worker.output_audio_track if worker else None
```

11 of them: `video_processor`, `audio_processor`, `video_transformer` (deprecated), `video_receiver`, `audio_receiver`, `source_video_track`, `source_audio_track`, `input_video_track`, `input_audio_track`, `output_video_track`, `output_audio_track`.

### Option A1 — small descriptor (recommended)

```python
class _WorkerForwarded:
    def __init__(self, attr): self._attr = attr
    def __set_name__(self, owner, name): self._attr = self._attr or name
    def __get__(self, instance, owner=None):
        if instance is None: return self
        worker = instance._get_worker()
        return getattr(worker, self._attr) if worker else None

class WebRtcStreamerContext(Generic[VideoProcessorT, AudioProcessorT]):
    video_processor: Optional[Union[VideoProcessorT, CallbackAttachableProcessor]] = _WorkerForwarded("video_processor")
    audio_processor: Optional[Union[AudioProcessorT, CallbackAttachableProcessor]] = _WorkerForwarded("audio_processor")
    video_receiver: Optional[VideoReceiver] = _WorkerForwarded("video_receiver")
    # ...
```

Pros: 11 lines instead of ~80. Cons: harder to discover for users via IDE jump-to-definition.

### Option A2 — leave as-is

The properties are tedious but readable. If the goal is "less code, more clarity," option A1 wins. If it's "easier for users to navigate," leave them.

### Option A3 — expose `context.worker` directly

Drop the per-attribute forwarding entirely; tell users to go through `ctx.worker.video_processor` etc. This is *clearer about the lifecycle* (the worker can be `None`) and removes all 11 properties.

Public-API change. Would require a deprecation period: keep the existing properties for one release marked deprecated, add `.worker` property in parallel, remove next major release.

### Recommendation

A1 if you're not ready to break API; A3 if you're willing to do a deprecation cycle. Avoid option A2.

## Part B — `@overload` consolidation

**File**: `streamlit_webrtc/component.py:242-403`

Four overloads, each with ~45 nearly-identical kwargs. The only difference between them is whether `video_processor_factory` and `audio_processor_factory` are typed as `None` or `Optional[...Factory[T]]`. The duplication makes every signature change a five-place edit.

### Option B1 — `TypedDict` + `Unpack` (Python 3.11+)

Define a shared kwargs `TypedDict`, then have each overload extend it with the differing field. Reduces each overload's signature to a few lines.

Requires Python ≥ 3.11 floor. Project currently supports 3.10 (until Oct 2026), so this can't ship until then, *unless* you're OK with `typing_extensions.Unpack`.

### Option B2 — drop overloads entirely

Return type is always `WebRtcStreamerContext[Any, Any]`. Loses the typed narrowing in user code: someone who passes `video_processor_factory=MyVideoProcessor` won't get `ctx.video_processor` typed as `MyVideoProcessor`.

Cost depends on how many users actually rely on this. Likely few. Big win in readability.

### Option B3 — leave as-is

If you change kwargs rarely (which appears to be true — the signature has been stable for a while), the maintenance cost is real but bounded.

### Recommendation

B2 is the largest reduction. B1 is the principled answer but blocked on the Python 3.11 floor. B3 is fine if you don't want to engage with the API question now.

## Part C — Small cleanups in the same area

- `streamlit_webrtc/component.py:212` — the random salt string `r':frontend 6)r])0Gea7e#2E#{y^i*_UzwU"@RJP<z'` works but is alarming. Change to a calm sentinel like `":__webrtc_frontend__"` — under your control on both sides, collisions impossible. Or leave it and add a one-line comment explaining the salt.
- `streamlit_webrtc/component.py:485` — the `type(context).__name__ != WebRtcStreamerContext.__name__` trick is real (Streamlit hot-reload changes class identity). Add a one-sentence comment so future readers don't try to "fix" it back to `isinstance`.
- `streamlit_webrtc/component.py:158-167` — `video_transformer` property is deprecated since v0.20. Removable, with a changelog entry under `Removed`. Bundle with item 02's deprecation cleanup if shipping in the same release.

## Acceptance criteria

- Decide A1 vs A3 (or A2 + documented rationale) and apply.
- Decide B1 vs B2 vs B3 (or B3 + documented rationale) and apply.
- Salt/sentinel comment landed.
- Hot-reload trick has a one-line explanatory comment.
- `uv run pytest` and `pre-commit` green.
- No mypy regression in `uv run mypy .`.

## Risk notes

- A3 and B2 are public-API changes — they need a changelog fragment and arguably a deprecation cycle.
- A1 and B1 are pure refactors — no user-visible change.
- The `__name__` check in `compile_state`-adjacent code looks like a smell but is actually correct; don't "fix" it without understanding Streamlit's script-rerun semantics.
