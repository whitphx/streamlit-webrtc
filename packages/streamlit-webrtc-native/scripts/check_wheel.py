"""Run installed-wheel tests across CPython versions with build tools hidden."""

import argparse
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    for version in ("3.10", "3.11", "3.12", "3.13", "3.14"):
        with tempfile.TemporaryDirectory(prefix="native-wheel-") as directory:
            python = str(Path(directory) / "bin/python")
            subprocess.run(["uv", "venv", "--python", version, directory], check=True)
            subprocess.run(
                [
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    python,
                    "av>=15.1.0",
                    "numpy",
                    "aiortc>=1.14.0",
                    "pytest",
                    "pytest-asyncio",
                ],
                check=True,
            )
            subprocess.run(
                [
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    python,
                    "--no-index",
                    "--no-deps",
                    str(args.wheel.resolve()),
                ],
                check=True,
            )
            env = {
                k: v
                for k, v in os.environ.items()
                if k
                not in {
                    "PYTHONPATH",
                    "LK_CUSTOM_WEBRTC",
                    "DYLD_LIBRARY_PATH",
                    "LD_LIBRARY_PATH",
                }
            }
            env["PATH"] = ""
            subprocess.run(
                [
                    python,
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    str(ROOT / "tests"),
                ],
                cwd=directory,
                env=env,
                check=True,
            )
            print(f"CPython {version}: passed", flush=True)


if __name__ == "__main__":
    main()
