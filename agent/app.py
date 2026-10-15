"""Starts everything and connects the pieces:

    hotkeys / popup / tray  ->  App  ->  worker thread  ->  Agent (brains + tools)  ->  popup + voice

All commands run one after another on a single worker thread, because Windows UI Automation
(used for screen control) must stay on the thread where it was started.
"""

import logging
import os
import queue
import sys
import threading

from agent import config, safety
from agent.memory import get_memory
from agent.safety import StopSwitch

log = logging.getLogger("agent")
_mutex = None  # keeps the single-instance lock alive


class App:
    def __init__(self, settings: dict):
        from agent.agent import Agent
        from agent.brains import BrainRouter
        from agent.hotkeys import Hotkeys
        from agent.tooling import load_all_tools
        from agent.tools import screen, web
        from agent.transcriber import Transcriber
        from agent.ui import Popup, Tray
        from agent.usage import Usage
        from agent.voice import Recorder, Speaker

        self.settings = settings
        self.stop = StopSwitch()
        self.jobs = queue.Queue()
        self.working = False

        brain_choices = [(name, profile.get("label", name)) for name, profile in settings["brains"].items()]
        self.popup = Popup(self.stop, on_send=self.submit_text, on_mic=self.toggle_mic, on_stop=self.press_stop,
                           brains=brain_choices, current_brain=settings["main_brain"],
                           on_brain_change=self.set_main_brain)
        notice = lambda text: self.popup.show("info", text)  # noqa: E731
        self.speaker = Speaker(rate=settings["speech_rate"], on_notice=notice)
        self.recorder = Recorder()
        self.transcriber = Transcriber(config.get_key("GEMINI_API_KEY"), settings["voice_model"], on_notice=notice)
        self.usage = Usage()
        self.router = BrainRouter(settings, self.usage, on_status=self.popup.status, on_notice=notice)
        self.agent = Agent(settings, self.router, load_all_tools(), get_memory(), ui=self, stop=self.stop)
        screen.configure(settings, hide_popup=self.popup.hide_and_wait)
        web.configure(settings, ask_user=self._ask_user)
        self._screen = screen
        self._web = web

        self.tray = Tray(
            on_open=lambda: self.popup.show_window(focus=True),
            on_new_conversation=self.new_conversation,
            on_settings=lambda: _open_file(config.SETTINGS_FILE),
            on_memory=lambda: _open_file(config.MEMORY_FILE, default="[]"),
            on_log=lambda: _open_file(config.ACTION_LOG_FILE),
            on_quit=self.quit,
            brains=brain_choices,
            get_main=lambda: self.settings["main_brain"],
            set_main=self.set_main_brain,
            get_backup=lambda: self.settings.get("backup_brain") or "",
            set_backup=self.set_backup_brain,
            cost_text=self.cost_text,
        )
        self.hotkeys = Hotkeys(settings, on_talk_start=self.start_listening, on_talk_end=self.finish_listening,
                               on_open_popup=lambda: self.popup.show_window(focus=True), on_stop=self.press_stop)
        threading.Thread(target=self._worker, daemon=True, name="agent-worker").start()
        threading.Thread(target=self._watch_timer, daemon=True, name="watch-timer").start()

        talk = settings["push_to_talk_hotkey"].upper()
        self.popup.show("info", f"Ready. Hold {talk} and speak, or type below. "
                                f"Press {settings['stop_key'].upper()} to stop me. AI: {self.mode_text()}")
        self.popup.show_window(focus=True)

    # ---------------------------------------------------- what the Agent calls (its "ui")

    def show(self, kind, text):
        self.popup.show(kind, text)

    def status(self, text):
        self.popup.status(text)

    def confirm(self, reason, described) -> bool:
        return self.popup.confirm(reason, described)

    def speak(self, text):
        self.speaker.speak(text)

    def _ask_user(self, message: str) -> bool:
        """The web tools hand over to you (login, password, CAPTCHA, payment) and wait."""
        self.speaker.speak(message)
        return self.popup.confirm(message, "When you are finished in the browser, click Done.",
                                  title="Your turn", yes_text="Done", no_text="Cancel")

    # ---------------------------------------------------- commands

    def submit_text(self, text: str):
        self._queue_job(text=text)

    def _queue_job(self, text=None, audio=None):
        if self.working:
            self.popup.show("info", "Still working on the last command. Press Esc to stop it first.")
            return
        self.speaker.stop()
        self.working = True
        self.jobs.put(("command", text, audio))

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
            text, audio = payload
            self.tray.set_state("busy")
            try:
                if audio is not None:
                    text = self._transcribe(audio)
                if text:
                    self.agent.handle(text)
            except Exception as e:
                log.exception("Command failed")
                self.popup.show("error", f"Unexpected problem: {e} (details in data/agent.log)")
            finally:
                self.working = False
                self.tray.set_state("normal")
                self.popup.status("Ready")
                self.popup.show_window(focus=False)  # comes back after screen actions hid it

    def _watch_timer(self):
        """Once a minute, queue checks for watched pages that are due (only while idle)."""
        while True:
            threading.Event().wait(60)
            if self.working or not self.jobs.empty():
                continue
            try:
                for watch_id in self._web.due_watches():
                    self.jobs.put(("watch", watch_id))
            except Exception:
                log.exception("Watch timer failed")

    def _run_watch(self, watch_id: int):
        try:
            message = self._web.check_watch(watch_id)
        except Exception as e:
            log.exception("Watch check failed")
            message = None
            self.popup.show("error", f"Page watch failed: {e}")
        if message:
            self.popup.show("info", f"[Watch] {message}")
            self.popup.show_window(focus=False)
            self.speaker.speak(self.settings.get("watch_announcement", "New content on a watched page."))

    def _transcribe(self, audio: bytes) -> str:
        from agent.brains import BrainError
        self.popup.status("Recognizing speech...")
        try:
            text = self.transcriber.transcribe(audio)
        except BrainError as e:
            self.popup.show("error", str(e))
            return ""
        if not text:
            self.popup.show("info", "I didn't catch that. Try again, a bit closer to the microphone.")
            return ""
        self.popup.show("info", f"(voice) {text}")
        return text

    # ---------------------------------------------------- voice

    def start_listening(self):
        if self.working:
            self.popup.show("info", "Still working on the last command. Press Esc to stop it first.")
            return
        self.speaker.stop()
        try:
            self.recorder.start()
        except Exception as e:
            self.popup.show("error", f"Microphone problem: {e}")
            return
        self.tray.set_state("listening")
        self.popup.set_mic_active(True)
        self.popup.status("Listening... release to send")
        self.popup.show_window(focus=False)

    def finish_listening(self):
        if not self.recorder.recording:
            return
        audio = self.recorder.stop()
        self.tray.set_state("normal")
        self.popup.set_mic_active(False)
        if audio is None:
            self.popup.status("Too short - hold the keys while you speak")
            return
        self._queue_job(audio=audio)

    def toggle_mic(self):
        """The Mic button: click to start, click again to send."""
        if self.recorder.recording:
            self.finish_listening()
        else:
            self.start_listening()

    # ---------------------------------------------------- brains and costs

    def set_main_brain(self, name: str):
        self._set_brain("main_brain", name)
        self.popup.set_brain(name)

    def set_backup_brain(self, name: str):
        self._set_brain("backup_brain", name)

    def _set_brain(self, key: str, name: str):
        self.settings[key] = name
        config.save_settings(self.settings)
        brain = self.router.brains.get(name)
        self.popup.show("info", f"AI: {self.mode_text()}")
        if brain is not None and brain.missing_key:
            self.popup.show("error", f"{brain.label} needs an API key: put {brain.missing_key}=... in the .env "
                                     "file, then restart the agent.")
        self.tray.set_state("normal")  # refresh the tray menu

    def mode_text(self) -> str:
        brains = self.router.brains
        main = brains.get(self.settings["main_brain"])
        backup = brains.get(self.settings.get("backup_brain") or "")
        text = main.label if main else "?"
        return text + (f", backup: {backup.label}" if backup and backup is not main else ", no backup")

    def cost_text(self) -> str:
        spent = self.usage.month_cost()
        return f"Cloud this month: ${spent:.2f} / ${float(self.settings['cloud_monthly_budget_usd']):.2f}"

    # ---------------------------------------------------- misc

    def press_stop(self):
        if self._screen.sent_keys_recently():  # the agent itself pressed Esc inside an app
            return
        self.speaker.stop()
        if self.working:
            self.stop.press()
            self.popup.status("Stopping...")

    def new_conversation(self):
        self.agent.new_conversation()
        self.popup.show("info", "New conversation started.")

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
    os.startfile(str(path))


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
        _message_box("The agent is already running. Look for its round icon in the system tray (bottom right).")
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
        _message_box(f"The agent could not start:\n\n{e}\n\nRun check_setup.bat to find the problem.")
        sys.exit(1)
    app.run()
    os._exit(0)  # make sure background threads (hotkeys, tray) don't keep the program alive
