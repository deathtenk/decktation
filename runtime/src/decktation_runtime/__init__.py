"""Runtime package scaffold for Decktation."""

__all__ = ["WoWVoiceChat", "raw_button_states"]


def __getattr__(name):
    if name == "WoWVoiceChat":
        from .voice_service import WoWVoiceChat

        return WoWVoiceChat
    if name == "raw_button_states":
        from .hid import raw_button_states

        return raw_button_states
    raise AttributeError(name)
