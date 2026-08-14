from types import SimpleNamespace

import wow_voice_chat
from wow_voice_chat import WoWVoiceChat


class FakeNumpy:
    @staticmethod
    def abs(values):
        return [abs(value) for value in values]

    @staticmethod
    def max(values):
        return max(values)

    @staticmethod
    def square(values):
        return [value * value for value in values]

    @staticmethod
    def mean(values):
        return sum(values) / len(values)

    @staticmethod
    def sqrt(value):
        return value ** 0.5


class FakeModel:
    def __init__(self):
        self.kwargs = None

    def transcribe(self, audio, **kwargs):
        self.kwargs = kwargs
        return [SimpleNamespace(text="hello")], SimpleNamespace()


class FakeAudio(list):
    dtype = "float32"


def test_transcription_defaults_auto_detect_and_transcribe(monkeypatch):
    monkeypatch.setattr(wow_voice_chat, "np", FakeNumpy)
    service = WoWVoiceChat(lazy_load=True)
    service.model = FakeModel()
    service._prepare_audio = lambda audio, sample_rate: FakeAudio([0.0, 0.1])

    assert service.transcribe_audio([0.0, 0.1]) == "hello"

    assert service.model.kwargs["language"] is None
    assert service.model.kwargs["task"] == "transcribe"


def test_transcription_can_preselect_language_and_translate(monkeypatch):
    monkeypatch.setattr(wow_voice_chat, "np", FakeNumpy)
    service = WoWVoiceChat(
        lazy_load=True,
        transcription_language="fr",
        translate_to_english=True,
    )
    service.model = FakeModel()
    service._prepare_audio = lambda audio, sample_rate: FakeAudio([0.0, 0.1])

    assert service.transcribe_audio([0.0, 0.1]) == "hello"

    assert service.model.kwargs["language"] == "fr"
    assert service.model.kwargs["task"] == "translate"
