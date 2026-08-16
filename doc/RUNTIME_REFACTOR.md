# Runtime Architecture

This document describes Decktation's current backend architecture after the
runtime split and packaging work.

## Goals

- Preserve the Decky/frontend API while isolating runtime concerns.
- Keep `main.py` as the Decky backend entrypoint.
- Move controller monitoring, audio capture, transcription, and `ydotoold`
  lifecycle into a dedicated runtime process.
- Build and distribute the runtime as a packaged executable with a locked
  dependency tree.

## Current split

The plugin now runs as two cooperating layers:

- `main.py`
  - Decky lifecycle hooks
  - Decky RPC methods
  - runtime process supervision
  - JSON request/response bridging
  - runtime event logging
- `bin/decktation-runtime`
  - controller monitoring
  - button-state polling
  - audio capture
  - transcription
  - text injection via bundled `ydotool`
  - private `ydotoold` lifecycle
  - runtime status and events

`main.py` is intentionally a bridge, not the place where runtime behavior
should grow.

## Runtime source layout

The runtime source of truth lives under `runtime/src/decktation_runtime/`:

```text
runtime/
  pyproject.toml
  uv.lock
  runtime_entry.py
  decktation-runtime.spec
  src/decktation_runtime/
    __init__.py
    config.py
    controller_monitor.py
    hid.py
    logging_setup.py
    protocol.py
    runtime_backend.py
    server.py
    voice_service.py
    ydotool.py
```

### Module roles

- `config.py`
  path helpers for packaged/runtime layouts
- `controller_monitor.py`
  raw HID helper process for physical button combos
- `hid.py`
  Valve controller raw report decoding
- `protocol.py`
  request/response framing helpers
- `runtime_backend.py`
  runtime-owned command handlers and process lifecycle
- `server.py`
  line-delimited JSON runtime server
- `voice_service.py`
  audio capture, transcription, and text injection
- `ydotool.py`
  helper binary discovery

## Runtime protocol

The Decky bridge and runtime communicate over line-delimited JSON on
stdin/stdout.

Request shape:

```json
{"id":"req-1","method":"initialize","params":{"config_dir":"/tmp/decktation"}}
```

Success response:

```json
{"id":"req-1","ok":true,"result":{"initialized":true,"protocol_version":1}}
```

Error response:

```json
{"id":"req-1","ok":false,"error":{"code":"unknown_method","message":"Unknown method: foo"}}
```

Async event:

```json
{"event":"log","payload":{"message":"runtime server started","protocol_version":1}}
```

Implemented runtime methods:

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

## Runtime ownership

The runtime now owns the behavior that used to be mixed into `main.py`:

- controller-monitor process startup/shutdown
- controller button-state polling
- `ydotoold` startup/shutdown
- audio capture via Pulse/PipeWire tools
- transcription model loading and execution

`runtime_client.py` is the host-side subprocess client used by `main.py`.

## Packaging model

The packaged runtime is built from locked dependencies:

- `runtime/pyproject.toml`
  source of truth for runtime dependencies
- `runtime/uv.lock`
  frozen dependency tree
- `runtime/decktation-runtime.spec`
  PyInstaller one-file build definition

`backend/Dockerfile`:

- installs `uv`
- resolves the runtime environment from `uv.lock`
- builds `ydotool` and `ydotoold`
- bundles helper binaries into the packaged runtime

`backend/entrypoint.sh` exports the final build artifacts under `backend/out/`.

`Makefile` exposes:

- `runtime-lock`
- `runtime-build`

## Installed plugin layout

The packaged plugin layout is:

```text
decktation/
  main.py
  runtime_client.py
  plugin.json
  dist/index.js
  defaults/
  bin/
    decktation-runtime
    licenses/
```

The old root compatibility shims have been removed:

- `wow_voice_chat.py`
- `controller_listener.py`
- `deck_hid.py`
- `runtime_bootstrap.py`

Tests and developer tooling now import `decktation_runtime.*` directly.

## Release and install flow

Current release flow:

1. Build the packaged runtime.
2. Build `decktation.zip`.
3. Upload `decktation.zip` to GitHub Releases on tags.
4. Publish lightweight Pages metadata and download index pages.

Current install flow:

- Decky installs from the packaged ZIP.
- `install_to_decky.sh` installs from a local `build-output/decktation.zip` or
  downloads the latest packaged ZIP from GitHub Releases.
- The runtime executable is installed at `bin/decktation-runtime`.

## Current status

The architectural refactor is complete.

Remaining work is operational rather than structural:

- validate the packaged runtime on target SteamOS hardware
- keep docs, CI, and release flow aligned with the packaged-runtime model
- verify Decky Plugin Database submission constraints against the packaged
  build
