from unittest.mock import MagicMock

import telemetry


def test_dictation_trace_contains_only_requested_diagnostics(monkeypatch):
    monkeypatch.setattr(telemetry, "_enabled", True)
    transaction = MagicMock()
    monkeypatch.setattr(
        telemetry.sentry_sdk,
        "start_transaction",
        MagicMock(return_value=transaction),
    )

    result = telemetry.start_dictation_trace("guild_wars_2", "steam_deck")
    telemetry.finish_dictation_trace(result, True)

    transaction.set_tag.assert_any_call("preset", "guild_wars_2")
    transaction.set_tag.assert_any_call("controller_type", "steam_deck")
    transaction.set_tag.assert_any_call("success", True)
    transaction.set_status.assert_called_once_with("ok")
    transaction.finish.assert_called_once_with()


def test_scrubber_removes_user_content_and_home_path():
    scrubbed = telemetry._scrub(
        {
            "transcription": "private speech",
            "username": "deck",
            "path": "/home/deck/plugin/file",
        }
    )

    assert scrubbed == {"path": "<home>/plugin/file"}


def test_event_scrubber_removes_automatic_device_metadata():
    event = {
        "server_name": "personal-device",
        "user": {"ip_address": "192.0.2.1"},
        "request": {"headers": {"authorization": "secret"}},
        "modules": {"private-package": "1.0"},
        "contexts": {
            "device": {"name": "Personal Deck"},
            "os": {"name": "Linux"},
            "runtime": {"name": "CPython"},
            "trace": {"trace_id": "abc", "span_id": "def"},
            "decktation": {"preset": "wow"},
        },
    }

    assert telemetry._before_send(event, {}) == {
        "contexts": {
            "trace": {"trace_id": "abc", "span_id": "def"},
            "decktation": {"preset": "wow"},
        }
    }


def test_disabled_diagnostics_do_not_create_events_or_traces(monkeypatch):
    monkeypatch.setattr(telemetry, "_enabled", False)
    capture_message = MagicMock()
    start_transaction = MagicMock()
    monkeypatch.setattr(telemetry.sentry_sdk, "capture_message", capture_message)
    monkeypatch.setattr(
        telemetry.sentry_sdk, "start_transaction", start_transaction
    )

    assert telemetry.capture_error("test.failure") is None
    assert telemetry.start_dictation_trace("wow", "steam_deck") is None
    capture_message.assert_not_called()
    start_transaction.assert_not_called()
