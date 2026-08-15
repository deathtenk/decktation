"""Runtime server entrypoint for the backend split scaffold."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
import os
import sys
from typing import Callable, TextIO

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
    config: dict = field(default_factory=dict)
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
    ):
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout
        self.stderr = stderr or sys.stderr
        self.state = RuntimeState()
        self.handlers: dict[str, Callable[[dict], dict]] = {
            "handshake": self.handle_handshake,
            "initialize": self.handle_initialize,
            "get_status": self.handle_get_status,
            "shutdown": self.handle_shutdown,
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
        return {
            "protocol_version": PROTOCOL_VERSION,
            "runtime": "decktation-runtime",
            "initialized": self.state.initialized,
            "pid": os.getpid(),
        }

    def handle_initialize(self, params: dict) -> dict:
        self.state.config = dict(params)
        self.state.initialized = True
        self.log(
            "runtime initialized",
            config_keys=sorted(self.state.config.keys()),
        )
        return {
            "protocol_version": PROTOCOL_VERSION,
            "initialized": True,
            "config_keys": sorted(self.state.config.keys()),
        }

    def handle_get_status(self, params: dict) -> dict:
        return {
            "protocol_version": PROTOCOL_VERSION,
            "runtime": "decktation-runtime",
            "initialized": self.state.initialized,
            "shutdown_requested": self.state.shutdown_requested,
            "startup_time": self.state.startup_time,
            "config_keys": sorted(self.state.config.keys()),
        }

    def handle_shutdown(self, params: dict) -> dict:
        self.state.shutdown_requested = True
        return {
            "shutdown": True,
            "initialized": self.state.initialized,
        }

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
    server = RuntimeServer()
    return server.serve_forever()


if __name__ == "__main__":
    raise SystemExit(main())
