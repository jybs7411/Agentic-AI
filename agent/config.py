"""Where files live, and loading your settings.

- `.env`           holds your API keys (secret, never shared).
- `settings.json`  holds everything you may want to change (hotkeys, AI models, voice...).
                   It is created automatically the first time the agent starts.
- `data/`          holds memory, the action log, the undo journal and the cloud cost record.
"""

import json
import os
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SETTINGS_FILE = ROOT / "settings.json"
ENV_FILE = ROOT / ".env"

MEMORY_FILE = DATA_DIR / "memory.json"
ACTION_LOG_FILE = DATA_DIR / "actions.log"
UNDO_FILE = DATA_DIR / "undo.json"
USAGE_FILE = DATA_DIR / "usage.json"
ERROR_LOG_FILE = DATA_DIR / "agent.log"

# AI "brains" the agent can think with. All of them speak the OpenAI-compatible API.
# Prices are US dollars per 1 million tokens, used only to track your monthly spending.
# They are estimates: check the provider's price page and correct them if needed.
DEFAULT_BRAINS = {
    "glm": {
        "label": "GLM-4.6V (Z.ai)",
        "base_url": "https://api.z.ai/api/paas/v4/",
        "api_key_env": "ZAI_API_KEY",
        "model": "glm-4.6v",
        "vision": True,
        "price_input": 0.3, "price_output": 0.9,
        "timeout": 120,
    },
    "glm-flash": {
        "label": "GLM-4.6V-Flash (Z.ai, free)",
        "base_url": "https://api.z.ai/api/paas/v4/",
        "api_key_env": "ZAI_API_KEY",
        "model": "glm-4.6v-flash",
        "vision": True,
        "price_input": 0, "price_output": 0,
        "timeout": 120,
    },
    "qwen": {
        "label": "Qwen-VL (Alibaba Cloud)",
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "api_key_env": "DASHSCOPE_API_KEY",
        "model": "qwen3-vl-plus",
        "vision": True,
        "price_input": 0.2, "price_output": 1.6,
        "timeout": 120,
    },
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "api_key_env": "DEEPSEEK_API_KEY",
        "model": "deepseek-chat",
        "vision": False,
        "price_input": 0.3, "price_output": 1.2,
        "timeout": 120,
    },
    "gemini": {
        "label": "Gemini (Google)",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key_env": "GEMINI_API_KEY",
        "model": "gemini-flash-latest",
        # Each Gemini model has its own free DAILY limit: when one runs out, the next one is used
        # until midnight Pacific time. Per-minute limits are just waited out.
        "auto_switch_models": True,
        "model_filter": "flash",
        "candidate_models": ["gemini-flash-latest", "gemini-2.5-flash", "gemini-flash-lite-latest",
                             "gemini-2.5-flash-lite"],
        # Less "thinking" per step: faster answers and fewer tokens ("low" works on all Flash models).
        "reasoning_effort": "low",
        "vision": True,
        "price_input": 0, "price_output": 0,  # free tier; put real prices here if you enable billing
        "timeout": 120,
    },
    "openrouter": {
        "label": "OpenRouter (any model)",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "model": "openrouter/auto",  # or e.g. a specific model name from openrouter.ai/models
        "vision": True,
        "price_input": 3.0, "price_output": 15.0,  # depends on the model; set it to your model's price
        "timeout": 120,
    },
}

DEFAULT_SETTINGS = {
    # Which AI thinks for the agent (a name from "brains" below). Also selectable in the tray menu
    # and the popup. The backup takes over when the main AI is unavailable (limit used up, no key,
    # server off). "" = no backup.
    "main_brain": "gemini",
    "backup_brain": "",
    # Stop using paid cloud brains when this month's estimated cost reaches this (US dollars).
    "cloud_monthly_budget_usd": 6.0,
    "brains": DEFAULT_BRAINS,

    # Voice commands are transcribed by Gemini (one small request per command). A "lite" model has
    # its own, larger free limit, so voice doesn't use up the main AI's requests.
    "voice_model": "gemini-flash-lite-latest",
    # Language of the popup, tray and messages: "ko" or "en". (The AI always answers in your language.)
    "ui_language": "ko",
    # Text size in the popup (bigger = easier to read). Where you leave the popup is remembered.
    "ui_font_size": 10,
    "popup_geometry": "",

    # Hold this to talk, release to send.
    "push_to_talk_hotkey": "ctrl+alt+space",
    # Press this to open the popup and type.
    "open_popup_hotkey": "ctrl+alt+a",
    # Press this while the agent is working to stop it immediately.
    "stop_key": "esc",
    # Select text in any app, press this, then pick an action (or say/type what to do with it).
    "selection_hotkey": "ctrl+alt+w",
    # The quick buttons shown for selected text: button label -> what the agent is asked to do.
    "selection_actions": {
        "다듬기": "선택한 글을 내 문체로 자연스럽게 다듬어서 그 자리에 바꿔 넣어줘. 원래 언어는 유지해줘.",
        "맞춤법": "선택한 글의 맞춤법, 띄어쓰기, 문법만 고쳐서 바꿔 넣어줘. 내용과 말투는 바꾸지 마.",
        "요약": "선택한 글을 3줄로 요약해서 보여줘. 바꿔 넣지는 마.",
        "한국어로": "선택한 글을 자연스러운 한국어로 번역해서 그 자리에 바꿔 넣어줘.",
        "English": "선택한 글을 자연스러운 영어로 번역해서 그 자리에 바꿔 넣어줘.",
        "Deutsch": "선택한 글을 자연스러운 독일어로 번역해서 그 자리에 바꿔 넣어줘.",
    },

    # Read short replies out loud with Windows voices.
    "speak_replies": True,
    # Speech speed from -10 (slow) to 10 (fast).
    "speech_rate": 1,

    # Safety limits (each step is one AI request; the free Gemini tier allows only a limited number).
    "max_steps_per_command": 15,
    "max_recording_seconds": 60,

    # How much of the conversation the agent keeps in mind.
    "conversation_turns_to_keep": 6,
    "new_conversation_after_idle_minutes": 30,

    # Tool names that must ALWAYS ask you first (e.g. "move_item"), or NEVER ask (use with care).
    "always_confirm_tools": [],
    "never_confirm_tools": [],

    # Extra folders the agent must ask before changing anything inside (e.g. "D:\\Important").
    "extra_protected_folders": [],

    # Screen control (Stage 2).
    # Windows whose title contains one of these words are never captured in screenshots.
    "screenshot_blocklist": ["1Password", "Bitwarden", "KeePass", "LastPass", "Bank", "은행", "Banking"],
    # Screenshots are shrunk to this width before being sent (smaller = cheaper and faster).
    "screenshot_max_width": 1280,
    # Clicking a button whose name contains one of these words asks you first.
    "risky_click_words": [
        "send", "보내기", "전송", "senden", "delete", "삭제", "löschen", "remove", "제거", "entfernen",
        "buy", "구매", "구입", "kaufen", "pay", "결제", "지불", "bezahlen", "order", "주문", "bestellen",
        "submit", "제출", "post", "게시", "publish", "install", "설치", "uninstall", "format", "포맷",
        "transfer", "송금", "이체", "sign out", "로그아웃", "탈퇴", "unsubscribe",
    ],
    # Web (Stage 3): the agent's own browser. "msedge" (built into Windows) or "chrome".
    "browser_channel": "msedge",
    "browser_executable": "",       # optional: full path to a Chromium-based browser instead
    "browser_visible": True,
    "web_search_engine": "google",  # "google", "naver", "duckduckgo" or "bing"
    "web_page_chars": 4000,         # how much page text the AI reads at a time
    # Spoken when a watched page (watch_page) has something new.
    "watch_announcement": "지켜보던 페이지에 새 내용이 있어요.",
    # The agent refuses to open or read these sites (banking, payments). Add your own.
    "web_blocked_sites": [
        "kbstar.com", "shinhan.com", "wooribank.com", "kebhana.com", "hanabank.com", "nonghyup.com",
        "ibk.co.kr", "kakaobank.com", "toss.im", "tossbank.com", "standardchartered.co.kr", "citibank.co.kr",
        "busanbank.co.kr", "knbank.co.kr", "dgb.co.kr", "kfcc.co.kr", "epostbank.go.kr", "suhyup-bank.com",
        "sparkasse.de", "deutsche-bank.de", "commerzbank.de", "ing.de", "dkb.de", "n26.com", "comdirect.de",
        "postbank.de", "paypal.com",
    ],
    # In these programs, pressing Enter usually sends a message, so it asks you first.
    # Programs whose windows are never captured or controlled (password managers).
    "private_programs": ["1password", "bitwarden", "keepass", "lastpass", "dashlane", "enpass", "nordpass"],
    "messaging_apps": ["kakaotalk", "slack", "discord", "teams", "telegram", "whatsapp", "line",
                       "outlook", "thunderbird", "signal", "wechat", "messenger"],
}


# Settings and brains from earlier versions that no longer exist (removed when loading).
REMOVED_SETTINGS = ("brain_mode", "local_brain", "cloud_brain", "escalate_after_steps", "escalate_after_errors")
REMOVED_BRAINS = ("lmstudio",)  # the local LM Studio model was removed


def load_settings() -> dict:
    """Read settings.json, adding any missing options with their default value."""
    settings = json.loads(json.dumps(DEFAULT_SETTINGS))  # deep copy
    raw = _read_raw_settings()
    if raw is not None:
        # Stage 1 used "model" for Gemini; it is now only used for voice.
        if "model" in raw and "voice_model" not in raw:
            raw["voice_model"] = raw["model"]
        raw.pop("model", None)
        if raw.get("voice_model") == "gemini-flash-latest":  # old default shared the main AI's limit
            raw["voice_model"] = DEFAULT_SETTINGS["voice_model"]
        if raw.get("max_steps_per_command") == 25:  # old default
            raw["max_steps_per_command"] = DEFAULT_SETTINGS["max_steps_per_command"]
        for old_key in REMOVED_SETTINGS:
            raw.pop(old_key, None)
        user_brains = raw.pop("brains", {})
        if not isinstance(user_brains, dict):
            user_brains = {}
        for name in REMOVED_BRAINS:
            user_brains.pop(name, None)
            for key in ("main_brain", "backup_brain"):
                if raw.get(key) == name:
                    raw[key] = DEFAULT_SETTINGS[key]
        settings.update(raw)
        for name, profile in user_brains.items():
            if isinstance(profile, dict):
                settings["brains"][name] = {**settings["brains"].get(name, {}), **profile}
    settings = _repair(settings)
    if settings != _read_raw_settings():
        save_settings(settings)
    return settings


def _read_raw_settings():
    if not SETTINGS_FILE.exists():
        return None
    raw = SETTINGS_FILE.read_bytes()
    try:
        text = raw.decode("utf-8-sig")  # Notepad may add a BOM
    except UnicodeDecodeError:
        text = raw.decode("cp949", errors="replace")  # saved as "ANSI" on Korean Windows
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"settings.json has a typo near line {e.lineno}: {e.msg}. "
            "Fix it, or delete the file to get the defaults back."
        ) from e
    if not isinstance(data, dict):
        raise ValueError("settings.json must start with { and end with }. Delete the file to get the defaults back.")
    return data


def _repair(settings: dict) -> dict:
    """Put back defaults for values with the wrong type (e.g. "brains": null), so a hand edit can't
    stop the agent from starting."""
    for key, default in DEFAULT_SETTINGS.items():
        value = settings.get(key)
        if isinstance(default, bool):
            ok = isinstance(value, bool)
        elif isinstance(default, (int, float)):
            ok = isinstance(value, (int, float)) and not isinstance(value, bool)
        else:
            ok = isinstance(value, type(default))
        if not ok:
            settings[key] = json.loads(json.dumps(default))
    brains = {}
    for name, profile in settings["brains"].items():
        if isinstance(profile, dict) and profile.get("base_url") and profile.get("model"):
            brains[name] = profile
    settings["brains"] = brains or json.loads(json.dumps(DEFAULT_BRAINS))
    return settings


_SAVE_LOCK = threading.Lock()


def save_settings(settings: dict) -> None:
    """Write settings.json in one step (a crash mid-write can't leave a half-written file)."""
    with _SAVE_LOCK:  # the tray, the popup and the agent may save at the same moment
        temp = SETTINGS_FILE.with_name(SETTINGS_FILE.name + ".tmp")
        temp.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temp, SETTINGS_FILE)


def load_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(ENV_FILE)
    except ImportError:
        pass


def get_key(env_name: str) -> str:
    """Read an API key. The .env file wins (it is read fresh, so a key set while the agent runs is used
    right away); a Windows environment variable is the fallback. Returns "" when it isn't set."""
    if not env_name:
        return ""
    key = ""
    try:
        from dotenv import dotenv_values
        key = (dotenv_values(ENV_FILE).get(env_name) or "").strip()
    except Exception:
        pass
    if not key or key.startswith("paste-your"):
        key = os.environ.get(env_name, "").strip()
    return "" if key.startswith("paste-your") else key


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(exist_ok=True)
