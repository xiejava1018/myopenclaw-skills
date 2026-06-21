"""draw.io CLI wrapper: availability check + headless export."""
import re
import shutil
import subprocess

DRAWIO_CMD = "drawio"
INSTALL_HINT = (
    "draw.io cli not found. install: brew install --cask drawio  "
    "(macos), or download from https://github.com/jgraph/drawio-desktop/releases"
)


def drawio_available() -> bool:
    return shutil.which(DRAWIO_CMD) is not None


def drawio_version() -> str | None:
    if not drawio_available():
        return None
    try:
        out = subprocess.run(
            [DRAWIO_CMD, "--version"], capture_output=True, text=True, timeout=30
        )
        m = re.search(r"(\d+\.\d+\.\d+)", out.stdout)
        return m.group(1) if m else None
    except (subprocess.SubprocessError, OSError):
        return None


def check_status() -> dict:
    available = drawio_available()
    return {
        "available": available,
        "version": drawio_version() if available else None,
        # Always carry install guidance; callers surface it only when needed.
        "install_hint": INSTALL_HINT,
    }


class ExportError(Exception):
    pass


def export_image(drawio_path: str, out_path: str, fmt: str = "png",
                 scale: int = 2, border: int = 20) -> None:
    if not drawio_available():
        raise ExportError(INSTALL_HINT)
    cmd = [
        DRAWIO_CMD, "-x", "-f", fmt, "-o", out_path, drawio_path,
        "--scale", str(scale), "--border", str(border),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        raise ExportError(
            f"drawio export failed (exit {result.returncode}): {result.stderr.strip()}"
        )
