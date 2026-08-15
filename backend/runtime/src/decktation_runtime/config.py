import sys
from pathlib import Path


def find_project_root(start=None):
    """Locate the plugin/project root from a runtime package module."""
    current = Path(start or __file__).resolve()
    for candidate in (current.parent, *current.parents):
        if (candidate / "plugin.json").exists() or (candidate / "defaults").exists():
            return candidate
    return current.parents[0]


PROJECT_ROOT = find_project_root()
DEFAULTS_DIR = PROJECT_ROOT / "defaults"
BIN_DIR = PROJECT_ROOT / "bin"


def is_frozen_bundle():
    return bool(getattr(sys, "_MEIPASS", None))


def bundled_root():
    if is_frozen_bundle():
        return Path(sys._MEIPASS)
    return PROJECT_ROOT


def helper_binary_path(name: str) -> Path:
    bundle_candidate = bundled_root() / "bin" / name
    if bundle_candidate.exists():
        return bundle_candidate
    return BIN_DIR / name


def bundled_library_path(*parts: str) -> Path:
    bundle_candidate = bundled_root().joinpath(*parts)
    if bundle_candidate.exists():
        return bundle_candidate
    return PROJECT_ROOT.joinpath(*parts)
