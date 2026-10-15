"""Setup checker. Run check_setup.bat: it tests each part and says how to fix problems."""

import sys

OK, FAIL, WARN = "[ OK ]", "[실패]", "[주의]"
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
        report(WARN if role == "백업" else FAIL, f"{role} AI {brain.label}: API 키가 없어요",
               f"setup_key.bat 또는 트레이 > API 키 설정으로 {brain.missing_key}를 넣으세요")
        return
    try:
        names = brain.list_models()
        listed = ", ".join(names[:8]) + (" ..." if len(names) > 8 else "")
        report(OK, f"{role} AI {brain.label} 연결됨. 모델: {listed}")
        if names and brain.model not in names and not brain.auto_switch:
            report(WARN, f"모델 '{brain.model}'이(가) 목록에 없어요",
                   f"위 목록의 정확한 이름을 settings.json (brains > {brain.name} > model)에 넣으세요")
    except Exception as e:
        report(FAIL, f"{role} AI {brain.label}에 연결할 수 없어요: {str(e)[:200]}", "키와 인터넷 연결을 확인하세요")
        return
    try:
        reply = brain.chat([{"role": "user", "content": "Set the volume to 30 percent."}], [TEST_TOOL], StopSwitch())
        if reply.tool_calls and reply.tool_calls[0]["name"] == "set_volume":
            report(OK, f"{role} AI가 도구를 쓸 수 있어요 (set_volume {reply.tool_calls[0]['arguments']})")
        else:
            report(WARN, f"{role} AI가 답은 했지만 도구를 쓰지 않았어요: {reply.text[:80]}",
                   "이 모델은 도구 사용이 약할 수 있어요. 다른 모델을 써 보세요")
    except BrainError as e:
        report(FAIL, f"{role} AI 테스트 실패: {e}")


def check_microphone():
    """Record two seconds and look at the loudness, so a muted or blocked microphone is found now."""
    try:
        import numpy as np
        import sounddevice as sd
        name = sd.query_devices(kind="input")["name"]
    except Exception as e:
        report(FAIL, f"마이크를 찾을 수 없어요 ({e})",
               "마이크를 연결하고, 설정 > 개인 정보 > 마이크에서 '데스크톱 앱의 마이크 액세스 허용'을 켜세요")
        return
    print(f"       마이크 '{name}' 테스트: 2초 동안 아무 말이나 해 주세요…")
    try:
        audio = sd.rec(int(2 * 16000), samplerate=16000, channels=1, dtype="int16")
        sd.wait()
        peak = int(np.abs(audio.astype(np.int32)).max())
    except Exception as e:
        report(FAIL, f"마이크 녹음 실패 ({e})", "다른 앱이 마이크를 쓰고 있지 않은지 확인하세요")
        return
    if peak < 300:
        report(FAIL, f"마이크 '{name}'에서 소리가 거의 들리지 않아요 (최대 {peak})",
               "마이크 음소거, Windows 소리 설정의 입력 장치, 개인 정보 > 마이크 권한을 확인하세요")
    else:
        report(OK, f"마이크 '{name}' 작동함 (소리 크기 {peak})")


def main():
    print("\n=== Desktop Agent 설치 확인 ===\n")

    version = sys.version_info
    if version >= (3, 10):
        report(OK, f"Python {version.major}.{version.minor}")
    else:
        report(FAIL, f"Python {version.major}.{version.minor}은(는) 너무 오래됐어요", "Python 3.10 이상을 설치하세요")

    for module, package in [("openai", "openai"), ("google.genai", "google-genai"), ("dotenv", "python-dotenv"),
                            ("keyboard", "keyboard"), ("sounddevice", "sounddevice"), ("numpy", "numpy"),
                            ("pystray", "pystray"), ("PIL", "pillow"), ("psutil", "psutil"),
                            ("win32gui", "pywin32"), ("mss", "mss"), ("uiautomation", "uiautomation"),
                            ("send2trash", "send2trash"), ("pypdf", "pypdf"), ("docx", "python-docx"),
                            ("pyperclip", "pyperclip"), ("screen_brightness_control", "screen-brightness-control"),
                            ("playwright", "playwright"), ("openpyxl", "openpyxl"), ("tzdata", "tzdata")]:
        try:
            __import__(module)
        except Exception as e:
            report(FAIL, f"라이브러리 {package}이(가) 없어요 ({e})", "install.bat을 다시 실행하세요")
    if not problems:
        report(OK, "라이브러리 모두 설치됨")

    from agent import config
    try:
        settings = config.load_settings()
        report(OK, f"settings.json (기본 AI: {settings['main_brain']}, 백업 AI: {settings['backup_brain'] or '없음'})")
    except ValueError as e:
        report(FAIL, str(e))
        return

    from agent.brains import BrainRouter
    from agent.usage import Usage
    router = BrainRouter(settings, Usage())
    main_brain = router.brains.get(settings["main_brain"])
    if main_brain is None:
        report(FAIL, f"main_brain '{settings['main_brain']}'이(가) brains에 없어요", "트레이 메뉴에서 고르세요")
    else:
        check_brain(main_brain, "기본")
    backup = router.brains.get(settings["backup_brain"] or "")
    if backup is not None and backup is not main_brain:
        check_brain(backup, "백업")
    spent = Usage().month_cost()
    report(OK if spent != float("inf") else WARN,
           f"이번 달 유료 AI 사용액: ${spent:.2f} / 예산 ${float(settings['cloud_monthly_budget_usd']):.2f}")

    gemini_key = config.get_key("GEMINI_API_KEY")
    if not gemini_key:
        report(WARN, "GEMINI_API_KEY가 없어서 음성 명령은 안 돼요 (입력은 돼요)",
               "setup_key.bat으로 넣으세요 (무료: https://aistudio.google.com/apikey)")
    else:
        try:
            from agent.transcriber import Transcriber
            models = Transcriber(gemini_key, settings["voice_model"]).available_flash_models()
            report(OK, f"Gemini 음성 인식 준비됨 (모델 {settings['voice_model']}; 예비: {', '.join(models[:4])})")
        except Exception as e:
            report(FAIL, f"Gemini 음성 확인 실패: {str(e)[:200]}", "setup_key.bat으로 키를 다시 넣어 보세요")

    check_microphone()

    try:
        from agent.app import _make_dpi_aware
        _make_dpi_aware()
        import mss
        with mss.mss() as sct:
            sizes = [f"{m['width']}x{m['height']}" for m in sct.monitors[1:]]
        report(OK, f"화면 캡처 작동. 모니터: {', '.join(sizes)}")
        from agent.tools.screen import _target_window, _uia
        _uia()
        target = _target_window()
        report(OK, f"화면 읽기 작동. 앞에 있는 창: {target['title'] if target else '(없음)'}")
    except Exception as e:
        report(FAIL, f"화면 조작 확인 실패: {e}")

    try:
        import tempfile
        from agent.tools import web
        web.PROFILE_DIR = tempfile.mkdtemp(prefix="agent-check-")
        web.configure(dict(settings, browser_visible=False))
        web._page().set_content("<p>ok</p>")
        report(OK, f"에이전트 브라우저 작동 ({settings['browser_channel'] or 'custom'})")
        web.shutdown()
    except Exception as e:
        report(FAIL, f"에이전트 브라우저를 시작할 수 없어요: {str(e)[:250]}",
               'settings.json의 "browser_channel"을 "chrome" 또는 "msedge"로 바꾸거나, '
               ".venv\\Scripts\\python -m playwright install chromium 실행 후 browser_channel을 \"\"로 두세요")

    try:
        from agent.voice import list_voices
        voices = list_voices()
        report(OK, "Windows 음성: " + ("; ".join(voices) or "없음"))
        cultures = {v.rsplit("|", 1)[-1].strip() for v in voices}
        if "ko-KR" not in cultures:
            report(WARN, "한국어 음성이 없어서 한국어 답변을 소리로 읽어 줄 수 없어요",
                   "설정 > 시간 및 언어 > 음성 > 음성 추가에서 '한국어'를 설치하세요 (README '음성 추가' 참고)")
    except Exception as e:
        report(WARN, f"음성 목록을 가져오지 못했어요 ({e})")

    print()
    if problems:
        print(f"문제 {problems}개를 찾았어요. 위의 [실패] 줄을 고친 뒤 다시 확인하세요.")
    else:
        print("모두 정상이에요. start.bat 또는 바탕화면의 'Desktop Agent'로 시작하세요.")
    print()


if __name__ == "__main__":
    main()
