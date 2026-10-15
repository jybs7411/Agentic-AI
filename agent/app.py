"""Starts everything and connects the pieces:

    hotkeys / popup / tray  ->  App  ->  Agent (Gemini + tools)  ->  popup + voice
"""

import logging
import os
import sys
import threading

from agent import config, safety
from agent.memory import get_memory
from agent.safety import StopSwitch

log = logging.getLogger("agent")
_mutex = None  # keeps the single-instance lock alive


class App:
    def __init__(self, settings: dict, api_key: str):
        from agent.agent import Agent
        from agent.brain import Brain
        from agent.hotkeys import Hotkeys
        from agent.tooling import load_all_tools
        from agent.ui import Popup, Tray
        from agent.voice import Recorder, Speaker

        self.settings = settings
        self.stop = StopSwitch()
        self._run_lock = threading.Lock()

        self.popup = Popup(self.stop, on_send=self.submit_text, on_mic=self.toggle_mic, on_stop=self.press_stop)
        notice = lambda text: self.popup.show("info", text)  # noqa: E731
        self.speaker = Speaker(rate=settings["speech_rate"], on_notice=notice)
        self.recorder = Recorder()
        brain = Brain(api_key, settings["model"], on_status=self.popup.status, on_notice=notice)
        self.agent = Agent(settings, brain, load_all_tools(), get_memory(), ui=self, stop=self.stop)

        self.tray = Tray(
            on_open=lambda: self.popup.show_window(focus=True),
            on_new_conversation=self.new_conversation,
            on_settings=lambda: _open_file(config.SETTINGS_FILE),
            on_memory=lambda: _open_file(config.MEMORY_FILE, default="[]"),
            on_log=lambda: _open_file(config.ACTION_LOG_FILE),
            on_quit=self.quit,
        )
        self.hotkeys = Hotkeys(settings, on_talk_start=self.start_listening, on_talk_end=self.finish_listening,
                               on_open_popup=lambda: self.popup.show_window(focus=True), on_stop=self.press_stop)

        talk = settings["push_to_talk_hotkey"].upper()
        self.popup.show("info", f"Ready. Hold {talk} and speak, or type below. "
                                f"Press {settings['stop_key'].upper()} to stop me. Model: {settings['model']}")
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

    # ---------------------------------------------------- commands

    def submit_text(self, text: str):
        self._start_command(text=text)

    def _start_command(self, text=None, audio=None):
        if not self._run_lock.acquire(blocking=False):
            self.popup.show("info", "Still working on the last command. Press Esc to stop it first.")
            return
        self.speaker.stop()

        def work():
            self.tray.set_state("busy")
            try:
                self.agent.handle(text=text, audio_wav=audio)
            except Exception as e:
                log.exception("Command failed")
                self.popup.show("error", f"Unexpected problem: {e} (details in data/agent.log)")
            finally:
                self.tray.set_state("normal")
                self._run_lock.release()

        threading.Thread(target=work, daemon=True, name="agent").start()

    # ---------------------------------------------------- voice

    def start_listening(self):
        if self.agent.busy:
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
        self.popup.status("Sending your voice...")
        self._start_command(audio=audio)

    def toggle_mic(self):
        """The Mic button: click to start, click again to send."""
        if self.recorder.recording:
            self.finish_listening()
        else:
            self.start_listening()

    # ---------------------------------------------------- misc

    def press_stop(self):
        self.speaker.stop()
        if self.agent.busy:
            self.stop.press()
            self.popup.status("Stopping...")

    def new_conversation(self):
        self.agent.new_conversation()
        self.popup.show("info", "New conversation started.")

    def quit(self):
        self.stop.press()
        self.speaker.stop()
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
    """Makes the popup sharp instead of blurry on high-resolution screens."""
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
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
        api_key = config.load_api_key()
    except ValueError as e:
        _message_box(str(e))
        sys.exit(1)
    safety.set_extra_protected(settings["extra_protected_folders"])
    log.info("Starting with model %s", settings["model"])
    try:
        app = App(settings, api_key)
    except Exception as e:
        log.exception("Startup failed")
        _message_box(f"The agent could not start:\n\n{e}\n\nRun check_setup.bat to find the problem.")
        sys.exit(1)
    app.run()
    os._exit(0)  # make sure background threads (hotkeys, tray) don't keep the program alive
