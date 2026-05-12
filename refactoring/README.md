# Refactoring plan

Each numbered file is a self-contained unit of work. Order matters: items 1–3 are low-risk preconditions; items 4–5 unlock testability; items 6–8 are the structural cleanup that becomes safe once tests exist.

Pick any one and tell Claude to work on it.

| # | File | Risk | Effort | Depends on |
|---|---|---|---|---|
| 1 | [01-bump-streamlit-minimum.md](./01-bump-streamlit-minimum.md) | Low (mechanical) | M | — |
| 2 | [02-delete-dead-code.md](./02-delete-dead-code.md) | Low | S | — |
| 3 | [03-fix-ice-candidate-mutable-class-attr.md](./03-fix-ice-candidate-mutable-class-attr.md) | Low | XS | — |
| 4 | [04-decouple-worker-from-streamlit-runtime.md](./04-decouple-worker-from-streamlit-runtime.md) | Medium | M | 1 (easier after) |
| 5 | [05-add-pytest-layers.md](./05-add-pytest-layers.md) | Low | M-L | 4 |
| 6 | [06-refactor-process-offer-coro.md](./06-refactor-process-offer-coro.md) | Medium | M | 5 |
| 7 | [07-refactor-webrtc-streamer-function.md](./07-refactor-webrtc-streamer-function.md) | Medium | M | 5 |
| 8 | [08-cleanup-webrtc-streamer-context.md](./08-cleanup-webrtc-streamer-context.md) | Low | S | 1 |

## Cross-cutting principles

- **No public API breakage** unless the doc explicitly says so. `webrtc_streamer()` kwargs, `WebRtcStreamerContext` properties, and the `VideoProcessorBase` / `AudioProcessorBase` contract are part of the contract.
- **Add a changelog fragment** for any user-visible change.
- **Each item should land as its own PR.** Don't fold multiple items together — keeping diffs reviewable is the point.
- **Verify with both `uv run pytest` and `pre-commit run --all-files`** before opening a PR.
