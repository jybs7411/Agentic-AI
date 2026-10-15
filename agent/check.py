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


TEST_TOOL = {"type": "function", "function": {
    "name": "set_volume", "description": "Set the speaker volume (0-100).",
    "parameters": {"type": "object", "properties": {"percent": {"type": "integer"}}, "required": ["percent"]}}}


def check_brain(brain, role: str):
    """Ask the brain to use a tool once: proves it's reachable AND can do function calling."""
    from agent.brains import BrainError
    from agent.safety import StopSwitch
    if brain.missing_key:
        report(WARN if role == "cloud" else FAIL, f"{role} brain {brain.label}: no API key",
               f"Put {brain.missing_key}=your-key in the .env file")
        return
    try:
        names = brain.list_models()
        listed = ", ".join(names[:8]) + (" ..." if len(names) > 8 else "")
        report(OK, f"{role} brain {brain.label} reachable. Models: {listed}")
        if names and brain.model not in names:
            report(WARN, f"Model '{brain.model}' is not in that list",
                   "Copy the exact name from the list into settings.json (brains > "
                   f"{brain.name} > model)")
    except Exception as e:
        hint = ("Open LM Studio > Developer tab > load your model > Start Server"
                if brain.is_local else "Check the key and your internet connection")
        report(FAIL, f"{role} brain {brain.label} not reachable: {str(e)[:200]}", hint)
        return
    try:
        reply = brain.chat([{"role": "user", "content": "Set the volume to 30 percent."}], [TEST_TOOL], StopSwitch())
        if reply.tool_calls and reply.tool_calls[0]["name"] == "set_volume":
            report(OK, f"{role} brain can use tools (asked for set_volume {reply.tool_calls[0]['arguments']})")
        else:
            report(WARN, f"{role} brain answered but did not use the tool: {reply.text[:80]}",
                   "This model may be weak at tool use; try another model")
    except BrainError as e:
        report(FAIL, f"{role} brain test failed: {e}")


def main():
    print("\n=== Desktop Agent setup check ===\n")

    version = sys.version_info
    if version >= (3, 10):
        report(OK, f"Python {version.major}.{version.minor}")
    else:
        report(FAIL, f"Python {version.major}.{version.minor} is too old", "Install Python 3.10 or newer")

    for module, package in [("openai", "openai"), ("google.genai", "google-genai"), ("dotenv", "python-dotenv"),
                            ("keyboard", "keyboard"), ("sounddevice", "sounddevice"), ("numpy", "numpy"),
                            ("pystray", "pystray"), ("PIL", "pillow"), ("psutil", "psutil"),
                            ("win32gui", "pywin32"), ("mss", "mss"), ("uiautomation", "uiautomation"),
                            ("send2trash", "send2trash"), ("pypdf", "pypdf"), ("docx", "python-docx"),
                            ("pyperclip", "pyperclip"), ("screen_brightness_control", "screen-brightness-control"),
                            ("playwright", "playwright"), ("openpyxl", "openpyxl")]:
        try:
            __import__(module)
        except Exception as e:
            report(FAIL, f"Library {package} is missing ({e})", "Run install.bat again")
    if not problems:
        report(OK, "All libraries installed")

    from agent import config
    try:
        settings = config.load_settings()
        report(OK, f"settings.json (brain mode: {settings['brain_mode']}, local: {settings['local_brain']}, "
                   f"cloud: {settings['cloud_brain']})")
    except ValueError as e:
        report(FAIL, str(e))
        return

    from agent.brains import BrainRouter
    from agent.usage import Usage
    router = BrainRouter(settings, Usage())
    if settings["brain_mode"] in ("auto", "local"):
        check_brain(router.brains[settings["local_brain"]], "local")
    if settings["brain_mode"] in ("auto", "cloud"):
        check_brain(router.brains[settings["cloud_brain"]], "cloud")
    report(OK, f"Cloud spending this month: ${Usage().month_cost():.2f} of "
               f"${float(settings['cloud_monthly_budget_usd']):.2f} budget")

    gemini_key = config.get_key("GEMINI_API_KEY")
    if not gemini_key:
        report(WARN, "No GEMINI_API_KEY: voice commands won't work (typing still does)",
               "Put GEMINI_API_KEY=your-key in .env (free at https://aistudio.google.com/apikey)")
    else:
        try:
            from agent.transcriber import Transcriber
            models = Transcriber(gemini_key, settings["voice_model"]).available_flash_models()
            report(OK, f"Gemini voice ready (model {settings['voice_model']}; backups: {', '.join(models[:4])})")
        except Exception as e:
            report(FAIL, f"Gemini voice check failed: {str(e)[:200]}", "Check GEMINI_API_KEY in .env")

    try:
        import sounddevice as sd
        report(OK, f"Microphone: {sd.query_devices(kind='input')['name']}")
    except Exception as e:
        report(FAIL, f"No microphone found ({e})",
               "Plug in a microphone, and check Settings > Privacy > Microphone allows desktop apps")

    try:
        from agent.app import _make_dpi_aware
        _make_dpi_aware()
        import mss
        with mss.mss() as sct:
            sizes = [f"{m['width']}x{m['height']}" for m in sct.monitors[1:]]
        report(OK, f"Screen capture works. Monitors: {', '.join(sizes)}")
        from agent.tools.screen import _target_window, _uia
        _uia()
        target = _target_window()
        report(OK, f"Screen reading works. Front window: {target['title'] if target else '(none)'}")
    except Exception as e:
        report(FAIL, f"Screen control check failed: {e}")

    try:
        import tempfile
        from agent.tools import web
        web.PROFILE_DIR = tempfile.mkdtemp(prefix="agent-check-")
        web.configure(dict(settings, browser_visible=False))
        web._page().set_content("<p>ok</p>")
        report(OK, f"Agent browser works ({settings['browser_channel'] or 'custom'})")
        web.shutdown()
    except Exception as e:
        report(FAIL, f"Agent browser could not start: {str(e)[:250]}",
               'Set "browser_channel" to "chrome" or "msedge" in settings.json, or run: '
               ".venv\\Scripts\\python -m playwright install chromium  and set browser_channel to \"\"")

    try:
        from agent.voice import list_voices
        voices = list_voices()
        report(OK, "Windows voices: " + ("; ".join(voices) or "none"))
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
