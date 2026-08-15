from pathlib import Path

from .config import helper_binary_path


YDOTOOL_SOCKET = "/tmp/decktation-ydotool.sock"


def candidate_paths():
    return [
        helper_binary_path("ydotool"),
        Path("/usr/bin/ydotool"),
        Path("/usr/local/bin/ydotool"),
    ]
