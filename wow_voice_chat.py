from importlib import import_module
import sys

from runtime_bootstrap import ensure_runtime_src_path


ensure_runtime_src_path()
_impl = import_module("decktation_runtime.voice_service")

if __name__ != "__main__":
    sys.modules[__name__] = _impl
else:
    _impl.main()
