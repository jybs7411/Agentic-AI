"""Tests that run without Windows, a microphone or API keys (the AI is simulated).

Run:  .venv\\Scripts\\python -m pytest tests
"""

import json

import pytest

from agent import config
from agent import memory as memory_module
from agent.agent import Agent, _keep_latest_image
from agent.brains import Brain, BrainUnavailable, Reply, clean_text, parse_arguments, without_images
from agent.safety import ActionLog, StopSwitch, is_protected
from agent.tooling import load_all_tools
from agent.tools import screen
from agent.usage import Usage
from agent.texts import t
from agent.voice import clean_for_speech, detect_language

TOOLS = load_all_tools()


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    data = tmp_path / "agent-data"
    data.mkdir()
    monkeypatch.setattr(config, "UNDO_FILE", data / "undo.json")
    monkeypatch.setattr(config, "MEMORY_FILE", data / "memory.json")
    monkeypatch.setattr(config, "USAGE_FILE", data / "usage.json")
    monkeypatch.setattr(config, "SETTINGS_FILE", data / "settings.json")
    monkeypatch.setattr(memory_module, "_instance", None)
    screen.configure(config.DEFAULT_SETTINGS)
    return data


# ---------------------------------------------------------------- tool registry

def test_every_tool_has_a_complete_schema():
    for tool in TOOLS.values():
        fn = tool.schema()["function"]
        assert fn["description"], f"{tool.name} has no description"
        for arg, prop in fn["parameters"]["properties"].items():
            assert prop.get("description"), f"{tool.name}.{arg} has no description"
            assert prop["type"] in ("string", "integer", "number", "boolean", "array", "object")


def test_list_argument_schema():
    props = TOOLS["move_many"].schema()["function"]["parameters"]["properties"]
    assert props["sources"]["type"] == "array" and props["sources"]["items"] == {"type": "string"}


def test_small_model_type_slips_are_fixed():
    assert TOOLS["set_volume"].coerce({"percent": "30", "bogus": 1}) == {"percent": 30}
    assert TOOLS["list_folder"].coerce({"path": "C:\\", "show_hidden": "true"})["show_hidden"] is True


def test_expected_tools_exist():
    for name in ["find_files", "move_many", "delete_item", "undo_last_moves", "open_app", "close_window",
                 "run_command", "remember", "look_at_screen", "click_element", "find_and_click",
                 "type_into_element", "press_keys", "click_at", "read_screen_text", "scroll"]:
        assert name in TOOLS


# ---------------------------------------------------------------- risk rules

def test_file_risk_rules(tmp_path):
    existing = tmp_path / "a.txt"
    existing.write_text("x")
    assert TOOLS["delete_item"].risk_reason({"path": str(existing)})
    assert TOOLS["run_command"].risk_reason({"command": "dir"})
    assert TOOLS["list_folder"].risk_reason({"path": str(tmp_path)}) is None
    assert TOOLS["move_item"].risk_reason({"source": str(existing), "destination": str(tmp_path / "b.txt")}) is None
    assert TOOLS["write_text_file"].risk_reason({"path": str(existing), "content": "y", "overwrite": True})
    assert TOOLS["open_path"].risk_reason({"path": str(tmp_path / "setup.exe")})
    assert TOOLS["open_path"].risk_reason({"path": str(tmp_path / "photo.jpg")}) is None
    assert TOOLS["power_action"].risk_reason({"action": "cancel"}) is None
    many = [str(tmp_path / f"f{i}") for i in range(30)]
    assert TOOLS["move_many"].risk_reason({"sources": many, "destination_folder": str(tmp_path / "x")})


def test_screen_risk_rules(monkeypatch):
    screen._state["elements"] = {1: {"type": "Button", "name": "보내기", "value": "", "enabled": True, "rect": (0, 0, 9, 9)},
                                 2: {"type": "Button", "name": "Bold", "value": "", "enabled": True, "rect": (0, 0, 9, 9)}}
    assert TOOLS["click_element"].risk_reason({"number": "1"})
    assert TOOLS["click_element"].risk_reason({"number": 2}) is None
    assert TOOLS["find_and_click"].risk_reason({"name": "Delete"})
    assert TOOLS["press_keys"].risk_reason({"keys": "Alt + F4"})
    monkeypatch.setattr(screen, "_target_window", lambda: {"program": "KakaoTalk.exe"})
    assert TOOLS["press_keys"].risk_reason({"keys": "enter"})
    assert TOOLS["type_text"].risk_reason({"text": "hi", "press_enter": True})
    assert TOOLS["type_text"].risk_reason({"text": "hi"}) is None
    monkeypatch.setattr(screen, "_target_window", lambda: {"program": "notepad.exe"})
    assert TOOLS["press_keys"].risk_reason({"keys": "enter"}) is None


def test_agent_folder_and_drive_root_are_protected():
    assert is_protected(config.ROOT / "agent" / "app.py")
    assert is_protected("/")


# ---------------------------------------------------------------- file tools

def test_move_many_and_undo(tmp_path):
    files = []
    for name in ["a.pdf", "b.pdf"]:
        f = tmp_path / name
        f.write_text(name)
        files.append(str(f))
    result = TOOLS["move_many"].call({"sources": files, "destination_folder": str(tmp_path / "PDFs")})
    assert result["moved"] == 2
    undo = TOOLS["undo_last_moves"].call({"operations": 1})
    assert len(undo["restored"]) == 2
    assert (tmp_path / "a.pdf").exists() and not (tmp_path / "PDFs" / "a.pdf").exists()


def test_move_into_new_folder_keeps_file_name(tmp_path):
    (tmp_path / "report.pdf").write_text("x")
    result = TOOLS["move_item"].call({"source": str(tmp_path / "report.pdf"), "destination": str(tmp_path / "Archive")})
    assert result["to"] == str(tmp_path / "Archive" / "report.pdf")


def test_rename_refuses_existing_target(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    assert "error" in TOOLS["rename_item"].call({"path": str(tmp_path / "a.txt"), "new_name": "b.txt"})
    assert (tmp_path / "b.txt").read_text() == "b"


def test_find_and_read_korean(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "보고서.txt").write_text("한국어 내용", encoding="cp949")
    found = TOOLS["find_files"].call({"name_pattern": "보고서", "folder": str(tmp_path)})
    assert found["count"] == 1
    assert TOOLS["read_file"].call({"path": found["results"][0]["path"]})["content"] == "한국어 내용"


# ---------------------------------------------------------------- simulated brains

class FakeUI:
    def __init__(self, approve=True):
        self.approve = approve
        self.lines, self.spoken, self.confirms = [], [], []

    def show(self, kind, text):
        self.lines.append((kind, text))

    def status(self, text):
        pass

    def confirm(self, reason, described, title=None, yes_text=None, timeout=None):
        self.confirms.append(reason)
        return self.approve

    def speak(self, text):
        self.spoken.append(text)


class FakeBrain:
    """Plays back scripted replies and records what it was sent."""

    def __init__(self, replies, label="fake", vision=True, unavailable=False):
        self.replies = list(replies)
        self.sent = []
        self.label = label
        self.name = label
        self.vision = vision
        self.unavailable = unavailable
        self.missing_key = ""
        self.is_paid = False

    def budget_ok(self):
        return True

    def chat(self, messages, tools, stop):
        if self.unavailable:
            raise BrainUnavailable(f"{self.label} is off")
        self.sent.append(json.loads(json.dumps(messages)))
        text, calls = self.replies.pop(0)
        raw = [{"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["arguments"]}}
               for c in calls]
        message = {"role": "assistant", "content": text or None}
        if raw:
            message["tool_calls"] = raw
        return Reply(text=text, tool_calls=calls, message=message)


class FakeRouter:
    def __init__(self, *brains):
        self.brains = list(brains)

    def chain(self):
        return self.brains


def call(name, **args):
    return {"id": f"id-{name}", "name": name, "arguments": json.dumps(args)}


def make_agent(router, ui, tmp_path, **overrides):
    settings = json.loads(json.dumps(config.DEFAULT_SETTINGS))
    settings.update(overrides)
    return Agent(settings, router, TOOLS, memory_module.get_memory(), ui, StopSwitch(),
                 log=ActionLog(tmp_path / "actions.log"))


def test_agent_runs_tool_then_answers(tmp_path):
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "x.txt").write_text("x")
    brain = FakeBrain([("", [call("list_folder", path=str(folder))]), ("폴더에 파일이 1개 있어요.", [])])
    ui = FakeUI()
    make_agent(FakeRouter(brain), ui, tmp_path).handle("이 폴더에 뭐가 있어?")

    second = brain.sent[1]
    assert second[0]["role"] == "system"
    assert second[-2]["tool_calls"][0]["id"] == "id-list_folder"
    tool_msg = second[-1]
    assert tool_msg["role"] == "tool" and tool_msg["tool_call_id"] == "id-list_folder"
    assert json.loads(tool_msg["content"])["total_items"] == 1
    assert ui.spoken == ["폴더에 파일이 1개 있어요."]


def test_denied_action_is_not_executed(tmp_path):
    victim = tmp_path / "keep.txt"
    victim.write_text("important")
    brain = FakeBrain([("", [call("delete_item", path=str(victim))]), ("OK, I won't.", [])])
    ui = FakeUI(approve=False)
    make_agent(FakeRouter(brain), ui, tmp_path).handle("delete keep.txt")
    assert victim.exists() and ui.confirms
    assert json.loads(brain.sent[1][-1]["content"])["status"] == "denied_by_user"


def test_invalid_json_arguments_are_reported_back(tmp_path):
    brain = FakeBrain([("", [{"id": "x", "name": "list_folder", "arguments": "{oops"}]), ("sorry", [])])
    make_agent(FakeRouter(brain), FakeUI(), tmp_path).handle("list")
    assert "error" in json.loads(brain.sent[1][-1]["content"])


def test_memory_is_saved_and_appears_in_prompt(tmp_path):
    brain = FakeBrain([("", [call("remember", fact="Project folder is D:\\Work")]), ("Saved.", [])])
    agent = make_agent(FakeRouter(brain), FakeUI(), tmp_path)
    agent.handle("remember my project folder is D:\\Work")
    assert "D:\\Work" in agent._system_prompt()


def test_system_prompt_is_stable_and_time_goes_in_user_message(tmp_path):
    brain = FakeBrain([("Hello!", []), ("Again.", [])])
    agent = make_agent(FakeRouter(brain), FakeUI(), tmp_path)
    agent.handle("hi")
    agent.handle("hi again")
    assert brain.sent[0][0] == brain.sent[1][0]  # same system prompt -> local model can reuse its cache
    assert brain.sent[1][-1]["content"].startswith("[")
    assert [m["role"] for m in brain.sent[1]] == ["system", "user", "assistant", "user"]


def test_plan_text_is_shown_but_only_final_answer_is_spoken(tmp_path):
    brain = FakeBrain([("Plan: check folders.", [call("list_folder", path=str(tmp_path))]), ("Done.", [])])
    ui = FakeUI()
    make_agent(FakeRouter(brain), ui, tmp_path).handle("show my folders")
    assert ("agent", "Plan: check folders.") in ui.lines
    assert ui.spoken == ["Done."]


def test_falls_back_to_cloud_when_local_is_off(tmp_path):
    local = FakeBrain([], label="local", unavailable=True)
    cloud = FakeBrain([("클라우드가 답했어요.", [])], label="cloud")
    ui = FakeUI()
    make_agent(FakeRouter(local, cloud), ui, tmp_path).handle("hi")
    assert ui.spoken == ["클라우드가 답했어요."]
    assert any("cloud" in text for kind, text in ui.lines if kind == "info")


def test_reports_all_reasons_when_no_brain_works(tmp_path):
    ui = FakeUI()
    agent = make_agent(FakeRouter(FakeBrain([], "local", unavailable=True), FakeBrain([], "cloud", unavailable=True)),
                       ui, tmp_path)
    agent.handle("hi")
    errors = [text for kind, text in ui.lines if kind == "error"]
    assert "local is off" in errors[0] and "cloud is off" in errors[0]
    assert not agent.busy


def test_screenshot_reaches_vision_brain_as_image(tmp_path, monkeypatch):
    monkeypatch.setattr(TOOLS["look_at_screen"], "func",
                        lambda include_screenshot=True: {"elements": ['[1] Button "OK"'], "_image_jpeg_b64": "AAAA"})
    brain = FakeBrain([("", [call("look_at_screen")]), ("I see an OK button.", [])])
    make_agent(FakeRouter(brain), FakeUI(), tmp_path).handle("what's on screen?")
    last = brain.sent[1][-1]
    assert last["role"] == "user" and last["content"][1]["image_url"]["url"] == "data:image/jpeg;base64,AAAA"
    assert "_image_jpeg_b64" not in brain.sent[1][-2]["content"]


def test_blind_brain_gets_no_image(tmp_path, monkeypatch):
    monkeypatch.setattr(TOOLS["look_at_screen"], "func",
                        lambda include_screenshot=True: {"elements": [], "_image_jpeg_b64": "AAAA"})
    brain = FakeBrain([("", [call("look_at_screen")]), ("ok", [])], vision=False)
    make_agent(FakeRouter(brain), FakeUI(), tmp_path).handle("look")
    assert brain.sent[1][-1]["role"] == "tool"
    assert "can't see images" in brain.sent[1][-1]["content"]


def test_only_latest_screenshot_is_kept():
    def img():
        return {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "x"}}]}

    out = _keep_latest_image([img(), {"role": "assistant", "content": "a"}, img()])
    assert out[0]["content"] == "[older screenshot removed]"
    assert isinstance(out[2]["content"], list)


def test_stop_switch_interrupts(tmp_path):
    class StoppingBrain(FakeBrain):
        def chat(self, messages, tools, stop):
            stop.press()
            stop.check()

    ui = FakeUI()
    agent = make_agent(FakeRouter(StoppingBrain([])), ui, tmp_path)
    agent.handle("do something long")
    assert ("info", t("stopped")) in ui.lines and not agent.busy


# ---------------------------------------------------------------- brains, budget, settings

def test_paid_brain_refuses_when_budget_is_used_up():
    usage = Usage()
    usage.record("glm", 10_000_000, 0, 0.3, 0.9)  # $3.00
    profile = dict(config.DEFAULT_BRAINS["glm"], api_key_env="")
    brain = Brain("glm", profile, usage, budget_ok=lambda: usage.month_cost() < 2.0)
    with pytest.raises(BrainUnavailable, match="예산|budget"):
        brain.chat([{"role": "user", "content": "hi"}], [], StopSwitch())
    assert usage.month_cost() == pytest.approx(3.0)


def test_missing_key_makes_brain_unavailable(monkeypatch):
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    monkeypatch.setattr(config, "load_env", lambda: None)
    brain = Brain("glm", config.DEFAULT_BRAINS["glm"])
    with pytest.raises(BrainUnavailable, match="API"):
        brain.chat([], [], StopSwitch())


def test_stage1_settings_are_migrated():
    config.SETTINGS_FILE.write_text(json.dumps({"model": "gemini-2.5-flash", "speech_rate": 3,
                                                "brains": {"glm": {"model": "glm-5v"}}}), encoding="utf-8")
    settings = config.load_settings()
    assert settings["voice_model"] == "gemini-2.5-flash" and "model" not in settings
    assert settings["speech_rate"] == 3
    assert settings["brains"]["glm"]["model"] == "glm-5v"
    assert settings["brains"]["glm"]["base_url"].startswith("https://api.z.ai")
    assert "lmstudio" not in settings["brains"] and "gemini" in settings["brains"]


def test_parse_arguments_tolerates_sloppy_output():
    assert parse_arguments('{"a": 1}') == {"a": 1}
    assert parse_arguments('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_arguments('"{\\"a\\": 1}"') == {"a": 1}
    assert parse_arguments("") == {}


def test_thinking_text_is_hidden():
    assert clean_text("<think>hmm</think>Done.") == "Done."
    assert clean_text("reasoning...</think>\nDone.") == "Done."


def test_without_images():
    out = without_images([{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "x"}}]}])
    assert out[0]["content"][0] == {"type": "text", "text": "[screenshot omitted]"}


# ---------------------------------------------------------------- voice helpers

def test_language_detection_for_voices():
    assert detect_language("메모장을 열었어요.") == "ko-KR"
    assert detect_language("Ich habe die Datei geöffnet.") == "de-DE"
    assert detect_language("I opened the file.") == "en-US"


def test_clean_for_speech_drops_paths_and_markdown():
    assert clean_for_speech("**Done.** Saved to C:\\Users\\me\\a.txt") == "Done. Saved to"


def test_old_long_tool_results_are_shortened():
    from agent.agent import _shorten_old_results
    turn = [{"role": "user", "content": "q"}] + [{"role": "tool", "tool_call_id": str(i), "content": "x" * 5000}
                                                for i in range(5)]
    out = _shorten_old_results(turn)
    assert [len(m["content"]) < 2000 for m in out[1:]] == [True, True, True, False, False]
    assert turn[1]["content"] == "x" * 5000  # original untouched


def test_spreadsheet_numbers_and_leading_zeros(tmp_path):
    from openpyxl import load_workbook
    TOOLS["save_spreadsheet"].call({"path": str(tmp_path / "s.xlsx"), "headers": ["a", "b", "c"],
                                    "rows": [["가", "007", "12.5"]]})
    assert [c.value for c in load_workbook(tmp_path / "s.xlsx").active[2]] == ["가", "007", 12.5]


def test_smart_main_ai_is_not_replaced_when_a_tool_fails(tmp_path):
    bad = [call("read_file", path=str(tmp_path / f"missing{i}.txt")) for i in range(3)]
    main = FakeBrain([("", [bad[0]]), ("", [bad[1]]), ("", [bad[2]]), ("That file doesn't exist.", [])], label="gemini")
    backup = FakeBrain([], label="backup")
    ui = FakeUI()
    make_agent(FakeRouter(main, backup), ui, tmp_path).handle("read it")
    assert ui.spoken == ["That file doesn't exist."] and backup.sent == []


def test_router_uses_main_then_backup():
    from agent.brains import BrainRouter
    settings = json.loads(json.dumps(config.DEFAULT_SETTINGS))
    router = BrainRouter(settings)
    assert [b.name for b in router.chain()] == ["gemini"]
    settings["backup_brain"] = "glm"
    assert [b.name for b in router.chain()] == ["gemini", "glm"]
    settings["main_brain"], settings["backup_brain"] = "glm", "glm"
    assert [b.name for b in router.chain()] == ["glm"]


def test_stage2_brain_settings_are_migrated():
    config.SETTINGS_FILE.write_text(json.dumps({"brain_mode": "auto", "local_brain": "lmstudio",
                                                "cloud_brain": "glm", "escalate_after_steps": 12}), encoding="utf-8")
    settings = config.load_settings()
    assert settings["main_brain"] == "gemini" and "brain_mode" not in settings
    assert settings["brains"]["gemini"]["auto_switch_models"] is True


def test_model_ranking_prefers_stable_newer_full_models():
    from agent.brains import rank_models
    names = ["gemini-2.5-flash", "gemini-3.6-flash", "gemini-3.6-flash-lite", "gemini-3.8-flash-preview",
             "gemini-3.6-flash-image", "gemini-3.6-pro", "gemini-flash-latest"]
    assert rank_models(names, "flash")[:3] == ["gemini-3.6-flash", "gemini-2.5-flash", "gemini-flash-latest"]
    assert "gemini-3.6-flash-image" not in rank_models(names, "flash")


def test_placeholder_signatures_replace_foreign_ones():
    from agent.brains import with_placeholder_signatures
    msgs = [{"role": "assistant", "content": None, "tool_calls": [
        {"id": "a", "type": "function", "function": {"name": "f", "arguments": "{}"},
         "extra_content": {"google": {"thought_signature": "OLD"}}}]}]
    out = with_placeholder_signatures(msgs)
    assert out[0]["tool_calls"][0]["extra_content"]["google"]["thought_signature"] == "skip_thought_signature_validator"
    assert msgs[0]["tool_calls"][0]["extra_content"]["google"]["thought_signature"] == "OLD"


def test_local_model_settings_are_removed():
    config.SETTINGS_FILE.write_text(json.dumps({
        "main_brain": "lmstudio", "backup_brain": "lmstudio",
        "brains": {"lmstudio": {"label": "Local", "base_url": "http://localhost:1234/v1", "model": "x"}}}),
        encoding="utf-8")
    settings = config.load_settings()
    assert "lmstudio" not in settings["brains"]
    assert settings["main_brain"] == "gemini" and settings["backup_brain"] == ""
    assert "escalate_after_steps" not in settings
