from io import StringIO
from pathlib import Path
import json
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime" / "src"))

from decktation_runtime.server import RuntimeServer  # noqa: E402


def read_messages(output: StringIO):
    return [
        json.loads(line)
        for line in output.getvalue().splitlines()
        if line.strip()
    ]


def test_server_emits_startup_event_and_serves_initialize_status_shutdown():
    stdin = StringIO(
        "\n".join(
            [
                '{"id":"req-1","method":"initialize","params":{"config_dir":"/tmp/decktation","plugin_dir":"/tmp/plugin"}}',
                '{"id":"req-2","method":"get_status","params":{}}',
                '{"id":"req-3","method":"shutdown","params":{}}',
            ]
        )
        + "\n"
    )
    stdout = StringIO()
    server = RuntimeServer(stdin=stdin, stdout=stdout)

    exit_code = server.serve_forever()
    messages = read_messages(stdout)

    assert exit_code == 0
    assert messages[0] == {
        "event": "log",
        "payload": {
            "message": "runtime server started",
            "protocol_version": 1,
        },
    }
    assert messages[1] == {
        "event": "log",
        "payload": {
            "message": "runtime initialized",
            "config_keys": ["config_dir", "plugin_dir"],
        },
    }
    assert messages[2] == {
        "id": "req-1",
        "ok": True,
        "result": {
            "config_keys": ["config_dir", "plugin_dir"],
            "initialized": True,
            "protocol_version": 1,
        },
    }
    assert messages[3]["id"] == "req-2"
    assert messages[3]["ok"] is True
    assert messages[3]["result"]["initialized"] is True
    assert messages[3]["result"]["config_keys"] == ["config_dir", "plugin_dir"]
    assert messages[4] == {
        "id": "req-3",
        "ok": True,
        "result": {
            "initialized": True,
            "shutdown": True,
        },
    }


def test_server_returns_unknown_method_error():
    stdin = StringIO('{"id":"req-1","method":"nope","params":{}}\n')
    stdout = StringIO()
    server = RuntimeServer(stdin=stdin, stdout=stdout)

    server.serve_forever()
    messages = read_messages(stdout)

    assert messages[1] == {
        "error": {
            "code": "unknown_method",
            "message": "Unknown method: nope",
        },
        "id": "req-1",
        "ok": False,
    }


def test_server_emits_protocol_error_for_bad_json():
    stdin = StringIO("{\n")
    stdout = StringIO()
    server = RuntimeServer(stdin=stdin, stdout=stdout)

    server.serve_forever()
    messages = read_messages(stdout)

    assert messages[1] == {
        "event": "protocol_error",
        "payload": {
            "code": "invalid_json",
            "message": "Invalid JSON: Expecting property name enclosed in double quotes",
        },
    }
