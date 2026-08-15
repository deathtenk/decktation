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
