"""Starts everything and connects the pieces:

    hotkeys / popup / tray  ->  App  ->  worker thread  ->  Agent (brains + tools)  ->  popup + voice

All commands run one after another on a single worker thread, because Windows UI Automation
(used for screen control) must stay on the thread where it was started.
"""

import logging
import os
import queue
import subprocess
import sys
import threading

from agent import config, safety, texts
from agent.memory import get_memory
from agent.safety import StopSwitch
from agent.texts import t

log = logging.getLogger("agent")
_mutex = None  # keeps the single-instance lock alive


class App:
    def __init__(self, settings: dict):
        from agent.agent import Agent
        from agent.brains import BrainRouter
        from agent.hotkeys import Hotkeys
        from agent.tooling import load_all_tools
        from agent.tools import routines, screen, web, writing
        from agent.transcriber import Transcriber
        from agent.ui import Popup, Tray
        from agent.usage import Usage
        from agent.voice import Recorder, Speaker

        texts.set_language(settings.get("ui_language", "ko"))
        self.settings = settings
        self.stop = StopSwitch()
        self.jobs = queue.Queue()
        self.working = False
        self._geometry_timer = None
        self._failed_watches = set()

        self.brain_choices = [(name, profile.get("label", name)) for name, profile in settings["brains"].items()]
        talk = settings["push_to_talk_hotkey"].upper()
        self.popup = Popup(self.stop, on_send=self.submit_text, on_mic=self.toggle_mic, on_stop=self.press_stop,
                           brains=self._brain_labels(), current_brain=settings["main_brain"],
                           on_brain_change=self.set_main_brain, font_size=int(settings.get("ui_font_size", 10) or 10),
                           geometry=str(settings.get("popup_geometry", "") or ""), on_geometry=self._remember_geometry,
                           talk_key=talk)
        notice = lambda text: self.popup.show("info", text)  # noqa: E731
        self.speaker = Speaker(rate=settings["speech_rate"], on_notice=notice)
        self.recorder = Recorder()
        self.transcriber = Transcriber(config.get_key("GEMINI_API_KEY"), settings["voice_model"], on_notice=notice,
                                       extra_names=lambda: [r.get("name", "") for r in routines.load_routines()])
        self.usage = Usage()
        self.router = BrainRouter(settings, self.usage, on_status=self.popup.status, on_notice=notice)
        self.agent = Agent(settings, self.router, load_all_tools(), get_memory(), ui=self, stop=self.stop)
        screen.configure(settings, hide_popup=self.popup.hide_and_wait)
        web.configure(settings, ask_user=self._ask_user)
        self._screen = screen
        self._web = web
        self._routines = routines
        self._writing = writing

        self.tray = Tray(
            on_open=lambda: self.popup.show_window(focus=True),
            on_new_conversation=self.new_conversation,
            on_settings=self.open_settings,
            on_memory=lambda: _open_file(config.MEMORY_FILE, default="[]"),
            on_log=lambda: _open_file(config.ACTION_LOG_FILE),
            on_quit=self.quit,
            brains=self.brain_choices,
            get_main=lambda: self.settings["main_brain"],
            set_main=self.set_main_brain,
            get_backup=lambda: self.settings.get("backup_brain") or "",
            set_backup=self.set_backup_brain,
            cost_text=self.cost_text,
            get_speak=lambda: bool(self.settings.get("speak_replies")),
            toggle_speak=self.toggle_speak,
            get_engine=lambda: self.settings.get("web_search_engine", "google"),
            set_engine=self.set_search_engine,
            on_api_key=self.open_key_setup,
            on_help=self.show_help,
        )
        self.hotkeys = Hotkeys(settings, on_talk_start=self.start_listening, on_talk_end=self.finish_listening,
                               on_open_popup=lambda: self.popup.show_window(focus=True), on_stop=self.press_stop,
                               on_selection=self.capture_selection)
        threading.Thread(target=self._worker, daemon=True, name="agent-worker").start()
        threading.Thread(target=self._watch_timer, daemon=True, name="watch-timer").start()

        self.popup.show("info", t("welcome", talk=talk, stop=settings["stop_key"].upper(), ai=self.mode_text()))
        main = self.router.brains.get(settings["main_brain"])
        if main is not None and main.missing_key:
            self.popup.show("error", t("needs_key", ai=main.label))
        self.popup.show_window(focus=True)

    # ---------------------------------------------------- what the Agent calls (its "ui")

    def show(self, kind, text):
        self.popup.show(kind, text)

    def status(self, text):
        self.popup.status(text)

    def confirm(self, reason, details="", **options) -> bool:
        return self.popup.confirm(reason, details, **options)

    def speak(self, text):
        self.speaker.speak(text)

    def _ask_user(self, message: str) -> bool:
        """The web tools hand over to you (login, password, CAPTCHA, payment) and wait. The popup does not
        take the keyboard, so you can type in the browser right away."""
        if self.settings.get("speak_replies"):
            self.speaker.speak(message)
        return self.popup.confirm(message, t("your_turn_body"), title=t("your_turn_title"), yes_text=t("done"),
                                  no_text=t("cancel"), focus=False)

    # ---------------------------------------------------- commands

    def submit_text(self, text: str, shown: str = None):
        if self._queue_job(text=text):
            self.popup.show("you", shown or text)

    def _queue_job(self, text=None, audio=None) -> bool:
        if self.working:
            self.popup.show("info", t("busy"))
            return False
        self.speaker.stop()
        self.working = True
        self.jobs.put(("command", text, audio))
        return True

    def _worker(self):
        """Runs every job one after another. The browser and screen reading live on this thread."""
        while True:
            kind, *payload = self.jobs.get()
            if kind == "quit":
                self._web.shutdown()
                payload[0].set()
                return
            if kind == "watch":
                self._run_watch(payload[0])
                continue
            self.tray.set_state("busy")
            self.popup.set_busy(True)
            try:
                if kind == "routine":
                    self.popup.show("info", t("routine_start", name=payload[0]))
                    self.agent.run_recorded_routine(payload[0])
                else:
                    text, audio = payload
                    if audio is not None:
                        text = self._transcribe(audio)
                    if text:
                        self.agent.handle(text)
            except Exception:
                log.exception("Command failed")
                self.popup.show("error", t("unexpected"))
            finally:
                self.working = False
                self.tray.set_state("normal")
                self.tray.refresh_menu()  # cost line
                self.popup.set_busy(False)
                self.popup.status(t("ready"))
                self.popup.show_window(focus=False)  # comes back after screen actions hid it

    def _watch_timer(self):
        """Once a minute: start scheduled routines and page watches that are due (only while idle)."""
        while True:
            threading.Event().wait(60)
            try:
                self._tick()
            except Exception:
                log.exception("Timer failed")

    def _tick(self):
        if self.working or not self.jobs.empty():
            return
        due = self._routines.due_routines()
        if due:
            self._routines.mark_scheduled(due[0]["name"], due[0]["slot"])
            self.working = True
            self.jobs.put(("routine", due[0]["name"]))
            return
        for watch_id in self._web.due_watches():
            self.jobs.put(("watch", watch_id))

    def _run_watch(self, watch_id: int):
        try:
            result = self._web.check_watch(watch_id) or {}
        except Exception as e:
            log.exception("Watch check failed")
            result = {"error": str(e)}
        if result.get("new"):
            self._failed_watches.discard(watch_id)
            self.popup.show("info", t("watch_new", message=result["new"]))
            self.popup.show_window(focus=False)
            self.speaker.speak(self.settings.get("watch_announcement") or t("watch_new", message=""))
        elif result.get("error") and watch_id not in self._failed_watches:
            self._failed_watches.add(watch_id)  # say it once, not every hour
            self.popup.show("error", t("watch_failed", url=result.get("url", ""), error=result["error"]))
        elif not result.get("error"):
            self._failed_watches.discard(watch_id)

    def _transcribe(self, audio: bytes) -> str:
        from agent.brains import BrainError
        self.popup.status(t("recognizing"))
        key = config.get_key("GEMINI_API_KEY")
        if key != self.transcriber.api_key:  # the key was set or changed since the agent started
            self.transcriber.api_key = key
            self.transcriber._client = None
        try:
            text = self.transcriber.transcribe(audio)
        except BrainError as e:
            self.popup.show("error", str(e))
            return ""
        if not text:
            self.popup.show("info", t("didnt_hear"))
            return ""
        self.popup.show("voice", text)
        return text

    # ---------------------------------------------------- selected text

    def capture_selection(self):
        """Selection hotkey: copy the selected text from the app in front and offer quick actions."""
        if self.working:
            self.popup.show("info", t("busy"))
            return

        def work():
            try:
                data = self._writing.capture_selection()
            except Exception as e:
                log.exception("Selection capture failed")
                self.popup.show("error", t("selection_failed", error=e))
                return
            if not data["text"].strip():
                self.popup.show("info", t("no_selection", key=self.settings["selection_hotkey"].upper()))
                self.popup.show_window(focus=False)
                return
            self.popup.show_selection(data["text"], data["window"], self.settings["selection_actions"])

        threading.Thread(target=work, daemon=True, name="selection").start()

    # ---------------------------------------------------- voice

    def start_listening(self, from_button: bool = False):
        if self.working:
            self.popup.show("info", t("busy"))
            return
        self.speaker.stop()
        try:
            self.recorder.start()
        except Exception as e:
            log.exception("Microphone failed")
            self.popup.show("error", t("mic_problem", error=e))
            return
        self.tray.set_state("listening")
        self.popup.set_mic_active(True)
        self.popup.status(t("listening_button") if from_button else t("listening"))
        self.popup.show_window(focus=False)

    def finish_listening(self):
        from agent.voice import SilentRecording
        if not self.recorder.recording:
            return
        try:
            audio = self.recorder.stop()
        except SilentRecording:
            audio = None
            self.popup.show("error", t("silent_mic"))
        else:
            if audio is None:
                self.popup.status(t("too_short"))
        self.tray.set_state("normal")
        self.popup.set_mic_active(False)
        if audio is not None:
            self._queue_job(audio=audio)

    def toggle_mic(self):
        """The Mic button: click to start, click again to send."""
        if self.recorder.recording:
            self.finish_listening()
        else:
            self.start_listening(from_button=True)

    # ---------------------------------------------------- brains, costs, options

    def _brain_labels(self) -> list:
        labels = []
        for name, label in self.brain_choices:
            env = self.settings["brains"][name].get("api_key_env", "")
            labels.append((name, label + (t("no_key_suffix") if env and not config.get_key(env) else "")))
        return labels

    def set_main_brain(self, name: str):
        self._set_brain("main_brain", name)
        self.popup.set_brain(name)

    def set_backup_brain(self, name: str):
        self._set_brain("backup_brain", name)

    def _set_brain(self, key: str, name: str):
        self.settings[key] = name
        config.save_settings(self.settings)
        brain = self.router.brains.get(name)
        self.popup.show("info", t("ai_changed", ai=self.mode_text()))
        if brain is not None and brain.env_missing():
            self.popup.show("error", t("needs_key", ai=brain.label))
        self.tray.refresh_menu()

    def mode_text(self) -> str:
        brains = self.router.brains
        main = brains.get(self.settings["main_brain"])
        backup = brains.get(self.settings.get("backup_brain") or "")
        text = main.label if main else "?"
        return text + ", " + (t("backup", name=backup.label) if backup and backup is not main else t("no_backup"))

    def cost_text(self) -> str:
        spent = self.usage.month_cost()
        if spent == float("inf"):
            spent = 0.0  # the usage file was damaged; the budget check already treats the month as used up
        try:
            budget = float(self.settings.get("cloud_monthly_budget_usd") or 0)
        except (TypeError, ValueError):
            budget = 0.0
        return t("tray_cost", spent=spent, budget=budget, krw=int(round(spent * 1400, -1)))

    def toggle_speak(self):
        self.settings["speak_replies"] = not self.settings.get("speak_replies")
        config.save_settings(self.settings)
        if not self.settings["speak_replies"]:
            self.speaker.stop()
        self.popup.show("info", t("speak_on") if self.settings["speak_replies"] else t("speak_off"))
        self.tray.refresh_menu()

    def set_search_engine(self, engine: str):
        self.settings["web_search_engine"] = engine
        self._web._settings["web_search_engine"] = engine
        config.save_settings(self.settings)
        self.popup.show("info", t("search_engine_set", name=engine))
        self.tray.refresh_menu()

    def open_key_setup(self):
        """Open the API key helper in a console window (it checks the key and saves it to .env)."""
        script = config.ROOT / "setup_key.py"
        try:
            subprocess.Popen([sys.executable.replace("pythonw.exe", "python.exe"), str(script)], cwd=str(config.ROOT),
                             creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
        except Exception as e:
            log.exception("Key setup failed to start")
            self.popup.show("error", str(e))

    def open_settings(self):
        _open_file(config.SETTINGS_FILE)
        self.popup.show("info", t("settings_restart"))

    def show_help(self):
        talk = self.settings["push_to_talk_hotkey"].upper()
        sel = self.settings["selection_hotkey"].upper()
        pop = self.settings["open_popup_hotkey"].upper()
        stop = self.settings["stop_key"].upper()
        help_text = texts.say(
            f"사용법\n"
            f"· 말로 명령: {talk}를 누른 채 말하고 떼세요. (또는 [말하기] 버튼)\n"
            f"· 글로 명령: {pop}로 창을 열고 입력하세요.\n"
            f"· 멈추기: {stop}\n"
            f"· 글 다듬기·번역: 아무 앱에서 글을 선택하고 {sel}\n"
            f"· 위험한 작업(삭제, 전송, 결제 등)은 항상 먼저 물어봐요. 기본 버튼은 [아니요]예요.\n"
            f"· 예: \"다운로드 폴더 정리해줘\", \"메모장 열어서 장보기 목록 적어줘\",\n"
            f"  \"오늘 날씨 검색해줘\", \"이 표를 엑셀로 저장해줘\", \"매일 아침 9시에 뉴스 요약 루틴 만들어줘\"\n"
            f"· 메일과 메시지는 초안만 만들어요. 보내기는 직접 하세요.",
            f"How to use\n"
            f"· Voice: hold {talk}, speak, release. (or the Mic button)\n"
            f"· Text: open the window with {pop} and type.\n"
            f"· Stop: {stop}\n"
            f"· Polish/translate text: select it in any app and press {sel}\n"
            f"· Risky actions (delete, send, pay...) always ask first; the default button is No.\n"
            f"· Examples: \"tidy my Downloads folder\", \"open Notepad and write a shopping list\",\n"
            f"  \"save this table to Excel\", \"make a routine that summarises the news every morning at 9\"\n"
            f"· Emails and messages are drafts only; you send them yourself.",
        )
        self.popup.show("info", help_text)
        self.popup.show_window(focus=True)

    def _remember_geometry(self, geometry: str):
        """Save where you put the popup (a second after you stop moving it)."""
        if self._geometry_timer is not None:
            self._geometry_timer.cancel()

        def save():
            if self.settings.get("popup_geometry") != geometry:
                self.settings["popup_geometry"] = geometry
                try:
                    config.save_settings(self.settings)
                except OSError:
                    pass

        self._geometry_timer = threading.Timer(1.0, save)
        self._geometry_timer.daemon = True
        self._geometry_timer.start()

    # ---------------------------------------------------- misc

    def press_stop(self):
        if self._screen.sent_keys_recently():  # the agent itself pressed Esc inside an app
            return
        self.speaker.stop()
        if self.working:
            self.stop.press()
            self.popup.status(t("stopping"))

    def new_conversation(self):
        self.agent.new_conversation()
        self.popup.show("info", t("new_conversation"))

    def quit(self):
        self.stop.press()
        self.speaker.stop()
        closed = threading.Event()
        self.jobs.put(("quit", closed))  # close the browser cleanly on the worker thread
        closed.wait(5)
        self.hotkeys.remove()
        self.tray.stop()
        self.popup.call(self.popup.root.destroy)

    def run(self):
        self.popup.run()


def _open_file(path, default=""):
    if not path.exists():
        path.parent.mkdir(exist_ok=True)
        path.write_text(default, encoding="utf-8")
    try:
        os.startfile(str(path))
    except OSError:  # no program is set to open this file type (e.g. .json, .jsonl)
        subprocess.Popen(["notepad.exe", str(path)])


def _setup_logging():
    config.ensure_data_dir()
    logging.basicConfig(filename=config.ERROR_LOG_FILE, level=logging.INFO, encoding="utf-8",
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    sys.excepthook = lambda *exc: log.error("Uncaught error", exc_info=exc)
    threading.excepthook = lambda args: log.error("Uncaught error in thread %s", args.thread,
                                                  exc_info=(args.exc_type, args.exc_value, args.exc_traceback))


def _already_running() -> bool:
    global _mutex
    try:
        import win32api
        import win32event
        import winerror
    except ImportError:
        return False
    _mutex = win32event.CreateMutex(None, False, "DesktopAgent.SingleInstance")
    return win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS


def _message_box(text: str, title: str = "Desktop Agent"):
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(title, text)
    root.destroy()


def _make_dpi_aware():
    """Use real screen pixels everywhere, so screenshots, element positions and clicks line up
    (also on high-resolution and multi-monitor setups)."""
    import ctypes
    try:
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):  # per-monitor v2
            return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass


def main():
    _setup_logging()
    if os.name != "nt":
        print("This agent runs on Windows.")
        sys.exit(1)
    if _already_running():
        _message_box("에이전트가 이미 실행 중이에요. 화면 오른쪽 아래 트레이의 보라색 동그라미 아이콘을 찾아보세요.\n"
                     "(안 보이면 작업 표시줄의 ^ 화살표를 누르세요.)\n\n"
                     "The agent is already running. Look for its round icon in the system tray (bottom right).")
        sys.exit(0)
    _make_dpi_aware()
    try:
        settings = config.load_settings()
        config.load_env()
    except ValueError as e:
        _message_box(str(e))
        sys.exit(1)
    safety.set_extra_protected(settings["extra_protected_folders"])
    log.info("Starting; main AI %s, backup %s", settings["main_brain"], settings.get("backup_brain"))
    try:
        app = App(settings)
    except Exception as e:
        log.exception("Startup failed")
        _message_box(f"에이전트를 시작하지 못했어요 / The agent could not start:\n\n{e}\n\n"
                     "check_setup.bat을 실행해서 문제를 찾아보세요. / Run check_setup.bat to find the problem.")
        sys.exit(1)
    app.run()
    os._exit(0)  # make sure background threads (hotkeys, tray) don't keep the program alive
