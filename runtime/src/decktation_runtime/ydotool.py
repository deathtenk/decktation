from pathlib import Path

from .config import BIN_DIR


YDOTOOL_SOCKET = "/tmp/decktation-ydotool.sock"


def candidate_paths():
    return [
        BIN_DIR / "ydotool",
        Path("/usr/bin/ydotool"),
        Path("/usr/local/bin/ydotool"),
    ]
