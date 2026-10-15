"""The App wiring (agent/app.py), with the Windows-only parts (popup, tray, hotkeys, microphone) replaced
by fakes. Checks that the App talks to the popup and tray with arguments they really accept, and that
commands, routines and page watches flow through the worker thread."""

import ast
import sys
import time
import types
from pathlib import Path

import pytest

from agent import config, texts
from agent import memory as memory_module
from agent.texts import t
from agent.tools import routines, web

UI_FILE = Path(__file__).resolve().parent.parent / "agent" / "ui.py"


def _init_params(class_name: str) -> set:
    """Parameter names of ui.<class_name>.__init__, read from the source (tkinter may be missing here)."""
    tree = ast.parse(UI_FILE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    return {a.arg for a in item.args.args[1:] + item.args.kwonlyargs}
    raise AssertionError(class_name)


def _public_methods(class_name: str) -> set:
    tree = ast.parse(UI_FILE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {item.name for item in node.body if isinstance(item, ast.FunctionDef)}
    raise AssertionError(class_name)


class FakePopup:
    def __init__(self, stop, **kwargs):
        self.kwargs = kwargs
        self.shown = []
        self.statuses = []
        self.busy = []
        self.confirms = []
        self.root = types.SimpleNamespace(destroy=lambda: None)

    def show(self, kind, text):
        self.shown.append((kind, text))

    def status(self, text):
        self.statuses.append(text)

    def set_busy(self, busy):
        self.busy.append(busy)

    def confirm(self, reason, details="", **options):
        self.confirms.append((reason, details, options))
        return True

    def set_brain(self, name):
        pass

    def set_mic_active(self, active):
        pass

    def show_selection(self, *args):
        pass

    def show_window(self, focus=False):
        pass

    def hide_and_wait(self):
        pass

    def call(self, fn, *args):
        fn(*args)

    def run(self):
        pass


class FakeTray:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.refreshed = 0

    def set_state(self, state):
        pass

    def refresh_menu(self):
        self.refreshed += 1

    def stop(self):
        pass


class FakeHotkeys:
    def __init__(self, settings, **kwargs):
        self.kwargs = kwargs

    def remove(self):
        pass


class FakeSpeaker:
    def __init__(self, rate=0, on_notice=None):
        self.spoken = []

    def speak(self, text):
        self.spoken.append(text)

    def stop(self):
        pass


class FakeAgent:
    def __init__(self):
        self.handled = []
        self.routines = []

    def handle(self, text, unattended=False):
        self.handled.append((text, unattended))

    def run_recorded_routine(self, name):
        self.routines.append(name)

    def new_conversation(self):
        pass


@pytest.fixture
def app(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(config, "DATA_DIR", data)
    monkeypatch.setattr(config, "MEMORY_FILE", data / "memory.json")
    monkeypatch.setattr(config, "USAGE_FILE", data / "usage.json")
    monkeypatch.setattr(config, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setattr(memory_module, "_instance", None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    fake_ui = types.ModuleType("agent.ui")
    fake_ui.Popup, fake_ui.Tray = FakePopup, FakeTray
    monkeypatch.setitem(sys.modules, "agent.ui", fake_ui)
    import agent.hotkeys
    import agent.voice
    monkeypatch.setattr(agent.hotkeys, "Hotkeys", FakeHotkeys)
    monkeypatch.setattr(agent.voice, "Speaker", FakeSpeaker)

    from agent.app import App
    settings = config.load_settings()
    instance = App(settings)
    instance.agent = FakeAgent()
    yield instance
    texts.set_language("ko")


def _wait_until_idle(app, timeout=3.0):
    end = time.time() + timeout
    while (app.working or not app.jobs.empty()) and time.time() < end:
        time.sleep(0.02)
    time.sleep(0.05)


def test_app_passes_only_arguments_the_real_popup_and_tray_accept(app):
    assert set(app.popup.kwargs) <= _init_params("Popup")
    assert set(app.tray.kwargs) == _init_params("Tray")  # every tray callback is wired
    popup_methods = _public_methods("Popup")
    for used in ("show", "status", "set_busy", "confirm", "set_brain", "set_mic_active", "show_selection",
                 "show_window", "hide_and_wait", "call", "run"):
        assert used in popup_methods
    assert {"set_state", "refresh_menu", "stop"} <= _public_methods("Tray")


def test_welcome_and_missing_key_are_shown(app):
    assert app.popup.shown[0][0] == "info"
    assert t("needs_key", ai="Gemini (Google)") in [text for _, text in app.popup.shown]
    labels = dict(app.popup.kwargs["brains"])
    assert labels["gemini"].endswith(t("no_key_suffix"))


def test_typed_command_runs_on_the_worker(app):
    app.submit_text("메모장 열어줘", shown="[다듬기]")
    _wait_until_idle(app)
    assert ("you", "[다듬기]") in app.popup.shown
    assert app.agent.handled == [("메모장 열어줘", False)]
    assert app.popup.busy[-1] is False and app.tray.refreshed >= 1


def test_second_command_while_busy_is_refused(app):
    app.working = True
    app.submit_text("again")
    assert ("info", t("busy")) in app.popup.shown
    assert app.jobs.empty()


def test_scheduled_routine_is_started_and_marked(app, monkeypatch):
    monkeypatch.setattr(routines, "due_routines", lambda: [{"name": "아침 뉴스", "slot": "2026-10-15T09:00"}])
    marked = []
    monkeypatch.setattr(routines, "mark_scheduled", lambda name, slot: marked.append((name, slot)))
    app._tick()
    _wait_until_idle(app)
    assert marked == [("아침 뉴스", "2026-10-15T09:00")]
    assert app.agent.routines == ["아침 뉴스"]


def test_watch_news_is_announced_and_errors_are_reported_once(app, monkeypatch):
    monkeypatch.setattr(web, "check_watch", lambda watch_id: {"new": "새 글 2개"})
    app._run_watch(1)
    assert ("info", t("watch_new", message="새 글 2개")) in app.popup.shown
    assert app.speaker.spoken

    monkeypatch.setattr(web, "check_watch", lambda watch_id: {"error": "timeout", "url": "https://example.com"})
    before = len(app.popup.shown)
    app._run_watch(2)
    app._run_watch(2)
    errors = [s for s in app.popup.shown[before:] if s[0] == "error"]
    assert len(errors) == 1 and "example.com" in errors[0][1]


def test_your_turn_does_not_steal_the_keyboard(app):
    assert app._ask_user("로그인해 주세요") is True
    reason, details, options = app.popup.confirms[-1]
    assert options["focus"] is False and options["yes_text"] == t("done")


def test_tray_options_are_saved(app, monkeypatch):
    monkeypatch.setitem(web._settings, "web_search_engine", web._settings.get("web_search_engine", "google"))
    was = app.settings["speak_replies"]
    app.toggle_speak()
    assert app.settings["speak_replies"] is (not was)
    app.set_search_engine("naver")
    assert web._settings["web_search_engine"] == "naver"
    saved = config.load_settings()
    assert saved["web_search_engine"] == "naver" and saved["speak_replies"] is (not was)
    assert "$0.00" in app.cost_text()


def test_popup_position_is_saved_once_moving_stops(app):
    for x in range(5):
        app._remember_geometry(f"460x600+{x}+10")
    deadline = time.time() + 3
    while time.time() < deadline and config.load_settings().get("popup_geometry") != "460x600+4+10":
        time.sleep(0.1)
    assert config.load_settings()["popup_geometry"] == "460x600+4+10"


def test_key_set_while_running_is_picked_up(app):
    config.ENV_FILE.write_text("GEMINI_API_KEY=AIza-new-key-1234567890\n", encoding="utf-8")
    assert app.router.brains["gemini"].env_missing() is False
