"""Line-delimited JSON protocol for the runtime bridge."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Any


PROTOCOL_VERSION = 1


class ProtocolError(ValueError):
    """Raised when a runtime protocol message is invalid."""

    def __init__(self, message: str, code: str = "invalid_request"):
        super().__init__(message)
        self.code = code


@dataclass
class RuntimeRequest:
    id: str
    method: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "method": self.method,
            "params": self.params,
        }


@dataclass
class RuntimeResponse:
    id: str
    ok: bool
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {"id": self.id, "ok": self.ok}
        if self.ok:
            payload["result"] = self.result or {}
        else:
            payload["error"] = self.error or {"code": "runtime_error", "message": "Unknown error"}
        return payload


@dataclass
class RuntimeEvent:
    event: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "payload": self.payload,
        }


def _loads_line(line: str) -> dict[str, Any]:
    try:
        data = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"Invalid JSON: {exc.msg}", code="invalid_json") from exc
    if not isinstance(data, dict):
        raise ProtocolError("Protocol message must be a JSON object")
    return data


def parse_request_line(line: str) -> RuntimeRequest:
    data = _loads_line(line)
    request_id = data.get("id")
    method = data.get("method")
    params = data.get("params", {})

    if not isinstance(request_id, str) or not request_id:
        raise ProtocolError("Request id must be a non-empty string")
    if not isinstance(method, str) or not method:
        raise ProtocolError("Request method must be a non-empty string")
    if not isinstance(params, dict):
        raise ProtocolError("Request params must be an object")

    return RuntimeRequest(id=request_id, method=method, params=params)


def response_ok(request_id: str, result: dict[str, Any] | None = None) -> RuntimeResponse:
    return RuntimeResponse(id=request_id, ok=True, result=result or {})


def response_error(
    request_id: str,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> RuntimeResponse:
    error = {
        "code": code,
        "message": message,
    }
    if details:
        error["details"] = details
    return RuntimeResponse(id=request_id, ok=False, error=error)


def event_message(event: str, payload: dict[str, Any] | None = None) -> RuntimeEvent:
    return RuntimeEvent(event=event, payload=payload or {})


def dump_message(message: RuntimeRequest | RuntimeResponse | RuntimeEvent | dict[str, Any]) -> str:
    if hasattr(message, "to_dict"):
        payload = message.to_dict()
    elif hasattr(message, "__dataclass_fields__"):
        payload = asdict(message)
    else:
        payload = message
    return json.dumps(payload, sort_keys=True)
