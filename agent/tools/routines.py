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
from agent.texts import say
from agent.tooling import tool

_DAY_WORDS = [
    ("mon", "monday", "mo", "montag", "월", "월요일"), ("tue", "tuesday", "di", "dienstag", "화", "화요일"),
    ("wed", "wednesday", "mi", "mittwoch", "수", "수요일"), ("thu", "thursday", "do", "donnerstag", "목", "목요일"),
    ("fri", "friday", "fr", "freitag", "금", "금요일"), ("sat", "saturday", "sa", "samstag", "토", "토요일"),
    ("sun", "sunday", "so", "sonntag", "일", "일요일"),
]
DAY_NAMES = {word: index for index, words in enumerate(_DAY_WORDS) for word in words}
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
    "set_routine_schedule", "undo_last_moves", "web_ask_user",
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


def _find(routines: list, name: str, exact_only: bool = False):
    """The routine with this name. A part of a name also works, but only when it fits exactly one."""
    wanted = " ".join(str(name).split()).casefold()
    if not wanted:
        return None
    exact = [r for r in routines if " ".join(r["name"].split()).casefold() == wanted]
    if exact or exact_only:
        return exact[0] if exact else None
    partial = [r for r in routines if wanted in r["name"].casefold()]
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
    return {"time": f"{hour:02d}:{minute:02d}", "days": parse_days(days_text)}


def parse_days(days_text: str) -> list:
    """"평일" / "mon-fri" / "월~금" / "월,수,금" / "월수금" / "Mo,Mi,Fr" -> [0, 1, ...]. Unknown words are errors."""
    key = (days_text or "daily").strip().lower()
    if key in DAY_GROUPS:
        return DAY_GROUPS[key]
    key = re.sub(r"\s*(~|–|—|-|\bto\b|\bthru\b|\bthrough\b|\bbis\b)\s*", "-", key)
    key = re.sub(r"(?<=[월화수목금토일])(?=[월화수목금토일])", ",", key)  # "월수금" -> "월,수,금"
    days = set()
    for token in [t for t in re.split(r"[,\s/]+", key) if t]:
        ends = token.split("-")
        if len(ends) == 2 and all(ends):
            first, last = _day(ends[0]), _day(ends[1])
            if first is None or last is None:
                raise ValueError(f"Unknown day range '{token}'.")
            days.update(range(first, last + 1) if first <= last else list(range(first, 7)) + list(range(0, last + 1)))
            continue
        day = _day(token)
        if day is None:
            raise ValueError(f"Unknown day '{token}'. Use daily, weekdays, weekends or e.g. mon,wed,fri / 월,수,금.")
        days.add(day)
    if not days:
        raise ValueError(f"Unknown days '{days_text}'.")
    return sorted(days)


def _day(text: str):
    """A whole day word -> 0..6 ('mon', 'Monday', 'Montag', 'mo', '월', '월요일'), else None."""
    return DAY_NAMES.get(text.strip().lower().rstrip("."))


def _describe_schedule(schedule) -> str:
    if not schedule:
        return "on request only"
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    days = schedule["days"]
    day_text = ("every day" if len(days) == 7 else "weekdays" if days == [0, 1, 2, 3, 4]
                else "weekends" if days == [5, 6] else ", ".join(names[d] for d in days))
    return f"{schedule['time']}, {day_text}"


def due_routines(now: datetime = None) -> list:
    """Scheduled runs due now: [{"name", "slot"}]. A slot is the planned date+time, so a manual run
    earlier that day doesn't cancel it, and 23:55 still runs if checked just after midnight."""
    now = now or datetime.now()
    due = []
    for r in load_routines():
        schedule = r.get("schedule")
        if not isinstance(schedule, dict):
            continue
        try:
            hour, minute = map(int, schedule["time"].split(":"))
        except (KeyError, ValueError, AttributeError):
            continue
        for day_offset in (0, -1):
            planned = (now + timedelta(days=day_offset)).replace(hour=hour, minute=minute, second=0, microsecond=0)
            slot = planned.isoformat(timespec="minutes")
            if (planned.weekday() in schedule.get("days", []) and planned <= now <= planned + LATE_LIMIT
                    and str(r.get("last_scheduled") or "") != slot):
                due.append({"name": r["name"], "slot": slot})
                break
    return due


def mark_scheduled(name: str, slot: str):
    routines = load_routines()
    routine = _find(routines, name, exact_only=True)
    if routine:
        routine["last_scheduled"] = slot
        _save(routines)


def mark_ran(name: str):
    routines = load_routines()
    routine = _find(routines, name, exact_only=True)
    if routine:
        routine["last_run"] = datetime.now().isoformat(timespec="minutes")
        _save(routines)


def _upsert(routine: dict) -> dict:
    routines = [r for r in load_routines() if r["name"].casefold() != routine["name"].casefold()]
    routines.append(routine)
    _save(routines)
    return routine


# ---------------------------------------------------------------------- tools

def _risk_save_routine(args):
    steps = "\n".join(f"- {step}" for step in args.get("steps", []))
    when = f"{args.get('time')} ({args.get('days') or 'daily'})" if args.get("time") else say("요청할 때만", "on request")
    return say(f"루틴 '{args.get('name')}'을(를) 저장해요. 실행: {when}\n{steps}",
               f"Saves the routine '{args.get('name')}'. Runs: {when}\n{steps}")


def _risk_record_routine(args):
    last = _hooks["last_task"]() or {}
    steps = "\n".join(f"- {_action_text(a)}" for a in last.get("actions", []) if a["tool"] not in NOT_RECORDED)
    when = f"{args.get('time')} ({args.get('days') or 'daily'})" if args.get("time") else say("요청할 때만", "on request")
    return say(f"방금 한 작업을 루틴 '{args.get('name')}'(으)로 저장해요. 실행: {when}\n{steps}",
               f"Saves the previous task as routine '{args.get('name')}'. Runs: {when}\n{steps}")


@tool(risk=_risk_save_routine)
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


@tool(risk=_risk_record_routine)
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
                "instruction": "These steps were saved and approved by the user earlier. Carry them out now, "
                               "in order, then give one short summary."}
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


@tool(risk=lambda a: say(f"루틴 '{a.get('name')}'의 실행 시간을 바꿔요: {a.get('time') or '요청할 때만'} {a.get('days') or ''}",
                         f"Changes when '{a.get('name')}' runs: {a.get('time') or 'on request'} {a.get('days') or ''}"))
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


@tool(risk=lambda a: say(f"루틴 '{a.get('name')}'을(를) 지워요.", f"Deletes the routine '{a.get('name')}'."))
def delete_routine(name: str) -> dict:
    """Delete a saved routine.

    Args:
      name: The routine's name.
    """
    routines = load_routines()
    routine = _find(routines, name, exact_only=True)
    if routine is None:
        return {"error": f"No routine named exactly '{name}'.", "routines": [r["name"] for r in routines]}
    _save([r for r in routines if r is not routine])
    return {"deleted": routine["name"]}
