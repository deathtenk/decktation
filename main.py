import os
import sys
import json
import logging
import asyncio
import traceback
import shutil

# Decky API v1 uses ``decky``. Keep the old module name as a compatibility
# fallback for stable loader versions that predate the rename.
try:
    import decky
except ImportError:  # pragma: no cover - depends on the installed Decky version
    import decky_plugin as decky

# Setup logging first
logging.basicConfig(
    filename="/tmp/decktation.log",
    format="Decktation: %(asctime)s %(levelname)s %(message)s",
    filemode="w+",
    force=True,
)
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

plugin_path = os.environ["DECKY_PLUGIN_DIR"]

# Add our service to Python path
sys.path.insert(0, plugin_path)

from runtime_client import RuntimeClient, RuntimeClientError

# Import diagnostics support without connecting to Sentry. Collection is
# opt-in and is initialized only after the persisted user preference is read.
telemetry = False
telemetry_available = False
plugin_version = "unknown"
try:
    from telemetry import (
        breadcrumb as telemetry_breadcrumb,
        capture_error as telemetry_capture_error,
        flush as telemetry_flush,
        finish_dictation_trace as telemetry_finish_dictation,
        initialize as initialize_telemetry,
        set_enabled as telemetry_set_enabled,
        start_dictation_trace as telemetry_start_dictation,
    )

    with open(os.path.join(plugin_path, "plugin.json"), "r") as version_file:
        plugin_version = json.load(version_file).get("version", "unknown")
    telemetry_available = True
except Exception as e:
    logger.error(f"Failed to import diagnostics: {e}")

# Read consent before importing optional voice dependencies so startup import
# failures can be captured for users who have opted in.
decky_user_home = getattr(decky, "DECKY_USER_HOME", "/home/deck")
CONFIG_DIR = getattr(
    decky,
    "DECKY_SETTINGS_DIR",
    os.path.join(decky_user_home, "homebrew", "settings", "decktation"),
)
os.makedirs(CONFIG_DIR, exist_ok=True)
BUTTON_CONFIG_FILE = os.path.join(CONFIG_DIR, "button_config.json")

if telemetry_available:
    try:
        if os.path.exists(BUTTON_CONFIG_FILE):
            with open(BUTTON_CONFIG_FILE, "r") as diagnostics_config_file:
                diagnostics_config = json.load(diagnostics_config_file)
            telemetry = bool(diagnostics_config.get("shareDiagnostics", False))
        if telemetry:
            initialize_telemetry(plugin_version)
            telemetry_breadcrumb("plugin.initializing")
    except Exception as e:
        telemetry = False
        logger.error(f"Failed to initialize diagnostics: {e}")

# Debug: Log Python environment
logger.info(f"Python executable: {sys.executable}")
logger.info(f"Python version: {sys.version}")
logger.info(f"sys.path (first 5): {sys.path[:5]}")
logger.info(f"Current working directory: {os.getcwd()}")

# File paths for subprocess communication
STATE_FILE = "/tmp/decktation_l5"
PREVIEW_FILE = "/tmp/decktation_button_preview"
PID_FILE = "/tmp/decktation_listener.pid"
CONTROLLER_TYPE_FILE = "/tmp/decktation_controller_type"
# Decktation owns this socket and never modifies a system ydotool service.
YDOTOOL_SOCKET = "/tmp/decktation-ydotool.sock"

PRESETS_FILE = os.path.join(plugin_path, "game_presets.json")
if not os.path.exists(PRESETS_FILE):
    # Decky's builder installs the contents of defaults/ at the plugin root.
    # Keep source-tree execution useful for tests and local development.
    PRESETS_FILE = os.path.join(plugin_path, "defaults", "game_presets.json")

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


def _normalize_transcription_language(language):
    language = (language or "auto").strip().lower()
    if language in ("", "auto"):
        return "auto"
    if language not in SUPPORTED_WHISPER_LANGUAGES:
        raise ValueError(f"Unsupported transcription language: {language}")
    return language


def _normalize_model_size(model_size):
    model_size = (model_size or "base").strip().lower()
    if model_size not in SUPPORTED_WHISPER_MODEL_SIZES:
        raise ValueError(f"Unsupported model size: {model_size}")
    return model_size


def _read_button_config():
    config = dict(DEFAULT_BUTTON_CONFIG)
    if os.path.exists(BUTTON_CONFIG_FILE):
        with open(BUTTON_CONFIG_FILE, "r") as config_file:
            saved_config = json.load(config_file)
        if isinstance(saved_config, dict):
            config.update(saved_config)

    config["transcriptionLanguage"] = _normalize_transcription_language(
        config.get("transcriptionLanguage")
    )
    config["modelSize"] = _normalize_model_size(config.get("modelSize"))
    config["translateToEnglish"] = False
    return config


def _write_button_config(config):
    normalized_config = dict(DEFAULT_BUTTON_CONFIG)
    normalized_config.update(config)
    normalized_config["transcriptionLanguage"] = _normalize_transcription_language(
        normalized_config.get("transcriptionLanguage")
    )
    normalized_config["modelSize"] = _normalize_model_size(
        normalized_config.get("modelSize")
    )
    normalized_config["translateToEnglish"] = False
    with open(BUTTON_CONFIG_FILE, "w") as config_file:
        json.dump(normalized_config, config_file)
    return normalized_config

class Plugin:
    runtime_client = None
    runtime_events = {}
    runtime_initialized = False

    @staticmethod
    def _handle_runtime_event(event, payload):
        Plugin.runtime_events[event] = payload
        if event == "log":
            logger.info("Runtime: %s %s", payload.get("message", ""), payload)
        elif event == "protocol_error":
            logger.error("Runtime protocol error: %s", payload)
        else:
            logger.info("Runtime event %s: %s", event, payload)

    @staticmethod
    def _runtime_initialize_params():
        return {
            "plugin_dir": plugin_path,
            "config_dir": CONFIG_DIR,
            "button_config_file": BUTTON_CONFIG_FILE,
            "presets_file": PRESETS_FILE,
            "context_file": os.path.join(plugin_path, "wow_context.json"),
            "preview_file": PREVIEW_FILE,
            "state_file": STATE_FILE,
            "pid_file": PID_FILE,
            "controller_type_file": CONTROLLER_TYPE_FILE,
            "ydotool_socket": YDOTOOL_SOCKET,
            "plugin_version": plugin_version,
            "telemetry_enabled": telemetry,
        }

    @staticmethod
    async def _ensure_runtime():
        if Plugin.runtime_client and Plugin.runtime_initialized:
            return

        if Plugin.runtime_client is None:
            Plugin.runtime_client = RuntimeClient(
                plugin_path,
                logger,
                event_handler=Plugin._handle_runtime_event,
            )

        try:
            result = await asyncio.to_thread(
                Plugin.runtime_client.request,
                "initialize",
                Plugin._runtime_initialize_params(),
            )
            Plugin.runtime_initialized = bool(result.get("initialized", False))
        except Exception:
            Plugin._stop_runtime()
            raise

    @staticmethod
    def _stop_runtime():
        if Plugin.runtime_client:
            Plugin.runtime_client.stop()
        Plugin.runtime_client = None
        Plugin.runtime_initialized = False

    @staticmethod
    async def _runtime_call(method, params=None):
        await Plugin._ensure_runtime()
        return await asyncio.to_thread(
            Plugin.runtime_client.request,
            method,
            params or {},
        )

    async def _main(self):
        """Initialize the plugin"""
        try:
            logger.info("Initializing Decktation plugin")
            await Plugin._ensure_runtime()
            logger.info("Runtime bridge initialized")
            if telemetry:
                telemetry_breadcrumb("runtime.initialized")
        except Exception as e:
            logger.error(f"Failed to initialize: {traceback.format_exc()}")
            if telemetry:
                telemetry_capture_error("plugin.initialization_failed", e)
        return

    async def _unload(self):
        """Cleanup when plugin unloads"""
        logger.info("Unloading Decktation plugin")
        try:
            Plugin._stop_runtime()
        except Exception as e:
            logger.error(f"Error during unload: {traceback.format_exc()}")
            if telemetry:
                telemetry_capture_error("plugin.unload_failed", e)
        if telemetry:
            telemetry_flush()
        return

    async def _uninstall(self):
        """Remove runtime processes and transient files on uninstall."""
        Plugin._stop_runtime()

    async def _migration(self):
        """Move settings created by pre-store releases into Decky's settings."""
        legacy_dir = os.path.join(decky_user_home, ".config", "decktation")
        legacy_config = os.path.join(legacy_dir, "button_config.json")
        if not os.path.exists(BUTTON_CONFIG_FILE) and os.path.isfile(legacy_config):
            try:
                shutil.copy2(legacy_config, BUTTON_CONFIG_FILE)
                logger.info(f"Migrated settings from {legacy_config}")
            except OSError as error:
                logger.warning(f"Could not migrate settings: {error}")

    async def set_enabled(self, enabled: bool):
        """Enable or disable controller listening"""
        try:
            return await Plugin._runtime_call("set_enabled", {"enabled": enabled})
        except Exception as e:
            logger.error(f"Error setting enabled state: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}

    async def get_button_config(self):
        """Get current button configuration and settings"""
        try:
            return await Plugin._runtime_call("get_button_config")
        except Exception as e:
            logger.error(f"Error getting button config: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}

    async def set_share_diagnostics(self, enabled: bool):
        """Persist and immediately apply anonymous diagnostics consent."""
        global telemetry
        try:
            result = await Plugin._runtime_call(
                "set_share_diagnostics",
                {"enabled": enabled},
            )
            telemetry = bool(result.get("enabled", False)) and telemetry_available
            if telemetry_available:
                telemetry_set_enabled(telemetry, plugin_version)
            logger.info(f"Anonymous diagnostics {'enabled' if telemetry else 'disabled'}")
            return result
        except Exception as e:
            telemetry = False
            logger.error(f"Error saving diagnostics preference: {e}")
            return {"success": False, "error": str(e)}

    async def set_button_config(self, buttons: list, showNotifications: bool = True):
        """Set button configuration and settings, restart listener"""
        try:
            return await Plugin._runtime_call(
                "set_button_config",
                {
                    "buttons": buttons,
                    "showNotifications": showNotifications,
                },
            )
        except Exception as e:
            logger.error(f"Error setting button config: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}

    async def set_confirm_mode(self, enabled: bool):
        """Enable or disable the confirm-before-sending delay"""
        try:
            return await Plugin._runtime_call("set_confirm_mode", {"enabled": enabled})
        except Exception as e:
            logger.error(f"Error setting confirm mode: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}

    async def set_manual_send(self, enabled: bool):
        """Enable or disable manual send mode (skip final Enter press)"""
        try:
            return await Plugin._runtime_call("set_manual_send", {"enabled": enabled})
        except Exception as e:
            logger.error(f"Error setting manual send mode: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}

    async def set_transcription_options(self, language: str = "auto", translateToEnglish: bool = False):
        """Set Faster Whisper language selection."""
        try:
            return await Plugin._runtime_call(
                "set_transcription_options",
                {
                    "language": language,
                    "translateToEnglish": translateToEnglish,
                },
            )
        except Exception as e:
            logger.error(f"Error setting transcription options: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}

    async def set_model_size(self, modelSize: str = "base"):
        """Set the Faster Whisper model size and reload the model if needed."""
        try:
            return await Plugin._runtime_call(
                "set_model_size",
                {"modelSize": modelSize},
            )
        except Exception as e:
            logger.error(f"Error setting model size: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}

    async def get_presets(self):
        """Get all available game presets"""
        try:
            return await Plugin._runtime_call("get_presets")
        except Exception as e:
            logger.error(f"Error getting presets: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}

    async def get_active_preset(self):
        """Get the currently active game preset id"""
        try:
            return await Plugin._runtime_call("get_active_preset")
        except Exception as e:
            logger.error(f"Error getting active preset: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}

    async def set_active_preset(self, game: str):
        """Switch to a different game preset"""
        try:
            return await Plugin._runtime_call("set_active_preset", {"game": game})
        except Exception as e:
            logger.error(f"Error setting active preset: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}

    async def start_recording(self):
        """Start recording audio"""
        try:
            return await Plugin._runtime_call("start_recording")
        except Exception as e:
            logger.error(f"Error starting recording: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}

    async def stop_recording(self, send: bool = True):
        """Stop recording and transcribe"""
        try:
            return await Plugin._runtime_call("stop_recording", {"send": send})
        except Exception as e:
            logger.error(f"Error stopping recording: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}

    async def is_recording(self):
        """Check if currently recording"""
        try:
            return await Plugin._runtime_call("is_recording")
        except Exception as e:
            logger.error(f"Error checking recording status: {traceback.format_exc()}")
            return {"recording": False}

    async def update_context(self, context: dict):
        """Update WoW context for better transcription"""
        try:
            return await Plugin._runtime_call("update_context", {"context": context})
        except Exception as e:
            logger.error(f"Error updating context: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}

    async def get_status(self):
        """Get plugin status"""
        try:
            return await Plugin._runtime_call("get_status")
        except Exception as e:
            logger.error(f"Error getting status: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}

    async def load_model(self):
        """Explicitly load the Whisper model (called when user enables dictation)"""
        try:
            return await Plugin._runtime_call("load_model")
        except Exception as e:
            logger.error(f"Error loading model: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}

    async def get_last_transcription(self):
        """Get the last transcription result for UI display"""
        try:
            return await Plugin._runtime_call("get_last_transcription")
        except Exception as e:
            logger.error(f"Error getting last transcription: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}
