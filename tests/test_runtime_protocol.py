from pathlib import Path
import sys

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime" / "src"))

from decktation_runtime.protocol import (  # noqa: E402
    ProtocolError,
    dump_message,
    event_message,
    parse_request_line,
    response_error,
    response_ok,
)


def test_parse_request_line_accepts_valid_request():
    request = parse_request_line(
        '{"id":"req-1","method":"initialize","params":{"config_dir":"/tmp"}}'
    )

    assert request.id == "req-1"
    assert request.method == "initialize"
    assert request.params == {"config_dir": "/tmp"}


def test_parse_request_line_rejects_invalid_json():
    with pytest.raises(ProtocolError, match="Invalid JSON"):
        parse_request_line("{")


def test_parse_request_line_rejects_missing_method():
    with pytest.raises(ProtocolError, match="method must be a non-empty string"):
        parse_request_line('{"id":"req-1","params":{}}')


def test_parse_request_line_rejects_non_object_params():
    with pytest.raises(ProtocolError, match="params must be an object"):
        parse_request_line('{"id":"req-1","method":"initialize","params":[]}')


def test_response_ok_serializes_result_payload():
    payload = dump_message(response_ok("req-1", {"initialized": True}))

    assert payload == (
        '{"id": "req-1", "ok": true, "result": {"initialized": true}}'
    )


def test_response_error_serializes_error_payload():
    payload = dump_message(
        response_error("req-1", "unknown_method", "Unknown method: nope")
    )

    assert payload == (
        '{"error": {"code": "unknown_method", "message": "Unknown method: nope"}, '
        '"id": "req-1", "ok": false}'
    )


def test_event_message_serializes_payload():
    payload = dump_message(event_message("log", {"message": "started"}))

    assert payload == '{"event": "log", "payload": {"message": "started"}}'
