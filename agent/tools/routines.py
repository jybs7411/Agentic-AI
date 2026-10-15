"""Routines (Stage 4): save repeated work and run it by name or on a schedule.

Two kinds, stored in data/routines.json:
- "steps": a list of instructions in plain words. Each run, the AI carries them out, so it adapts
  to whatever is on screen (but uses AI requests).
- "recorded": the actions the agent just performed, replayed directly (fast, almost no AI use).
  Buttons and links are saved by NAME, not by number, so they are found again even if the page
  changed a little. If a step still fails, the AI gets the original goal and finishes the job.

Schedules ("09:00" + "daily" / "weekdays" / "weekends" / "mon,wed" / "월,수,금") run while the
agent is running. A run missed by more than 15 minutes (PC off, busy) is skipped until next time.
"""

import json
import re
from datetime import datetime, timedelta

from agent import config
from agent.tooling import tool

DAY_NAMES = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
             "월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6,
             "mo": 0, "di": 1, "mi": 2, "do": 3, "fr": 4, "sa": 5, "so": 6}
DAY_GROUPS = {"daily": list(range(7)), "매일": list(range(7)), "everyday": list(range(7)), "täglich": list(range(7)),
              "weekdays": [0, 1, 2, 3, 4], "평일": [0, 1, 2, 3, 4], "werktags": [0, 1, 2, 3, 4],
              "weekends": [5, 6], "주말": [5, 6], "wochenende": [5, 6]}
LATE_LIMIT = timedelta(minutes=15)

# Tools that only look at things; they are left out of recordings.
NOT_RECORDED = {
    "look_at_screen", "read_screen_text", "web_read", "web_look", "web_get_tables", "list_folder", "find_files",
    "file_info", "read_file", "get_known_folders", "list_windows", "list_installed_apps", "get_system_info",
    "get_clipboard", "list_watches", "remember", "forget", "get_selected_text", "show_style_guide",
    "save_style_guide", "save_routine", "record_routine", "run_routine", "list_routines", "delete_routine",
    "set_routine_schedule", "undo_last_moves",
}

_hooks = {"last_task": lambda: None, "replay": lambda actions: {"error": "Replay is not available."}}


def configure(last_task=None, replay=None):
    if last_task:
        _hooks["last_task"] = last_task
    if replay:
        _hooks["replay"] = replay


def _file():
    return config.DATA_DIR / "routines.json"


def load_routines() -> list:
    try:
        return json.loads(_file().read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(routines: list):
    _file().parent.mkdir(exist_ok=True)
    _file().write_text(json.dumps(routines, ensure_ascii=False, indent=1), encoding="utf-8")


def _find(routines: list, name: str):
    wanted = name.strip().casefold()
    exact = [r for r in routines if r["name"].casefold() == wanted]
    if exact:
        return exact[0]
    partial = [r for r in routines if wanted in r["name"].casefold() or r["name"].casefold() in wanted]
    return partial[0] if len(partial) == 1 else None


def parse_schedule(time_text: str, days_text: str):
    """("9:00", "평일") -> {"time": "09:00", "days": [0..4]}; ("", ...) -> None."""
    if not time_text.strip():
        return None
    match = re.fullmatch(r"\s*(\d{1,2})[:시.]?\s*(\d{2})?\s*분?\s*", time_text)
    if not match:
        raise ValueError(f"Time must look like 09:00, not '{time_text}'.")
    hour, minute = int(match.group(1)), int(match.group(2) or 0)
    if hour > 23 or minute > 59:
        raise ValueError(f"Invalid time '{time_text}'.")
    key = (days_text or "daily").strip().lower()
    if key in DAY_GROUPS:
        days = DAY_GROUPS[key]
    else:
        parts = [p for p in re.split(r"[,\s/]+|(?<=[월화수목금토일])", key) if p]
        days = sorted({_day(p) for p in parts} - {None})
        if not days:
            raise ValueError(f"Unknown days '{days_text}'. Use daily, weekdays, weekends or e.g. mon,wed,fri.")
    return {"time": f"{hour:02d}:{minute:02d}", "days": days}


def _day(text: str):
    """'mon' / 'Montag' / 'mo' / '월' / '월요일' -> 0"""
    for length in (3, 2, 1):
        if text[:length] in DAY_NAMES:
            return DAY_NAMES[text[:length]]
    return None


def _describe_schedule(schedule) -> str:
    if not schedule:
        return "on request only"
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    days = schedule["days"]
    day_text = ("every day" if len(days) == 7 else "weekdays" if days == [0, 1, 2, 3, 4]
                else "weekends" if days == [5, 6] else ", ".join(names[d] for d in days))
    return f"{schedule['time']}, {day_text}"


def due_routines(now: datetime = None) -> list:
    """Names of scheduled routines that should run now."""
    now = now or datetime.now()
    due = []
    for r in load_routines():
        schedule = r.get("schedule")
        if not schedule or now.weekday() not in schedule["days"]:
            continue
        hour, minute = map(int, schedule["time"].split(":"))
        planned = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if planned <= now <= planned + LATE_LIMIT and r.get("last_run", "")[:10] != now.strftime("%Y-%m-%d"):
            due.append(r["name"])
    return due


def mark_ran(name: str):
    routines = load_routines()
    routine = _find(routines, name)
    if routine:
        routine["last_run"] = datetime.now().isoformat(timespec="minutes")
        _save(routines)


def _upsert(routine: dict) -> dict:
    routines = [r for r in load_routines() if r["name"].casefold() != routine["name"].casefold()]
    routines.append(routine)
    _save(routines)
    return routine


# ---------------------------------------------------------------------- tools

@tool()
def save_routine(name: str, steps: list[str], time: str = "", days: str = "daily") -> dict:
    """Save a routine described in words, e.g. "아침 루틴": ["오늘 날씨 알려주기", "네이버 뉴스 헤드라인 5개 요약",
    "메일함 열기"]. Each run, you carry out the steps. Optionally runs on a schedule.

    Args:
      name: Short name the user will say, e.g. "아침 루틴".
      steps: The steps in order, each a short instruction.
      time: Time to run automatically, e.g. "09:00". Empty = only when the user asks.
      days: "daily", "weekdays", "weekends", or days like "mon,wed,fri" / "월,수,금".
    """
    try:
        schedule = parse_schedule(time, days)
    except ValueError as e:
        return {"error": str(e)}
    _upsert({"name": name.strip(), "type": "steps", "steps": [s.strip() for s in steps if s.strip()],
             "schedule": schedule, "created": datetime.now().isoformat(timespec="minutes")})
    return {"saved": name, "type": "steps", "runs": _describe_schedule(schedule)}


@tool()
def record_routine(name: str, time: str = "", days: str = "daily") -> dict:
    """Save the actions of the PREVIOUS finished command as a routine that can be replayed quickly
    (e.g. after "방금 한 거 '출근 준비'로 저장해줘"). Best for fixed actions: opening apps and sites,
    clicking the same buttons, downloading the same report.

    Args:
      name: Short name the user will say.
      time: Time to run automatically, e.g. "08:50". Empty = only when the user asks.
      days: "daily", "weekdays", "weekends", or days like "mon,wed,fri" / "월,수,금".
    """
    last = _hooks["last_task"]()
    if not last or not last.get("actions"):
        return {"error": "The previous command had no actions to record. Do the task first, then ask to save it."}
    try:
        schedule = parse_schedule(time, days)
    except ValueError as e:
        return {"error": str(e)}
    actions = [a for a in last["actions"] if a["tool"] not in NOT_RECORDED]
    if not actions:
        return {"error": "The previous command only looked at things; there is nothing to replay. "
                         "Use save_routine with steps instead."}
    _upsert({"name": name.strip(), "type": "recorded", "goal": last["command"], "actions": actions,
             "schedule": schedule, "created": datetime.now().isoformat(timespec="minutes")})
    return {"saved": name, "type": "recorded", "steps": [_action_text(a) for a in actions],
            "runs": _describe_schedule(schedule)}


def _action_text(action: dict) -> str:
    label = f' "{action["label"]}"' if action.get("label") else ""
    args = {k: v for k, v in action["args"].items() if k != "number"}
    return f"{action['tool']}{label} {json.dumps(args, ensure_ascii=False)[:120]}"


@tool()
def run_routine(name: str) -> dict:
    """Run a saved routine by name.

    Args:
      name: The routine's name (or a clear part of it).
    """
    routine = _find(load_routines(), name)
    if routine is None:
        return {"error": f"No routine named '{name}'.", "routines": [r["name"] for r in load_routines()]}
    mark_ran(routine["name"])
    if routine["type"] == "steps":
        return {"routine": routine["name"], "steps": routine["steps"],
                "instruction": "Carry out these steps now, in order, then give one short summary."}
    result = _hooks["replay"](routine["actions"])
    result["routine"] = routine["name"]
    if result.get("declined"):
        result["goal"] = routine["goal"]
        result["instruction"] = "The user declined a step. Do not continue; ask what they want."
    elif result.get("failed_step"):
        result["goal"] = routine["goal"]
        result["instruction"] = ("The replay stopped. Finish the original goal yourself with the normal tools, "
                                 "starting from where it stopped.")
    return result


@tool()
def list_routines() -> dict:
    """List the saved routines with their type and schedule."""
    return {"routines": [{"name": r["name"], "type": r["type"], "runs": _describe_schedule(r.get("schedule")),
                          "steps": r["steps"] if r["type"] == "steps" else [_action_text(a) for a in r["actions"]]}
                         for r in load_routines()]}


@tool()
def set_routine_schedule(name: str, time: str = "", days: str = "daily") -> dict:
    """Change when a routine runs automatically, or remove its schedule (empty time).

    Args:
      name: The routine's name.
      time: e.g. "18:00". Empty = only when the user asks.
      days: "daily", "weekdays", "weekends", or days like "mon,wed,fri" / "월,수,금".
    """
    routines = load_routines()
    routine = _find(routines, name)
    if routine is None:
        return {"error": f"No routine named '{name}'."}
    try:
        routine["schedule"] = parse_schedule(time, days)
    except ValueError as e:
        return {"error": str(e)}
    _save(routines)
    return {"routine": routine["name"], "runs": _describe_schedule(routine["schedule"])}


@tool()
def delete_routine(name: str) -> dict:
    """Delete a saved routine.

    Args:
      name: The routine's name.
    """
    routines = load_routines()
    routine = _find(routines, name)
    if routine is None:
        return {"error": f"No routine named '{name}'."}
    _save([r for r in routines if r is not routine])
    return {"deleted": routine["name"]}
