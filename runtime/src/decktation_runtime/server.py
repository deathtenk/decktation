"""Runtime server entrypoint for the backend split scaffold."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, UTC
import os
import sys
from typing import Callable, TextIO

from .runtime_backend import RuntimeBackend
from .protocol import (
    PROTOCOL_VERSION,
    ProtocolError,
    dump_message,
    event_message,
    parse_request_line,
    response_error,
    response_ok,
)


@dataclass
class RuntimeState:
    initialized: bool = False
    startup_time: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
    shutdown_requested: bool = False


class RuntimeServer:
    """Minimal source-runnable runtime server for protocol development."""

    def __init__(
        self,
        stdin: TextIO | None = None,
        stdout: TextIO | None = None,
        stderr: TextIO | None = None,
        backend: RuntimeBackend | None = None,
    ):
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout
        self.stderr = stderr or sys.stderr
        self.state = RuntimeState()
        self.backend = backend or RuntimeBackend()
        self.handlers: dict[str, Callable[[dict], dict]] = {
            "handshake": self.handle_handshake,
            "initialize": self.handle_initialize,
            "get_status": self.handle_get_status,
            "shutdown": self.handle_shutdown,
            "set_enabled": self.handle_set_enabled,
            "get_button_config": self.handle_get_button_config,
            "set_share_diagnostics": self.handle_set_share_diagnostics,
            "set_button_config": self.handle_set_button_config,
            "set_confirm_mode": self.handle_set_confirm_mode,
            "set_manual_send": self.handle_set_manual_send,
            "set_transcription_options": self.handle_set_transcription_options,
            "set_model_size": self.handle_set_model_size,
            "get_presets": self.handle_get_presets,
            "get_active_preset": self.handle_get_active_preset,
            "set_active_preset": self.handle_set_active_preset,
            "start_recording": self.handle_start_recording,
            "stop_recording": self.handle_stop_recording,
            "is_recording": self.handle_is_recording,
            "update_context": self.handle_update_context,
            "load_model": self.handle_load_model,
            "get_last_transcription": self.handle_get_last_transcription,
        }

    def emit(self, message) -> None:
        self.stdout.write(dump_message(message) + "\n")
        self.stdout.flush()

    def log(self, message: str, **payload) -> None:
        event_payload = {"message": message}
        event_payload.update(payload)
        self.emit(event_message("log", event_payload))

    def protocol_error(self, message: str, **payload) -> None:
        event_payload = {"message": message}
        event_payload.update(payload)
        self.emit(event_message("protocol_error", event_payload))

    def handle_handshake(self, params: dict) -> dict:
        result = {
            "protocol_version": PROTOCOL_VERSION,
            "initialized": self.state.initialized,
            "pid": os.getpid(),
        }
        result.update(self.backend.handshake(params))
        return result

    def handle_initialize(self, params: dict) -> dict:
        result = self.backend.initialize(params)
        self.state.initialized = True
        self.log(
            "runtime initialized",
            config_keys=sorted(params.keys()),
        )
        result.update({"protocol_version": PROTOCOL_VERSION})
        return result

    def handle_get_status(self, params: dict) -> dict:
        result = self.backend.get_status(params)
        result.update(
            {
                "protocol_version": PROTOCOL_VERSION,
                "runtime": "decktation-runtime",
                "initialized": self.state.initialized,
                "shutdown_requested": self.state.shutdown_requested,
                "startup_time": self.state.startup_time,
            }
        )
        return result

    def handle_shutdown(self, params: dict) -> dict:
        self.state.shutdown_requested = True
        return self.backend.shutdown(params)

    def _forward(self, method_name: str, params: dict) -> dict:
        return getattr(self.backend, method_name)(params)

    def handle_set_enabled(self, params: dict) -> dict:
        return self._forward("set_enabled", params)

    def handle_get_button_config(self, params: dict) -> dict:
        return self._forward("get_button_config", params)

    def handle_set_share_diagnostics(self, params: dict) -> dict:
        return self._forward("set_share_diagnostics", params)

    def handle_set_button_config(self, params: dict) -> dict:
        return self._forward("set_button_config", params)

    def handle_set_confirm_mode(self, params: dict) -> dict:
        return self._forward("set_confirm_mode", params)

    def handle_set_manual_send(self, params: dict) -> dict:
        return self._forward("set_manual_send", params)

    def handle_set_transcription_options(self, params: dict) -> dict:
        return self._forward("set_transcription_options", params)

    def handle_set_model_size(self, params: dict) -> dict:
        return self._forward("set_model_size", params)

    def handle_get_presets(self, params: dict) -> dict:
        return self._forward("get_presets", params)

    def handle_get_active_preset(self, params: dict) -> dict:
        return self._forward("get_active_preset", params)

    def handle_set_active_preset(self, params: dict) -> dict:
        return self._forward("set_active_preset", params)

    def handle_start_recording(self, params: dict) -> dict:
        return self._forward("start_recording", params)

    def handle_stop_recording(self, params: dict) -> dict:
        return self._forward("stop_recording", params)

    def handle_is_recording(self, params: dict) -> dict:
        return self._forward("is_recording", params)

    def handle_update_context(self, params: dict) -> dict:
        return self._forward("update_context", params)

    def handle_load_model(self, params: dict) -> dict:
        return self._forward("load_model", params)

    def handle_get_last_transcription(self, params: dict) -> dict:
        return self._forward("get_last_transcription", params)

    def dispatch(self, request_line: str) -> None:
        try:
            request = parse_request_line(request_line)
        except ProtocolError as exc:
            self.protocol_error(str(exc), code=exc.code)
            return

        handler = self.handlers.get(request.method)
        if handler is None:
            self.emit(
                response_error(
                    request.id,
                    "unknown_method",
                    f"Unknown method: {request.method}",
                )
            )
            return

        try:
            result = handler(request.params)
        except Exception as exc:  # pragma: no cover - defensive path
            self.emit(
                response_error(
                    request.id,
                    "internal_error",
                    str(exc),
                )
            )
            return

        self.emit(response_ok(request.id, result))

    def serve_forever(self) -> int:
        self.log(
            "runtime server started",
            protocol_version=PROTOCOL_VERSION,
        )
        for line in self.stdin:
            stripped = line.strip()
            if not stripped:
                continue
            self.dispatch(stripped)
            if self.state.shutdown_requested:
                break
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--controller-monitor", action="store_true")
    args, _ = parser.parse_known_args()

    if args.controller_monitor:
        from .controller_monitor import main as controller_monitor_main

        controller_monitor_main()
        return 0

    server = RuntimeServer()
    return server.serve_forever()


if __name__ == "__main__":
    raise SystemExit(main())
