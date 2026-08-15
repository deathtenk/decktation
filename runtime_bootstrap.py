from pathlib import Path
import sys


def ensure_runtime_src_path():
    """Make the in-repo runtime package importable during the migration."""
    runtime_src = Path(__file__).resolve().parent / "runtime" / "src"
    runtime_src_str = str(runtime_src)
    if runtime_src_str not in sys.path:
        sys.path.insert(0, runtime_src_str)
    return runtime_src
