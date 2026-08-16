"""
Shared pytest fixtures and mocks for Decktation tests.

Heavy dependencies (faster_whisper) are mocked at the module level
so tests can import the runtime voice service without requiring ML/audio
hardware.
"""

import sys
import os
from unittest.mock import MagicMock

# Point tests at the project root and runtime package source tree
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "runtime", "src"))

# Mock heavy deps before runtime modules are imported.
# numpy's C-extensions require the right libstdc++ which may not be present in the
# test venv; mock it since no test here exercises audio processing code.
sys.modules.setdefault("numpy", MagicMock())
sys.modules.setdefault("faster_whisper", MagicMock())
