"""Setup checker. Run check_setup.bat: it tests each part and says how to fix problems."""

import sys

OK, FAIL, WARN = "[ OK ]", "[FAIL]", "[WARN]"
problems = 0


def report(status, message, fix=None):
    global problems
    if status == FAIL:
        problems += 1
    print(f"{status} {message}")
    if fix:
        print(f"       -> {fix}")


def main():
    print("\n=== Desktop Agent setup check ===\n")

    # 1. Python
    version = sys.version_info
    if version >= (3, 10):
        report(OK, f"Python {version.major}.{version.minor}")
    else:
        report(FAIL, f"Python {version.major}.{version.minor} is too old", "Install Python 3.10 or newer from python.org")

    # 2. Libraries
    for module, package in [("google.genai", "google-genai"), ("dotenv", "python-dotenv"), ("keyboard", "keyboard"),
                            ("sounddevice", "sounddevice"), ("numpy", "numpy"), ("pystray", "pystray"),
                            ("PIL", "pillow"), ("psutil", "psutil"), ("win32gui", "pywin32"),
                            ("send2trash", "send2trash"), ("pypdf", "pypdf"), ("docx", "python-docx"),
                            ("pyperclip", "pyperclip"), ("screen_brightness_control", "screen-brightness-control")]:
        try:
            __import__(module)
            report(OK, f"Library {package}")
        except Exception as e:
            report(FAIL, f"Library {package} is missing ({e})", "Run install.bat again")

    # 3. Settings and API key
    from agent import config
    try:
        settings = config.load_settings()
        report(OK, f"settings.json (model: {settings['model']})")
    except ValueError as e:
        report(FAIL, str(e))
        settings = dict(config.DEFAULT_SETTINGS)
    api_key = None
    try:
        api_key = config.load_api_key()
        report(OK, "Gemini API key found in .env")
    except ValueError as e:
        report(FAIL, str(e), "Get a key at https://aistudio.google.com/apikey")

    # 4. Gemini connection
    if api_key:
        from agent.brain import Brain, BrainError
        from agent.safety import StopSwitch
        brain = Brain(api_key, settings["model"], on_notice=lambda t: report(WARN, t))
        try:
            models = brain.available_flash_models()
            report(OK, f"Connected to Gemini. Flash models available: {', '.join(models[:6]) or 'none'}")
        except Exception as e:
            report(FAIL, f"Could not list models: {e}", "Check the API key and your internet connection")
        try:
            response = brain.generate("Reply with only the word OK.", "You are a test.", [], StopSwitch())
            report(OK, f"Model '{brain.model}' answered: {(response.text or '').strip()[:40]}")
            if brain.model != settings["model"]:
                report(WARN, f"Your settings say '{settings['model']}' but '{brain.model}' worked.",
                       f"Put \"model\": \"{brain.model}\" in settings.json")
        except BrainError as e:
            report(FAIL, f"Test request failed: {e}")

    # 5. Microphone
    try:
        import sounddevice as sd
        device = sd.query_devices(kind="input")
        report(OK, f"Microphone: {device['name']}")
    except Exception as e:
        report(FAIL, f"No microphone found ({e})",
               "Plug in a microphone, and check Settings > Privacy > Microphone allows desktop apps")

    # 6. Voices
    try:
        from agent.voice import list_voices
        voices = list_voices()
        report(OK, "Windows voices: " + ("; ".join(voices) or "none"))
        for culture, language in [("ko-KR", "Korean"), ("de-DE", "German"), ("en-", "English")]:
            if not any(culture in v for v in voices):
                report(WARN, f"No {language} voice found, so {language} replies will not be spoken",
                       "See README > 'Voices'")
    except Exception as e:
        report(WARN, f"Could not list voices ({e})")

    print()
    if problems:
        print(f"{problems} problem(s) found. Fix the [FAIL] lines above, then run this check again.")
    else:
        print("Everything looks good. Start the agent with start.bat")
    print()


if __name__ == "__main__":
    main()
