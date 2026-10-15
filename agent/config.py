"""Where files live, and loading your settings.

- `.env`           holds your Gemini API key (secret, never shared).
- `settings.json`  holds everything you may want to change (hotkeys, model, voice...).
                   It is created automatically the first time the agent starts.
- `data/`          holds memory, the action log and the undo journal.
"""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SETTINGS_FILE = ROOT / "settings.json"
ENV_FILE = ROOT / ".env"

MEMORY_FILE = DATA_DIR / "memory.json"
ACTION_LOG_FILE = DATA_DIR / "actions.log"
UNDO_FILE = DATA_DIR / "undo.json"
ERROR_LOG_FILE = DATA_DIR / "agent.log"

DEFAULT_SETTINGS = {
    # Gemini model name. "gemini-flash-latest" is Google's alias for the newest Flash model.
    # If it stops working, the agent picks another available Flash model automatically.
    "model": "gemini-flash-latest",

    # Hold this to talk, release to send.
    "push_to_talk_hotkey": "ctrl+alt+space",
    # Press this to open the popup and type.
    "open_popup_hotkey": "ctrl+alt+a",
    # Press this while the agent is working to stop it immediately.
    "stop_key": "esc",

    # Read short replies out loud with Windows voices.
    "speak_replies": True,
    # Speech speed from -10 (slow) to 10 (fast).
    "speech_rate": 1,

    # Safety limits.
    "max_steps_per_command": 20,
    "max_recording_seconds": 60,

    # How much of the conversation the agent keeps in mind.
    "conversation_turns_to_keep": 8,
    "new_conversation_after_idle_minutes": 30,

    # Tool names that must ALWAYS ask you first (e.g. "move_item"), or NEVER ask (use with care).
    "always_confirm_tools": [],
    "never_confirm_tools": [],

    # Extra folders the agent must ask before changing anything inside (e.g. "D:\\Important").
    "extra_protected_folders": [],

    # Windows whose title contains one of these words are never captured in screenshots (Stage 2).
    "screenshot_blocklist": ["1Password", "Bitwarden", "KeePass", "LastPass", "Bank", "은행", "Banking"],
}


def load_settings() -> dict:
    """Read settings.json, adding any missing options with their default value."""
    settings = dict(DEFAULT_SETTINGS)
    if SETTINGS_FILE.exists():
        try:
            user_settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            settings.update(user_settings)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"settings.json has a typo near line {e.lineno}: {e.msg}. "
                "Fix it, or delete the file to get the defaults back."
            ) from e
    if settings != _read_raw_settings():
        save_settings(settings)
    return settings


def _read_raw_settings():
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_settings(settings: dict) -> None:
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")


def load_api_key() -> str:
    """Read GEMINI_API_KEY from the .env file (or the environment)."""
    try:
        from dotenv import load_dotenv
        load_dotenv(ENV_FILE)
    except ImportError:
        pass
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key or key == "paste-your-key-here":
        raise ValueError(
            "No Gemini API key found. Open the file '.env' in the agent folder and put your key "
            "after GEMINI_API_KEY="
        )
    return key


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(exist_ok=True)
