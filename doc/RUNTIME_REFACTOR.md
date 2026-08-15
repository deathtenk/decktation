# Runtime Refactor Plan

This document defines the target architecture for the backend split and the
first migration pass landed in PR 1.

## Goals

- Preserve the current Decky/frontend API while refactoring the backend.
- Move runtime-owned code into a dedicated Python package under `runtime/src/`.
- Keep `main.py` as the long-term Decky bridge entrypoint.
- Introduce a future runtime process boundary without switching to it yet.

## Current ownership

Today `main.py` does three jobs:

1. Decky plugin lifecycle and RPC surface.
2. Runtime bootstrap and dependency-path mutation.
3. Runtime orchestration for controller monitoring, transcription, and
   `ydotoold`.

The first pass only changes source layout. It does not change the live
execution model.

## Target ownership

The intended split is:

- `main.py`
  - Decky lifecycle
  - Decky RPC methods
  - runtime subprocess supervision
  - JSON request/response bridging
- `bin/decktation-runtime`
  - controller monitoring
  - audio capture
  - transcription
  - `ydotoold` lifecycle
  - runtime status/events

## Runtime package layout

PR 1 introduces:

```text
runtime/
  pyproject.toml
  src/decktation_runtime/
    __init__.py
    config.py
    controller_monitor.py
    hid.py
    logging_setup.py
    protocol.py
    server.py
    voice_service.py
    ydotool.py
```

## Compatibility strategy in PR 1

- `wow_voice_chat.py`, `controller_listener.py`, and `deck_hid.py` remain at
  the repository root as import-compatible shims.
- Tests and helper scripts can continue importing those legacy module names.
- The actual implementation now lives in `runtime/src/decktation_runtime/`.
- `main.py` remains untouched in this pass so plugin behavior is preserved.

## Method inventory for later bridge work

The future runtime command surface must cover the current Decky-facing methods
implemented in `main.py`:

- `_main`
- `_unload`
- `_uninstall`
- `_migration`
- `set_enabled`
- `get_button_config`
- `set_share_diagnostics`
- `set_button_config`
- `set_confirm_mode`
- `set_manual_send`
- `set_transcription_options`
- `set_model_size`
- `get_presets`
- `get_active_preset`
- `set_active_preset`
- `start_recording`
- `stop_recording`
- `is_recording`
- `update_context`
- `get_status`
- `load_model`
- `get_last_transcription`

PR 1 does not change method behavior. It only creates the package and design
foundation needed for later protocol work.
