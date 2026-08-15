from io import StringIO
from pathlib import Path
import json
import sys
import tempfile


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime" / "src"))

from decktation_runtime.runtime_backend import RuntimeBackend  # noqa: E402
from decktation_runtime.server import RuntimeServer  # noqa: E402


def read_messages(output: StringIO):
    return [
        json.loads(line)
        for line in output.getvalue().splitlines()
        if line.strip()
    ]


def test_server_emits_startup_event_and_serves_initialize_status_shutdown():
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_dir = Path(tmpdir)
        config_dir = plugin_dir / "config"
        defaults_dir = plugin_dir / "defaults"
        defaults_dir.mkdir(parents=True)
        (defaults_dir / "game_presets.json").write_text(
            json.dumps(
                {
                    "wow": {
                        "name": "World of Warcraft",
                        "chat_open_key": "enter",
                        "chat_send_key": "enter",
                        "default_channel": "say",
                        "channels": {"say": "/s ", "type": ""},
                        "whisper_prompt": "",
                    }
                }
            )
        )

        stdin = StringIO(
            "\n".join(
                [
                    json.dumps(
                        {
                            "id": "req-1",
                            "method": "initialize",
                            "params": {
                                "config_dir": str(config_dir),
                                "plugin_dir": str(plugin_dir),
                            },
                        }
                    ),
                    '{"id":"req-2","method":"get_status","params":{}}',
                    '{"id":"req-3","method":"shutdown","params":{}}',
                ]
            )
            + "\n"
        )
        stdout = StringIO()
        server = RuntimeServer(stdin=stdin, stdout=stdout, backend=RuntimeBackend(service_factory=FakeService))

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
        assert messages[3]["result"]["service_ready"] is True
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


class FakeService:
    def __init__(
        self,
        context_file,
        lazy_load,
        test_mode,
        test_audio_file,
        preset,
        confirm_delay,
        manual_send,
        model_size,
        transcription_language,
    ):
        self.context_file = context_file
        self.preset = preset
        self.confirm_delay = confirm_delay
        self.manual_send = manual_send
        self.model_size = model_size
        self.transcription_language = transcription_language
        self.model = None
        self.model_loading = False
        self.model_load_error = None
        self.is_recording = False
        self.pending_text = None
        self.last_transcription = {"text": "last", "timestamp": 1}

    def is_model_ready(self):
        return self.model is not None

    def _confirm_delay_for(self, text):
        return 3.2

    def set_transcription_options(self, language=None):
        self.transcription_language = language

    def set_model_size(self, model_size):
        self.model_size = model_size
        return True

    def set_preset(self, preset):
        self.preset = preset

    def start_recording(self):
        self.is_recording = True

    def stop_recording(self, send=True):
        self.is_recording = False
        self.pending_text = "recorded text" if send else None

    def _load_model(self):
        self.model = object()
        self.model_load_error = None
        return True

    def get_last_transcription(self):
        return self.last_transcription


def test_server_supports_full_request_response_api_surface():
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_dir = Path(tmpdir)
        config_dir = plugin_dir / "config"
        defaults_dir = plugin_dir / "defaults"
        defaults_dir.mkdir(parents=True)
        (defaults_dir / "game_presets.json").write_text(
            json.dumps(
                {
                    "wow": {
                        "name": "World of Warcraft",
                        "chat_open_key": "enter",
                        "chat_send_key": "enter",
                        "default_channel": "say",
                        "channels": {"say": "/s ", "type": ""},
                        "whisper_prompt": "",
                    },
                    "generic": {
                        "name": "Generic",
                        "chat_open_key": None,
                        "chat_send_key": None,
                        "default_channel": "type",
                        "channels": {"type": ""},
                        "whisper_prompt": "",
                    },
                }
            )
        )
        preview_file = plugin_dir / "preview.txt"
        preview_file.write_text("R1")

        commands = [
            {
                "id": "init",
                "method": "initialize",
                "params": {
                    "plugin_dir": str(plugin_dir),
                    "config_dir": str(config_dir),
                    "preview_file": str(preview_file),
                },
            },
            {"id": "cfg1", "method": "get_button_config", "params": {}},
            {"id": "en1", "method": "set_enabled", "params": {"enabled": True}},
            {
                "id": "btn1",
                "method": "set_button_config",
                "params": {"buttons": ["L1", "R1", "L1"], "showNotifications": False},
            },
            {"id": "diag1", "method": "set_share_diagnostics", "params": {"enabled": True}},
            {"id": "conf1", "method": "set_confirm_mode", "params": {"enabled": True}},
            {"id": "man1", "method": "set_manual_send", "params": {"enabled": True}},
            {
                "id": "lang1",
                "method": "set_transcription_options",
                "params": {"language": "fr", "translateToEnglish": False},
            },
            {"id": "model1", "method": "set_model_size", "params": {"modelSize": "small"}},
            {"id": "presets1", "method": "get_presets", "params": {}},
            {"id": "game1", "method": "get_active_preset", "params": {}},
            {"id": "game2", "method": "set_active_preset", "params": {"game": "generic"}},
            {"id": "load1", "method": "load_model", "params": {}},
            {"id": "rec1", "method": "start_recording", "params": {}},
            {"id": "rec2", "method": "is_recording", "params": {}},
            {"id": "rec3", "method": "stop_recording", "params": {"send": True}},
            {"id": "ctx1", "method": "update_context", "params": {"context": {"zone": "Azeroth"}}},
            {"id": "last1", "method": "get_last_transcription", "params": {}},
            {"id": "status1", "method": "get_status", "params": {}},
        ]

        stdin = StringIO("\n".join(json.dumps(command) for command in commands) + "\n")
        stdout = StringIO()
        server = RuntimeServer(stdin=stdin, stdout=stdout, backend=RuntimeBackend(service_factory=FakeService))

        server.serve_forever()
        messages = read_messages(stdout)
        responses = [message for message in messages if "id" in message]
        by_id = {message["id"]: message for message in responses}

        assert by_id["cfg1"]["result"]["config"]["buttons"] == ["L1", "R1"]
        assert by_id["en1"]["result"] == {"success": True}
        assert by_id["btn1"]["result"] == {"success": True}
        assert by_id["diag1"]["result"] == {"success": True, "enabled": True}
        assert by_id["conf1"]["result"] == {"success": True}
        assert by_id["man1"]["result"] == {"success": True}
        assert by_id["lang1"]["result"] == {
            "success": True,
            "language": "fr",
            "translateToEnglish": False,
        }
        assert by_id["model1"]["result"] == {
            "success": True,
            "modelSize": "small",
            "reloaded": False,
        }
        assert by_id["presets1"]["result"]["success"] is True
        assert by_id["game1"]["result"] == {"success": True, "game": "wow"}
        assert by_id["game2"]["result"] == {"success": True}
        assert by_id["load1"]["result"] == {"success": True, "error": None}
        assert by_id["rec1"]["result"] == {"success": True}
        assert by_id["rec2"]["result"] == {"recording": True}
        assert by_id["rec3"]["result"] == {"success": True}
        assert by_id["ctx1"]["result"] == {"success": True}
        assert by_id["last1"]["result"] == {
            "success": True,
            "transcription": {"text": "last", "timestamp": 1},
        }
        assert by_id["status1"]["result"]["success"] is True
        assert by_id["status1"]["result"]["detected_button"] == "R1"
        assert by_id["status1"]["result"]["model_ready"] is True
        assert by_id["status1"]["result"]["input_ready"] is False


def test_server_validates_language_and_model_errors():
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_dir = Path(tmpdir)
        defaults_dir = plugin_dir / "defaults"
        defaults_dir.mkdir(parents=True)
        (defaults_dir / "game_presets.json").write_text(
            json.dumps(
                {
                    "wow": {
                        "name": "World of Warcraft",
                        "chat_open_key": "enter",
                        "chat_send_key": "enter",
                        "default_channel": "say",
                        "channels": {"say": "/s ", "type": ""},
                        "whisper_prompt": "",
                    }
                }
            )
        )
        stdin = StringIO(
            "\n".join(
                [
                    json.dumps(
                        {
                            "id": "init",
                            "method": "initialize",
                            "params": {"plugin_dir": str(plugin_dir), "config_dir": str(plugin_dir / "config")},
                        }
                    ),
                    '{"id":"badlang","method":"set_transcription_options","params":{"language":"xx"}}',
                    '{"id":"badmodel","method":"set_model_size","params":{"modelSize":"huge"}}',
                ]
            )
            + "\n"
        )
        stdout = StringIO()
        server = RuntimeServer(stdin=stdin, stdout=stdout, backend=RuntimeBackend(service_factory=FakeService))

        server.serve_forever()
        messages = read_messages(stdout)
        responses = [message for message in messages if "id" in message]
        by_id = {message["id"]: message for message in responses}

        assert by_id["badlang"]["error"]["code"] == "internal_error"
        assert "Unsupported transcription language" in by_id["badlang"]["error"]["message"]
        assert by_id["badmodel"]["error"]["code"] == "internal_error"
        assert "Unsupported model size" in by_id["badmodel"]["error"]["message"]
