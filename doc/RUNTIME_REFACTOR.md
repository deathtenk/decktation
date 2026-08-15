# Runtime Refactor Plan

This document defines the target architecture for the backend split and tracks
the migration work that has landed so far.

## Goals

- Preserve the current Decky/frontend API while refactoring the backend.
- Move runtime-owned code into a dedicated Python package under `runtime/src/`.
- Keep `main.py` as the long-term Decky bridge entrypoint.
- Move the live plugin over to a runtime process boundary while preserving the
  current frontend API.

## Current ownership

Before the refactor, `main.py` did three jobs:

1. Decky plugin lifecycle and RPC surface.
2. Runtime bootstrap and dependency-path mutation.
3. Runtime orchestration for controller monitoring, transcription, and
   `ydotoold`.

That coupling has now been split incrementally across the migration steps
below.

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
- `main.py` remained untouched in this pass so plugin behavior was preserved.

## Method inventory

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

PR 1 did not change method behavior. It only created the package and design
foundation needed for later protocol work.

## PR 2 protocol shape

PR 2 introduces a source-runnable line-delimited JSON protocol over
stdin/stdout.

Requests:

```json
{"id":"req-1","method":"initialize","params":{"config_dir":"/tmp/decktation"}}
```

Success responses:

```json
{"id":"req-1","ok":true,"result":{"initialized":true,"protocol_version":1}}
```

Error responses:

```json
{"id":"req-1","ok":false,"error":{"code":"unknown_method","message":"Unknown method: foo"}}
```

Async events:

```json
{"event":"log","payload":{"message":"runtime server started","protocol_version":1}}
```

The initial server supports only:

- `handshake`
- `initialize`
- `get_status`
- `shutdown`

This kept PR 2 limited to protocol validation and server framing. Runtime
ownership had not moved out of `main.py` yet.

## PR 3 request/response surface

PR 3 completes the planned request/response method surface so the host-side
bridge can proxy the same API currently exposed by `main.py`.

Implemented request methods:

- `handshake`
- `initialize`
- `get_status`
- `shutdown`
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
- `load_model`
- `get_last_transcription`

PR 3 still did not move controller monitoring or `ydotoold` ownership into the
runtime. Those lifecycle responsibilities remained scheduled for PR 4.

## PR 4 runtime ownership and bridge conversion

PR 4 completed the remaining runtime-owned lifecycle work and switched
`main.py` over to the runtime bridge.

Changes landed in this phase:

- `RuntimeBackend` now owns:
  - controller-monitor process startup/shutdown
  - controller button-state polling
  - `ydotoold` startup/shutdown
  - bundled PortAudio configuration for runtime audio dependencies
- `decktation_runtime.server` supports `--controller-monitor` so the runtime
  entrypoint can launch the controller helper process directly.
- `runtime_client.py` was added as the host-side subprocess client for the
  runtime.
- `main.py` now:
  - starts the runtime process
  - sends `initialize`
  - proxies Decky RPC calls over the JSON runtime protocol
  - consumes runtime events for logging/diagnostics
  - stops the runtime on unload/uninstall

At this point, the intended architecture is live in source form:

- `main.py`
  - Decky lifecycle
  - Decky RPC methods
  - runtime subprocess supervision
  - JSON request/response bridging
- `runtime/src/decktation_runtime/`
  - controller monitoring ownership
  - audio/transcription ownership
  - `ydotoold` lifecycle ownership
  - runtime status/events

## Current status

The runtime split is functionally in place in source form.

Completed:

- source layout refactor into `runtime/src/decktation_runtime/`
- JSON runtime protocol and source-runnable server
- full request/response runtime API surface matching current Decky methods
- runtime ownership of controller monitoring and `ydotoold`
- `main.py` bridge conversion through `RuntimeClient`

Remaining major work:

- define runtime dependencies in `pyproject.toml`
- generate and commit `uv.lock`
- package the runtime as a Docker-built executable in `bin/`
- update the install flow to copy the packaged runtime instead of installing
  loose Python dependencies
