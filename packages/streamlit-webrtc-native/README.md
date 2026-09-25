# Native audio companion

This experimental package connects a remote WebRTC peer to Python audio processing through LiveKit's Rust bindings to libwebrtc. The headless native audio source and stream APIs provide packet pacing and NetEq audio reception without requiring a LiveKit server. See the pinned upstream API references in `rust/src/lib.rs` and the bundled notices in `licenses/`.

The current upstream archive statically includes FFmpeg code, even for an audio-only peer. These wheels are for local evaluation; binary redistribution needs a verified source and relinking plan or a build that excludes FFmpeg. CI builds and tests them without publishing wheel artifacts. See [FFmpeg’s redistribution guidance](https://ffmpeg.org/legal.html).

## Build and install

From this directory, install the Rust toolchain specified by `rust-toolchain.toml`, a C++ compiler (Xcode command-line tools on macOS or Clang 21 on Linux), and `uv`. Then run:

```sh
uv sync --locked --no-install-project
uv run --no-sync python scripts/build_wheel.py
uv pip install --no-deps dist/*.whl
uv run --no-sync pytest
```

The build downloads a checksum-verified WebRTC archive and links it into the extension. Installing the resulting wheel requires neither a compiler nor a separate WebRTC runtime download. Platform archive selection is defined in `scripts/build_wheel.py`; CI builds each supported target and exercises the installed wheels with build tools hidden from `PATH`. Linux builders also need `pkg-config`, GLib and JPEG development headers.

To check a wheel across the Python versions exercised by CI:

```sh
uv run --no-sync python scripts/check_wheel.py dist/<wheel-file>.whl
```

## Exchange audio

```python
from streamlit_webrtc_native import AudioPeer


async def echo(offer_sdp):
    async with AudioPeer() as peer:
        answer_sdp = await peer.answer(offer_sdp)
        # Deliver answer_sdp through your application's signaling channel.
        while True:
            await peer.send(await peer.recv())
```

The answer waits for ICE gathering and includes the candidates. Applications can pass ICE server credentials to the constructor and forward later remote candidates with `add_ice_candidate()`. Local candidate streaming is not exposed yet.

Received frames use a continuous delivered-sample clock. Dropped application-queue frames and NetEq concealment cannot be recovered from that clock alone; use RTP statistics when interpreting recordings. A stalled consumer drops the oldest queued receive frames to limit accumulated latency.

`send()` applies backpressure while converting PyAV frames for the native source. To interrupt playback, stop application producers, await `clear_output()`, and then start the next utterance. Clearing invalidates pending sends and waits for the current native capture acknowledgement. Audio already transmitted can still play at the remote peer.

Use the async context manager or call `close()` explicitly. Connection loss ends reception when libwebrtc reports the disconnect. This experimental API handles one incoming and one outgoing audio track; video, arbitrary aiortc tracks, stereo preservation, and utterance finalization are outside its current scope.

## Updating dependencies

After changing the Cargo dependency graph, regenerate its bundled notices from this directory:

```sh
cargo install --locked cargo-about --version 0.9.2 --features cli
cargo about generate --locked --fail --manifest-path rust/Cargo.toml about.hbs --output-file licenses/RUST-DEPENDENCIES.md
```

The license policy in `about.toml` covers Rust dependencies. The prebuilt WebRTC archive and the additional `webrtc-sys` notice are tracked separately; regenerating Rust notices does not resolve the FFmpeg redistribution requirement.
