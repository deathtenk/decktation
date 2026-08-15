"""Runtime-owned backend state and command handlers."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any, Callable
import ctypes.util

from .config import DEFAULTS_DIR, PROJECT_ROOT


DEFAULT_BUTTON_CONFIG = {
    "buttons": ["L1", "R1"],
    "showNotifications": True,
    "enabled": False,
    "game": "wow",
    "confirmMode": False,
    "manualSend": False,
    "shareDiagnostics": False,
    "modelSize": "base",
    "transcriptionLanguage": "auto",
}

SUPPORTED_WHISPER_MODEL_SIZES = {"base", "small", "medium"}

SUPPORTED_WHISPER_LANGUAGES = {
    "af", "am", "ar", "as", "az", "ba", "be", "bg", "bn", "bo", "br",
    "bs", "ca", "cs", "cy", "da", "de", "el", "en", "es", "et", "eu",
    "fa", "fi", "fo", "fr", "gl", "gu", "ha", "haw", "he", "hi", "hr",
    "ht", "hu", "hy", "id", "is", "it", "ja", "jw", "ka", "kk", "km",
    "kn", "ko", "la", "lb", "ln", "lo", "lt", "lv", "mg", "mi", "mk",
    "ml", "mn", "mr", "ms", "mt", "my", "ne", "nl", "nn", "no", "oc",
    "pa", "pl", "ps", "pt", "ro", "ru", "sa", "sd", "si", "sk", "sl",
    "sn", "so", "sq", "sr", "su", "sv", "sw", "ta", "te", "tg", "th",
    "tk", "tl", "tr", "tt", "uk", "ur", "uz", "vi", "yi", "yo", "yue",
    "zh",
}

STATE_FILE = "/tmp/decktation_l5"
PREVIEW_FILE = "/tmp/decktation_button_preview"
PID_FILE = "/tmp/decktation_listener.pid"
CONTROLLER_TYPE_FILE = "/tmp/decktation_controller_type"
YDOTOOL_SOCKET = "/tmp/decktation-ydotool.sock"


def normalize_transcription_language(language: str | None) -> str:
    language = (language or "auto").strip().lower()
    if language in ("", "auto"):
        return "auto"
    if language not in SUPPORTED_WHISPER_LANGUAGES:
        raise ValueError(f"Unsupported transcription language: {language}")
    return language


def normalize_model_size(model_size: str | None) -> str:
    model_size = (model_size or "base").strip().lower()
    if model_size not in SUPPORTED_WHISPER_MODEL_SIZES:
        raise ValueError(f"Unsupported model size: {model_size}")
    return model_size


@dataclass
class RuntimeContext:
    plugin_dir: Path = PROJECT_ROOT
    config_dir: Path = PROJECT_ROOT / ".runtime-config"
    button_config_file: Path = PROJECT_ROOT / ".runtime-config" / "button_config.json"
    presets_file: Path = DEFAULTS_DIR / "game_presets.json"
    context_file: Path = PROJECT_ROOT / "wow_context.json"
    preview_file: Path = Path(PREVIEW_FILE)
    state_file: Path = Path(STATE_FILE)
    pid_file: Path = Path(PID_FILE)
    controller_type_file: Path = Path(CONTROLLER_TYPE_FILE)
    ydotool_socket: Path = Path(YDOTOOL_SOCKET)
    plugin_version: str = "unknown"
    telemetry_enabled: bool = False


@dataclass
class RuntimeBackend:
    service_factory: Callable[..., Any] | None = None
    enable_runtime_processes: bool = True
    controller_enabled: bool = False
    recording_start_count: int = 0
    active_preset: str = "wow"
    ydotoold_ready: bool = False
    runtime_context: RuntimeContext = field(default_factory=RuntimeContext)
    voice_service: Any | None = None
    presets: dict[str, dict] = field(default_factory=dict)
    listener_process: Any | None = None
    ydotoold_process: Any | None = None
    poll_thread: threading.Thread | None = None
    poll_running: bool = False
    log_callback: Callable[..., None] | None = None

    def initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        plugin_dir = Path(params.get("plugin_dir") or self.runtime_context.plugin_dir)
        config_dir = Path(params.get("config_dir") or self.runtime_context.config_dir)
        button_config_file = Path(
            params.get("button_config_file") or config_dir / "button_config.json"
        )
        presets_file = Path(
            params.get("presets_file")
            or plugin_dir / "game_presets.json"
        )
        if not presets_file.exists():
            presets_file = plugin_dir / "defaults" / "game_presets.json"
        context_file = Path(
            params.get("context_file") or plugin_dir / "wow_context.json"
        )
        preview_file = Path(
            params.get("preview_file") or self.runtime_context.preview_file
        )
        state_file = Path(
            params.get("state_file") or self.runtime_context.state_file
        )
        pid_file = Path(
            params.get("pid_file") or self.runtime_context.pid_file
        )
        controller_type_file = Path(
            params.get("controller_type_file") or self.runtime_context.controller_type_file
        )
        ydotool_socket = Path(
            params.get("ydotool_socket") or self.runtime_context.ydotool_socket
        )
        plugin_version = params.get("plugin_version", self.runtime_context.plugin_version)
        telemetry_enabled = bool(
            params.get("telemetry_enabled", self.runtime_context.telemetry_enabled)
        )

        config_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_context = RuntimeContext(
            plugin_dir=plugin_dir,
            config_dir=config_dir,
            button_config_file=button_config_file,
            presets_file=presets_file,
            context_file=context_file,
            preview_file=preview_file,
            state_file=state_file,
            pid_file=pid_file,
            controller_type_file=controller_type_file,
            ydotool_socket=ydotool_socket,
            plugin_version=plugin_version,
            telemetry_enabled=telemetry_enabled,
        )
        self._configure_bundled_portaudio()
        self.presets = self._load_presets()
        config = self._read_button_config()
        self.controller_enabled = bool(config.get("enabled", False))
        self.active_preset = config.get("game", "wow")
        self.voice_service = self._create_voice_service(config)
        if self.enable_runtime_processes:
            self.start_ydotoold()
            if self.start_controller_listener():
                self.start_polling()
        return {
            "initialized": True,
            "config_keys": sorted(params.keys()),
        }

    def _create_voice_service(self, config: dict[str, Any]):
        if self.service_factory is None:
            from .voice_service import WoWVoiceChat

            self.service_factory = WoWVoiceChat
        preset_id = config.get("game", "wow")
        preset = self.presets.get(preset_id, self.presets.get("wow", {}))
        return self.service_factory(
            context_file=str(self.runtime_context.context_file),
            lazy_load=True,
            test_mode=False,
            test_audio_file=None,
            preset=preset,
            confirm_delay=2.0 if config.get("confirmMode", False) else 0,
            manual_send=bool(config.get("manualSend", False)),
            model_size=config.get("modelSize", "base"),
            transcription_language=(
                None
                if config.get("transcriptionLanguage", "auto") == "auto"
                else config.get("transcriptionLanguage")
            ),
        )

    def _load_presets(self) -> dict[str, dict]:
        with open(self.runtime_context.presets_file, "r") as preset_file:
            return json.load(preset_file)

    def _read_button_config(self) -> dict[str, Any]:
        config = dict(DEFAULT_BUTTON_CONFIG)
        if self.runtime_context.button_config_file.exists():
            with open(self.runtime_context.button_config_file, "r") as config_file:
                saved_config = json.load(config_file)
            if isinstance(saved_config, dict):
                config.update(saved_config)
        config["transcriptionLanguage"] = normalize_transcription_language(
            config.get("transcriptionLanguage")
        )
        config["modelSize"] = normalize_model_size(config.get("modelSize"))
        config["translateToEnglish"] = False
        return config

    def _write_button_config(self, config: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(DEFAULT_BUTTON_CONFIG)
        normalized.update(config)
        normalized["transcriptionLanguage"] = normalize_transcription_language(
            normalized.get("transcriptionLanguage")
        )
        normalized["modelSize"] = normalize_model_size(normalized.get("modelSize"))
        normalized["translateToEnglish"] = False
        self.runtime_context.button_config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.runtime_context.button_config_file, "w") as config_file:
            json.dump(normalized, config_file)
        return normalized

    def handshake(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"runtime": "decktation-runtime"}

    def _configure_bundled_portaudio(self) -> None:
        bundled_portaudio = (
            self.runtime_context.plugin_dir / "bin" / "lib" / "libportaudio.so.2"
        )
        if not bundled_portaudio.is_file():
            return

        system_find_library = ctypes.util.find_library

        def find_bundled_library(name):
            if name == "portaudio":
                return str(bundled_portaudio)
            return system_find_library(name)

        ctypes.util.find_library = find_bundled_library

    def _log(self, message: str, **payload) -> None:
        if self.log_callback:
            self.log_callback(message, **payload)

    def _controller_command(self) -> list[str]:
        if getattr(sys, "frozen", False):
            return [sys.executable, "--controller-monitor"]
        return [sys.executable, "-m", "decktation_runtime.server", "--controller-monitor"]

    def _start_process_output_logger(self, process) -> None:
        threading.Thread(
            target=self._log_process_output,
            args=(process,),
            daemon=True,
        ).start()

    def _log_process_output(self, process) -> None:
        try:
            for line in process.stdout:
                self._log("child process", line=line.rstrip())
        except Exception as exc:  # pragma: no cover - defensive
            self._log("child process logging stopped", error=str(exc))

    def start_ydotoold(self) -> bool:
        self.ydotoold_ready = False
        ydotoold = self.runtime_context.plugin_dir / "bin" / "ydotoold"
        if not ydotoold.is_file():
            self._log("ydotoold missing", path=str(ydotoold))
            return False

        self.stop_ydotoold()
        try:
            self.ydotoold_process = subprocess.Popen(
                [
                    str(ydotoold),
                    "--socket-path", str(self.runtime_context.ydotool_socket),
                    "--socket-perm", "0600",
                    "--mouse-off",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self._start_process_output_logger(self.ydotoold_process)
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                if self.ydotoold_process.poll() is not None:
                    self.ydotoold_process = None
                    return False
                if self.runtime_context.ydotool_socket.exists():
                    self.ydotoold_ready = True
                    return True
                time.sleep(0.05)
        except Exception as exc:  # pragma: no cover - defensive
            self._log("failed to start ydotoold", error=str(exc))
        self.stop_ydotoold()
        return False

    def stop_ydotoold(self) -> None:
        self.ydotoold_ready = False
        process = self.ydotoold_process
        self.ydotoold_process = None
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        try:
            if self.runtime_context.ydotool_socket.exists():
                self.runtime_context.ydotool_socket.unlink()
        except OSError:
            pass

    def start_controller_listener(self) -> bool:
        self.stop_controller_listener()
        try:
            self.listener_process = subprocess.Popen(
                self._controller_command(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env={
                    **os.environ,
                    "DECKTATION_CONFIG_DIR": str(self.runtime_context.config_dir),
                },
            )
            self._start_process_output_logger(self.listener_process)
            time.sleep(0.5)
            if self.listener_process.poll() is not None:
                return False
            return True
        except Exception as exc:  # pragma: no cover - defensive
            self._log("failed to start controller listener", error=str(exc))
            return False

    def stop_controller_listener(self) -> None:
        pid_file = self.runtime_context.pid_file
        try:
            if pid_file.exists():
                pid = int(pid_file.read_text().strip())
                try:
                    os.kill(pid, 9)
                except OSError:
                    pass
        except Exception:
            pass

        if self.listener_process and self.listener_process.poll() is None:
            self.listener_process.kill()
        self.listener_process = None

        for path in (
            self.runtime_context.state_file,
            self.runtime_context.preview_file,
            self.runtime_context.pid_file,
            self.runtime_context.controller_type_file,
        ):
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass

    def start_polling(self) -> None:
        if self.poll_running:
            return
        self.poll_running = True
        self.poll_thread = threading.Thread(
            target=self.poll_button_state,
            name="decktation-runtime-poll",
            daemon=True,
        )
        self.poll_thread.start()

    def stop_polling(self) -> None:
        self.poll_running = False
        if self.poll_thread:
            self.poll_thread.join(timeout=2)
            self.poll_thread = None

    def poll_button_state(self) -> None:
        last_state = False
        health_check_counter = 0

        while self.poll_running:
            try:
                if not self.controller_enabled or self.voice_service is None:
                    time.sleep(0.1)
                    continue

                if self.runtime_context.state_file.exists():
                    state = self.runtime_context.state_file.read_text().strip() == "1"
                    if state and not last_state:
                        if self.voice_service.pending_text:
                            self.voice_service.cancel_pending()
                        elif not self.voice_service.is_recording:
                            self.voice_service.start_recording()
                            self.recording_start_count += 1
                    elif not state and last_state:
                        if self.voice_service.is_recording:
                            self.voice_service.stop_recording()
                    last_state = state

                health_check_counter += 1
                if health_check_counter >= 20:
                    health_check_counter = 0
                    if self.listener_process and self.listener_process.poll() is not None:
                        self._log("controller listener exited; restarting")
                        if self.start_controller_listener():
                            self._log("controller listener restarted")

                time.sleep(0.05)
            except Exception as exc:  # pragma: no cover - defensive
                self._log("poll_button_state error", error=str(exc))
                time.sleep(0.1)

    def get_status(self, params: dict[str, Any]) -> dict[str, Any]:
        service = self.voice_service
        model_ready = bool(service.is_model_ready()) if service else False
        model_loading = bool(getattr(service, "model_loading", False)) if service else False
        detected_button = "None"
        try:
            if self.runtime_context.preview_file.exists():
                detected_button = self.runtime_context.preview_file.read_text().strip() or "None"
        except OSError:
            pass
        pending_text = service.pending_text if service and service.pending_text else ""
        pending_delay = (
            service._confirm_delay_for(service.pending_text)
            if service and service.pending_text
            else 0
        )
        confirm_mode = bool(service.confirm_delay > 0) if service else False
        return {
            "success": True,
            "service_ready": service is not None,
            "model_ready": model_ready,
            "model_loading": model_loading,
            "recording": bool(service.is_recording) if service else False,
            "recording_start_count": self.recording_start_count,
            "detected_button": detected_button,
            "pending_text": pending_text,
            "pending_delay": pending_delay,
            "confirm_mode": confirm_mode,
            "input_ready": self.ydotoold_ready,
        }

    def shutdown(self, params: dict[str, Any]) -> dict[str, Any]:
        self.stop_polling()
        self.stop_controller_listener()
        self.stop_ydotoold()
        if self.voice_service and getattr(self.voice_service, "is_recording", False):
            self.voice_service.stop_recording(False)
        return {"shutdown": True, "initialized": self.voice_service is not None}

    def set_enabled(self, params: dict[str, Any]) -> dict[str, Any]:
        enabled = bool(params["enabled"])
        self.controller_enabled = enabled
        config = self._read_button_config()
        config["enabled"] = enabled
        self._write_button_config(config)
        return {"success": True}

    def get_button_config(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"success": True, "config": self._read_button_config()}

    def set_share_diagnostics(self, params: dict[str, Any]) -> dict[str, Any]:
        enabled = bool(params["enabled"])
        config = self._read_button_config()
        config["shareDiagnostics"] = enabled
        self._write_button_config(config)
        self.runtime_context.telemetry_enabled = enabled
        return {"success": True, "enabled": enabled}

    def set_button_config(self, params: dict[str, Any]) -> dict[str, Any]:
        buttons = params["buttons"]
        if not isinstance(buttons, list) or len(buttons) == 0:
            return {"success": False, "error": "buttons must be a non-empty list"}
        seen = set()
        unique_buttons = []
        for button in buttons:
            if button not in seen:
                seen.add(button)
                unique_buttons.append(button)
        config = self._read_button_config()
        config["buttons"] = unique_buttons
        config["showNotifications"] = bool(params.get("showNotifications", True))
        self._write_button_config(config)
        if self.enable_runtime_processes:
            self.stop_controller_listener()
            self.start_controller_listener()
        return {"success": True}

    def set_confirm_mode(self, params: dict[str, Any]) -> dict[str, Any]:
        enabled = bool(params["enabled"])
        config = self._read_button_config()
        config["confirmMode"] = enabled
        self._write_button_config(config)
        if self.voice_service:
            self.voice_service.confirm_delay = 2.0 if enabled else 0
        return {"success": True}

    def set_manual_send(self, params: dict[str, Any]) -> dict[str, Any]:
        enabled = bool(params["enabled"])
        config = self._read_button_config()
        config["manualSend"] = enabled
        self._write_button_config(config)
        if self.voice_service:
            self.voice_service.manual_send = enabled
        return {"success": True}

    def set_transcription_options(self, params: dict[str, Any]) -> dict[str, Any]:
        language = normalize_transcription_language(params.get("language", "auto"))
        config = self._read_button_config()
        config["transcriptionLanguage"] = language
        config["translateToEnglish"] = False
        self._write_button_config(config)
        if self.voice_service:
            self.voice_service.set_transcription_options(
                None if language == "auto" else language
            )
        return {"success": True, "language": language, "translateToEnglish": False}

    def set_model_size(self, params: dict[str, Any]) -> dict[str, Any]:
        model_size = normalize_model_size(params.get("modelSize", "base"))
        config = self._read_button_config()
        config["modelSize"] = model_size
        self._write_button_config(config)
        reloaded = False
        if self.voice_service:
            reloaded = self.voice_service.model is not None
            success = self.voice_service.set_model_size(model_size)
            if not success:
                return {"success": False, "error": self.voice_service.model_load_error}
        return {"success": True, "modelSize": model_size, "reloaded": reloaded}

    def get_presets(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "success": True,
            "presets": [{"id": key, "name": value["name"]} for key, value in self.presets.items()],
        }

    def get_active_preset(self, params: dict[str, Any]) -> dict[str, Any]:
        config = self._read_button_config()
        return {"success": True, "game": config.get("game", "wow")}

    def set_active_preset(self, params: dict[str, Any]) -> dict[str, Any]:
        game = params["game"]
        if game not in self.presets:
            return {"success": False, "error": f"Unknown preset: {game}"}
        config = self._read_button_config()
        config["game"] = game
        self._write_button_config(config)
        if self.voice_service:
            self.voice_service.set_preset(self.presets[game])
        self.active_preset = game
        return {"success": True}

    def start_recording(self, params: dict[str, Any]) -> dict[str, Any]:
        if self.voice_service is None:
            return {"success": False, "error": "Service not initialized"}
        self.voice_service.start_recording()
        self.recording_start_count += 1
        return {"success": True}

    def stop_recording(self, params: dict[str, Any]) -> dict[str, Any]:
        if self.voice_service is None:
            return {"success": False, "error": "Service not initialized"}
        send = bool(params.get("send", True))
        self.voice_service.stop_recording(send)
        return {"success": True}

    def is_recording(self, params: dict[str, Any]) -> dict[str, Any]:
        if self.voice_service is None:
            return {"recording": False}
        return {"recording": bool(self.voice_service.is_recording)}

    def update_context(self, params: dict[str, Any]) -> dict[str, Any]:
        context = params["context"]
        with open(self.runtime_context.context_file, "w") as context_file:
            json.dump(context, context_file)
        return {"success": True}

    def load_model(self, params: dict[str, Any]) -> dict[str, Any]:
        if self.voice_service is None:
            return {"success": False, "error": "Service not initialized"}
        success = self.voice_service._load_model()
        return {"success": success, "error": self.voice_service.model_load_error}

    def get_last_transcription(self, params: dict[str, Any]) -> dict[str, Any]:
        if self.voice_service is None:
            return {"success": False, "error": "Service not initialized"}
        return {"success": True, "transcription": self.voice_service.get_last_transcription()}
