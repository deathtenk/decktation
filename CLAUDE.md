# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Decktation is a push-to-talk dictation plugin for Steam Deck that enables voice-to-text input for gaming. It uses OpenAI's Whisper model (via faster-whisper) with context-aware transcription optimized for World of Warcraft gameplay. All processing is done locally on the device.

## Build Commands

```bash
npm install           # Install Node dependencies (package-lock.json is ignored)
npm run build         # Compile TypeScript to dist/index.js
npm run watch         # Watch mode for development
make runtime-lock     # Refresh runtime/uv.lock from runtime/pyproject.toml
make runtime-build    # Build backend/out/decktation-runtime via Docker
```

Runtime dependencies are defined in `runtime/pyproject.toml`, frozen in
`runtime/uv.lock`, and bundled into the packaged runtime executable.
The packaged runtime is the default launch path; source runtime launching is
debug-only via `DECKTATION_RUNTIME_MODE=source`.

## Testing

```bash
# Unit tests (no hardware required)
.venv/bin/pytest tests/ -v     # Run all unit tests

# One-time venv setup (uses nix Python 3.11)
/nix/store/dwix9cc815h6vxvdvl8zc6pvznq6whdh-python3-3.11.14/bin/python -m venv .venv
.venv/bin/pip install pytest

# Manual/integration tests
PYTHONPATH=runtime/src python3 -m decktation_runtime.voice_service --mode once --duration 3
python convert_wow_context.py --watch
```

### Unit test coverage (`tests/`)

| File | What it tests |
|------|--------------|
| `test_channel_parsing.py` | `parse_channel_and_text` — all separators, all WoW channels, generic preset |
| `test_presets.py` | `game_presets.json` structure, constructor preset wiring, `set_preset` live switching |
| `test_send_behavior.py` | `send_to_wow_chat` key presses — WoW channels (Enter+Enter), type channel (no Enter), Generic preset (no Enter) |

## Architecture

The system has five main components:

1. **Frontend Plugin** (`src/index.tsx`) - React/TypeScript Decky Loader plugin UI. Provides toggle to enable dictation, dynamic button configuration (1-5 buttons), status display, and manual test button. Hybrid UI shows dropdowns for each button with add/remove controls. Note: Steam's frontend input APIs only work when Steam UI is active, so controller input is handled by the backend.

2. **Backend Plugin** (`main.py`) - Python Decky plugin backend. Uses static methods and class variables (Decky quirk). Starts the packaged runtime process, proxies the Decky RPC surface, and owns runtime lifecycle.

3. **Controller Listener** (`runtime/src/decktation_runtime/controller_monitor.py`) - Runtime-owned helper process using the Steam Deck vendor raw HID interface to detect a configurable physical button combo. Reads configuration from `button_config.json` (array of 1-5 buttons). Writes button state to `/tmp/decktation_l5`. All buttons in the combo must be pressed simultaneously to activate, independent of the active Steam Input layout.

4. **Voice Service** (`runtime/src/decktation_runtime/voice_service.py`) - Core audio processing. Records audio via Pulse/PipeWire capture, transcribes with faster-whisper (base model, int8, CPU), parses chat channel prefixes, types output via ydotool.

5. **WoW Addon** (`WowAddon/DecktationContext/`) - Lua addon that exports game state (zone, target, party members, class/spec) to SavedVariables every 2 seconds. The `convert_wow_context.py` script watches and converts this to `wow_context.json` for the voice service.

### Data Flow
```
User adds/removes buttons in UI → set_button_config RPC → button_config.json
    ↓
Button Combo (1-5 buttons, raw HID) → controller_monitor.py reads config
    ↓
All buttons pressed? → Button state → /tmp/decktation_l5
    ↓
runtime_backend poller → voice_service.start_recording()
    ↓
Audio Capture → Whisper Transcription
    ↓
Parse Channel (party, raid, say, etc.)
    ↓
ydotool Types Text → Game Chat
```

### Chat Channel Detection
Voice input like "party, hello everyone" or "raid: pull boss" is parsed to extract channel prefix (`/p`, `/raid`) and message text. Supports separators: colon, comma, period, or space. Channels: `/s`, `/p`, `/raid`, `/g`, `/o`, `/y`, `/i`, `/w`.

## Key Files

- `src/index.tsx` - Plugin UI with button configuration dropdowns, status polling, manual test button
- `main.py` - Plugin lifecycle and runtime bridge RPC endpoints
- `runtime_client.py` - Host-side subprocess client for `decktation-runtime`
- `runtime/src/decktation_runtime/controller_monitor.py` - Raw HID process for configurable button combo detection
- `button_config.json` - User's button configuration (created on first config change)
- `runtime/src/decktation_runtime/voice_service.py` - Whisper model, audio recording, transcription, ydotool output
- `convert_wow_context.py` - Lua SavedVariables parser with `--watch` mode
- `WowAddon/DecktationContext/DecktationContext.lua` - WoW addon for game context

## Configuration

- Whisper model: `WhisperModel("base", device="cpu", compute_type="int8")`
- Context file: `wow_context.json` (auto-generated from WoW SavedVariables)
- Button config: `button_config.json` (default: `{"buttons": ["L1", "R1"]}`)
- Push-to-talk: Configurable 1-5 button combo via UI (default: L1+R1)
- Available buttons: L1, R1, L2, R2, L4, R4, L5, R5, A, B, X, Y
- Logs: `/tmp/decktation.log`

## Platform Notes

- Designed for Steam Deck Linux environment (Gaming Mode)
- Uses bundled **ydotool** plus a private runtime-managed `ydotoold` instance
- All selectable built-in controls are decoded from the Steam Deck vendor raw HID interface
- Per-game Steam Input layouts can emit XInput, keyboard, or mouse events without affecting combo detection
- WoW runs via Proton; addon SavedVariables at `~/.steam/steam/steamapps/compatdata/*/pfx/drive_c/Program Files (x86)/World of Warcraft/_retail_/WTF/Account/<ACCOUNT>/SavedVariables/`
- Plugin installs to `~/homebrew/plugins/decktation/`
- Packaged runtime installs to `~/homebrew/plugins/decktation/bin/decktation-runtime`

## Known Issues

- Steam's `RegisterForControllerStateChanges` API doesn't exist on all Steam Deck versions; the listener reads the physical raw HID report instead
- Plugin class methods must use `@staticmethod` and `Plugin.xxx` instead of `self.xxx` due to Decky loader quirk
