"""Tests that run without Windows, a microphone or an API key (Gemini is simulated).

Run:  .venv\\Scripts\\python -m pytest tests
"""

import json

import pytest
from google.genai import types

from agent import config
from agent.agent import Agent, _split_heard
from agent import memory as memory_module
from agent.safety import ActionLog, StopSwitch, is_protected
from agent.tooling import load_all_tools
from agent.voice import clean_for_speech, detect_language

TOOLS = load_all_tools()


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    data = tmp_path / "agent-data"
    data.mkdir()
    monkeypatch.setattr(config, "UNDO_FILE", data / "undo.json")
    monkeypatch.setattr(config, "MEMORY_FILE", data / "memory.json")
    monkeypatch.setattr(memory_module, "_instance", None)
    return data


# ---------------------------------------------------------------- tool registry

def test_every_tool_builds_a_gemini_declaration():
    for tool in TOOLS.values():
        decl = tool.declaration()
        assert decl.name == tool.name
        assert decl.description, f"{tool.name} has no description"
        for arg, schema in (decl.parameters.properties or {}).items() if decl.parameters else []:
            assert schema.description, f"{tool.name}.{arg} has no description"


def test_expected_tools_exist():
    for name in ["find_files", "move_many", "delete_item", "undo_last_moves", "open_app", "close_window",
                 "run_command", "remember", "set_volume", "power_action"]:
        assert name in TOOLS


# ---------------------------------------------------------------- risk rules

def test_risk_rules(tmp_path):
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
    assert (tmp_path / "PDFs" / "a.pdf").exists()
    undo = TOOLS["undo_last_moves"].call({"operations": 1})
    assert len(undo["restored"]) == 2
    assert (tmp_path / "a.pdf").exists() and not (tmp_path / "PDFs" / "a.pdf").exists()


def test_rename_refuses_existing_target(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    result = TOOLS["rename_item"].call({"path": str(tmp_path / "a.txt"), "new_name": "b.txt"})
    assert "error" in result
    assert (tmp_path / "b.txt").read_text() == "b"


def test_find_and_read(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "보고서.txt").write_text("한국어 내용", encoding="cp949")
    found = TOOLS["find_files"].call({"name_pattern": "보고서", "folder": str(tmp_path)})
    assert found["count"] == 1
    read = TOOLS["read_file"].call({"path": found["results"][0]["path"]})
    assert read["content"] == "한국어 내용"
    by_ext = TOOLS["find_files"].call({"folder": str(tmp_path), "extensions": "txt"})
    assert by_ext["count"] == 1


def test_write_text_file_does_not_overwrite_by_default(tmp_path):
    target = tmp_path / "note.txt"
    TOOLS["write_text_file"].call({"path": str(target), "content": "first"})
    result = TOOLS["write_text_file"].call({"path": str(target), "content": "second"})
    assert "error" in result
    assert target.read_text(encoding="utf-8") == "first"


# ---------------------------------------------------------------- agent loop (Gemini simulated)

class FakeUI:
    def __init__(self, approve=True):
        self.approve = approve
        self.lines, self.spoken, self.confirms = [], [], []

    def show(self, kind, text):
        self.lines.append((kind, text))

    def status(self, text):
        pass

    def confirm(self, reason, described):
        self.confirms.append(reason)
        return self.approve

    def speak(self, text):
        self.spoken.append(text)


class FakeBrain:
    """Plays back scripted Gemini replies and records what it was sent."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.sent = []

    def generate(self, contents, system_instruction, declarations, stop):
        self.sent.append(list(contents))
        parts = self.replies.pop(0)
        return types.GenerateContentResponse(
            candidates=[types.Candidate(content=types.Content(role="model", parts=parts))])


def call(name, **args):
    return types.Part(function_call=types.FunctionCall(id=f"id-{name}", name=name, args=args))


def text(t):
    return types.Part(text=t)


def make_agent(brain, ui, tmp_path):
    settings = dict(config.DEFAULT_SETTINGS)
    return Agent(settings, brain, TOOLS, memory_module.get_memory(), ui, StopSwitch(),
                 log=ActionLog(tmp_path / "actions.log"))


def test_agent_runs_tool_then_answers(tmp_path):
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "x.txt").write_text("x")
    brain = FakeBrain([[call("list_folder", path=str(folder))], [text("폴더에 파일이 1개 있어요.")]])
    ui = FakeUI()
    agent = make_agent(brain, ui, tmp_path)
    agent.handle(text="이 폴더에 뭐가 있어?")

    second_request = brain.sent[1]
    tool_result = second_request[-1].parts[0].function_response
    assert tool_result.name == "list_folder"
    assert tool_result.id == "id-list_folder"
    assert tool_result.response["total_items"] == 1
    assert ui.spoken == ["폴더에 파일이 1개 있어요."]
    log = [json.loads(line) for line in (tmp_path / "actions.log").read_text(encoding="utf-8").splitlines()]
    assert log[0]["tool"] == "list_folder" and log[0]["outcome"] == "done"


def test_denied_action_is_not_executed(tmp_path):
    victim = tmp_path / "keep.txt"
    victim.write_text("important")
    brain = FakeBrain([[call("delete_item", path=str(victim))], [text("OK, I won't delete it.")]])
    ui = FakeUI(approve=False)
    make_agent(brain, ui, tmp_path).handle(text="delete keep.txt")
    assert victim.exists()
    assert ui.confirms, "the user should have been asked"
    response = brain.sent[1][-1].parts[0].function_response.response
    assert response["status"] == "denied_by_user"


def test_memory_is_saved_and_appears_in_prompt(tmp_path):
    brain = FakeBrain([[call("remember", fact="Project folder is D:\\Work")], [text("Saved.")]])
    agent = make_agent(brain, FakeUI(), tmp_path)
    agent.handle(text="remember my project folder is D:\\Work")
    assert "D:\\Work" in agent._system_prompt()


def test_history_keeps_previous_turn(tmp_path):
    brain = FakeBrain([[text("Hello!")], [text("You said hi.")]])
    agent = make_agent(brain, FakeUI(), tmp_path)
    agent.handle(text="hi")
    agent.handle(text="what did I say?")
    second = brain.sent[1]
    assert [c.role for c in second] == ["user", "model", "user"]
    assert second[0].parts[0].text == "hi"


def test_voice_transcript_replaces_audio_in_history(tmp_path):
    brain = FakeBrain([[text("HEARD: 메모장 열어줘\n메모장을 열게요.")], [text("ok")]])
    ui = FakeUI()
    agent = make_agent(brain, ui, tmp_path)
    agent.handle(audio_wav=b"RIFF....fake")
    assert ("you", "(voice) 메모장 열어줘") in ui.lines
    agent.handle(text="next")
    first_user = brain.sent[1][0]
    assert first_user.parts[0].text == "(voice) 메모장 열어줘"
    assert all(p.inline_data is None for c in brain.sent[1] for p in c.parts)


def test_stop_switch_interrupts(tmp_path):
    ui = FakeUI()

    class StoppingBrain(FakeBrain):
        def generate(self, contents, system_instruction, declarations, stop):
            stop.press()
            stop.check()

    agent = make_agent(StoppingBrain([]), ui, tmp_path)
    agent.handle(text="do something long")
    assert ("info", "Stopped.") in ui.lines
    assert not agent.busy


# ---------------------------------------------------------------- small helpers

def test_split_heard():
    heard, rest = _split_heard("HEARD: Öffne den Rechner\nOkay.")
    assert heard == "Öffne den Rechner" and rest == "Okay."
    assert _split_heard("no transcript") == (None, "no transcript")


def test_language_detection_for_voices():
    assert detect_language("메모장을 열었어요.") == "ko-KR"
    assert detect_language("Ich habe die Datei geöffnet.") == "de-DE"
    assert detect_language("I opened the file.") == "en-US"


def test_clean_for_speech_drops_paths_and_markdown():
    assert clean_for_speech("**Done.** Saved to C:\\Users\\me\\a.txt") == "Done. Saved to"


def test_move_into_new_folder_keeps_file_name(tmp_path):
    (tmp_path / "report.pdf").write_text("x")
    result = TOOLS["move_item"].call({"source": str(tmp_path / "report.pdf"), "destination": str(tmp_path / "Archive")})
    assert result["to"] == str(tmp_path / "Archive" / "report.pdf")


def test_plan_text_is_shown_but_only_final_answer_is_spoken(tmp_path):
    brain = FakeBrain([[text("Plan: list the folder."), call("get_known_folders")], [text("Done.")]])
    ui = FakeUI()
    make_agent(brain, ui, tmp_path).handle(text="show my folders")
    assert ("agent", "Plan: list the folder.") in ui.lines
    assert ui.spoken == ["Done."]
