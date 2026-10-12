"""Build against verified upstream artifacts, without downloading at runtime."""

import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAG = "webrtc-89d790b"
ARTIFACTS = {
    ("Darwin", "arm64"): (
        "mac-arm64-release",
        "9f25fea48588deac18d68e120d18b33af7ef10f921f74b7c57f66b642262c348",
    ),
    ("Linux", "x86_64"): (
        "linux-x64-release",
        "b167adad5291cea0e4d66a0454d9d52d2ad714e6b0ed70f4410317d3ebde70c5",
    ),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache")
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    name, digest = ARTIFACTS[(platform.system(), platform.machine())]
    args.cache.mkdir(parents=True, exist_ok=True)
    archive = args.archive or args.cache / f"{TAG}-{name}.zip"
    if not archive.exists():
        # curl supplies TLS verification and retries without another Python dependency.
        subprocess.run(
            [
                "curl",
                "--fail",
                "--location",
                "--retry",
                "3",
                "--output",
                str(archive),
                f"https://github.com/livekit/rust-sdks/releases/download/{TAG}/webrtc-{name}.zip",
            ],
            check=True,
        )
    with archive.open("rb") as f:
        actual = hashlib.sha256()
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            actual.update(chunk)
    if actual.hexdigest() != digest:
        raise RuntimeError(f"Checksum mismatch for {archive}; remove it and retry")
    with tempfile.TemporaryDirectory(dir=args.cache) as directory:
        with zipfile.ZipFile(archive) as z:
            z.extractall(directory)
        native = Path(directory) / name
        # Cargo's downloaded artifact cache is separate from the wheel's installed runtime.
        env = dict(os.environ, LK_CUSTOM_WEBRTC=str(native.resolve()))
        if platform.system() == "Darwin":
            env["MACOSX_DEPLOYMENT_TARGET"] = "13.0"
        license_name = (
            "WEBRTC-mac-LICENSE.md"
            if platform.system() == "Darwin"
            else "WEBRTC-linux-LICENSE.md"
        )
        shutil.copyfile(native / "LICENSE.md", ROOT / "licenses" / license_name)
        subprocess.run(
            [
                "maturin",
                "build",
                "--release",
                "--locked",
                "--manifest-path",
                str(ROOT / "rust/Cargo.toml"),
                "--out",
                str(ROOT / "dist"),
            ],
            env=env,
            cwd=ROOT,
            check=True,
        )


if __name__ == "__main__":
    main()
