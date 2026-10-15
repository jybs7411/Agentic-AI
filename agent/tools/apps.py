"""App and window tools: open apps, list/focus/minimize/maximize/close windows, end programs."""

import difflib
import json
import os
import subprocess
import time

from agent.texts import say
from agent.tooling import tool
from agent.winutil import run_powershell

# Common apps that can be started directly, whatever language Windows is in.
BUILTIN_APPS = {
    "notepad": "notepad.exe", "메모장": "notepad.exe",
    "calculator": "calc.exe", "calc": "calc.exe", "계산기": "calc.exe",
    "paint": "mspaint.exe", "그림판": "mspaint.exe",
    "file explorer": "explorer.exe", "explorer": "explorer.exe", "파일 탐색기": "explorer.exe",
    "command prompt": "cmd.exe", "cmd": "cmd.exe", "명령 프롬프트": "cmd.exe",
    "powershell": "powershell.exe",
    "task manager": "taskmgr.exe", "작업 관리자": "taskmgr.exe",
    "settings": "ms-settings:", "설정": "ms-settings:",
    "control panel": "control.exe", "제어판": "control.exe",
    "snipping tool": "ms-screenclip:",
}

# Programs that can run any command or change the system: starting them asks first, because typing
# into them would otherwise bypass the approval that run_command needs.
POWERFUL_APPS = ("cmd", "command prompt", "명령 프롬프트", "powershell", "pwsh", "terminal", "터미널", "wt.exe",
                 "wscript", "cscript", "mshta", "regedit", "registry", "레지스트리", "task scheduler", "작업 스케줄러",
                 "wsl", "bash", "control panel", "제어판", "task manager", "작업 관리자", "services", "서비스")
SHELL_PROCESSES = {"cmd.exe", "powershell.exe", "pwsh.exe", "windowsterminal.exe", "wt.exe", "conhost.exe",
                   "openconsole.exe", "wsl.exe", "bash.exe", "mintty.exe", "putty.exe", "regedit.exe", "mmc.exe"}

PROTECTED_PROCESSES = {"system", "registry", "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe",
                       "services.exe", "lsass.exe", "svchost.exe", "dwm.exe", "fontdrvhost.exe"}

_start_apps_cache = None


def _start_apps() -> list:
    """All apps in the Start menu (desktop and Store apps): [{'Name':..., 'AppID':...}]."""
    global _start_apps_cache
    if _start_apps_cache is None:
        code, out, err = run_powershell("Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress")
        if code != 0 or not out:
            raise RuntimeError(f"Could not read the Start menu apps: {err}")
        data = json.loads(out)
        _start_apps_cache = data if isinstance(data, list) else [data]
    return _start_apps_cache


def _best_matches(query: str, names: list) -> list:
    q = query.lower().strip()
    lowered = {n.lower(): n for n in names}
    if q in lowered:
        return [lowered[q]]
    contains = sorted((n for n in names if q in n.lower()), key=len)
    if contains:
        return contains
    return [lowered[m] for m in difflib.get_close_matches(q, list(lowered), n=5, cutoff=0.6)]


def _risk_open_app(args):
    name = str(args.get("name", "")).lower()
    resolved = BUILTIN_APPS.get(name.strip(), "")
    if _start_apps_cache is not None and not resolved:
        matches = _best_matches(name, [a["Name"] for a in _start_apps_cache])
        resolved = matches[0].lower() if matches else ""
    if any(word in name or word in resolved.lower() for word in POWERFUL_APPS):
        return say(f"명령을 실행하거나 시스템을 바꿀 수 있는 프로그램을 열어요: {args.get('name')}",
                   f"Opens a program that can run commands or change the system: {args.get('name')}")
    return None


def _wait_for_new_window(before: set, seconds: float = 8.0):
    """After starting an app, wait until its window appears (saves the AI a 'wait' step)."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        time.sleep(0.4)
        try:
            for w in _windows():
                if w["id"] not in before and not w["minimized"]:
                    return w["title"]
        except Exception:
            return None
    return None


@tool(risk=_risk_open_app)
def open_app(name: str) -> dict:
    """Start an application by name, e.g. "Chrome", "Word", "Spotify", "Notepad", "KakaoTalk".
    Works for normal programs and Microsoft Store apps.

    Args:
      name: The app's name as it appears in the Start menu (English or Korean).
    """
    key = name.lower().strip()
    try:
        before = {w["id"] for w in _windows()}
    except Exception:
        before = set()
    if key in BUILTIN_APPS:
        os.startfile(BUILTIN_APPS[key])
        return {"opened": name, "window": _wait_for_new_window(before)}
    apps = _start_apps()
    matches = _best_matches(name, [a["Name"] for a in apps])
    if not matches:
        return {"error": f"No app named '{name}' found. Use list_installed_apps to see the exact names."}
    chosen = next(a for a in apps if a["Name"] == matches[0])
    app_id = chosen["AppID"]
    if os.path.exists(app_id):
        os.startfile(app_id)
    else:
        subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app_id}"])
    result = {"opened": chosen["Name"], "window": _wait_for_new_window(before)}
    if len(matches) > 1:
        result["other_matches"] = matches[1:6]
    return result


@tool()
def list_installed_apps(name_filter: str = "") -> dict:
    """List apps from the Start menu, optionally only those whose name contains a word.

    Args:
      name_filter: Only show apps whose name contains this text. Empty shows all.
    """
    names = sorted({a["Name"] for a in _start_apps()}, key=str.lower)
    if name_filter:
        names = [n for n in names if name_filter.lower() in n.lower()]
    return {"count": len(names), "apps": names[:300]}


# ---------------------------------------------------------------- windows

def _is_cloaked(hwnd) -> bool:
    """Hidden Store-app windows report as 'visible' but are cloaked; skip them."""
    import ctypes
    cloaked = ctypes.c_int(0)
    ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
    return cloaked.value != 0


def _windows() -> list:
    """Visible top-level windows, front-most first (Windows lists them in z-order)."""
    import psutil
    import win32gui
    import win32process

    found = []
    own_pid = os.getpid()

    def collect(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title or title == "Program Manager" or _is_cloaked(hwnd):
            return
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid == own_pid:  # skip the agent's own popup
            return
        try:
            process = psutil.Process(pid).name()
        except Exception:
            process = "?"
        found.append({"id": hwnd, "title": title, "program": process, "pid": pid,
                      "minimized": bool(win32gui.IsIconic(hwnd)), "rect": win32gui.GetWindowRect(hwnd)})

    win32gui.EnumWindows(collect, None)
    return found


def _find_windows(title_or_program: str) -> list:
    q = title_or_program.lower().strip()
    return [w for w in _windows() if q in w["title"].lower() or q in w["program"].lower()]


@tool()
def list_windows() -> dict:
    """List the open windows on the desktop with their title and program name."""
    return {"windows": [{k: w[k] for k in ("title", "program", "minimized")} for w in _windows()]}


def _one_window(title_or_program: str):
    matches = _find_windows(title_or_program)
    if not matches:
        return None, {"error": f"No open window matches '{title_or_program}'. Use list_windows."}
    return matches[0], None


@tool()
def focus_window(title_or_program: str) -> dict:
    """Bring a window to the front (restores it if minimized).

    Args:
      title_or_program: Part of the window title or the program name, e.g. "Chrome" or "report.docx".
    """
    window, error = _one_window(title_or_program)
    if error:
        return error
    bring_to_front(window["id"])
    return {"focused": window["title"]}


def bring_to_front(hwnd: int) -> bool:
    """Make a window the active one. Windows normally refuses this to background programs, so the agent
    briefly shares input with the current foreground window (AttachThreadInput). The old trick of
    tapping Alt is avoided: it opens the app's menu, and the next paste or Enter would go there."""
    import ctypes
    import win32api
    import win32con
    import win32gui
    user32 = ctypes.windll.user32
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    if user32.GetForegroundWindow() == hwnd:
        return True
    foreground = user32.GetForegroundWindow()
    fg_thread = user32.GetWindowThreadProcessId(foreground, None) if foreground else 0
    own_thread = win32api.GetCurrentThreadId()
    attached = bool(fg_thread and fg_thread != own_thread and user32.AttachThreadInput(own_thread, fg_thread, True))
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(own_thread, fg_thread, False)
    if user32.GetForegroundWindow() == hwnd:
        return True
    # Last resort: a harmless key (F24, which no app uses) counts as input and unlocks the switch.
    win32api.keybd_event(0x87, 0, 0, 0)
    win32api.keybd_event(0x87, 0, win32con.KEYEVENTF_KEYUP, 0)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.05)
    return user32.GetForegroundWindow() == hwnd


def _running_as_admin() -> bool:
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def is_elevated(pid: int) -> bool:
    """True if a process runs as administrator. A normal program can't send keys or clicks to those
    windows (Windows blocks it), so the agent should say so instead of failing silently."""
    if _running_as_admin():
        return False
    try:
        import ctypes
        from ctypes import wintypes
        kernel32, advapi32 = ctypes.windll.kernel32, ctypes.windll.advapi32
        process = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not process:
            return True
        token = wintypes.HANDLE()
        try:
            if not advapi32.OpenProcessToken(process, 0x0008, ctypes.byref(token)):  # TOKEN_QUERY
                return True
            elevation, size = wintypes.DWORD(), wintypes.DWORD()
            ok = advapi32.GetTokenInformation(token, 20, ctypes.byref(elevation), 4, ctypes.byref(size))
            return bool(ok and elevation.value)
        finally:
            if token:
                kernel32.CloseHandle(token)
            kernel32.CloseHandle(process)
    except Exception:
        return False


def _show_window(title_or_program: str, command: int, verb: str) -> dict:
    import win32gui
    window, error = _one_window(title_or_program)
    if error:
        return error
    win32gui.ShowWindow(window["id"], command)
    return {verb: window["title"]}


@tool()
def minimize_window(title_or_program: str) -> dict:
    """Minimize a window.

    Args:
      title_or_program: Part of the window title or the program name.
    """
    return _show_window(title_or_program, 6, "minimized")  # SW_MINIMIZE


@tool()
def maximize_window(title_or_program: str) -> dict:
    """Maximize a window.

    Args:
      title_or_program: Part of the window title or the program name.
    """
    return _show_window(title_or_program, 3, "maximized")  # SW_MAXIMIZE


@tool()
def minimize_all_windows() -> dict:
    """Minimize all windows to show the desktop (like Win+D)."""
    import win32api
    import win32con
    win32api.keybd_event(win32con.VK_LWIN, 0, 0, 0)
    win32api.keybd_event(ord("D"), 0, 0, 0)
    win32api.keybd_event(ord("D"), 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(win32con.VK_LWIN, 0, win32con.KEYEVENTF_KEYUP, 0)
    return {"done": True}


@tool(risk=lambda a: say(f"'{a.get('title_or_program')}' 창을 닫아요. 저장하지 않은 작업이 사라질 수 있어요.",
                         f"Closes the window '{a.get('title_or_program')}' (unsaved work could be lost)"))
def close_window(title_or_program: str) -> dict:
    """Close a window politely, like clicking its X button (the app may ask to save).

    Args:
      title_or_program: Part of the window title or the program name.
    """
    import win32con
    import win32gui
    window, error = _one_window(title_or_program)
    if error:
        return error
    win32gui.PostMessage(window["id"], win32con.WM_CLOSE, 0, 0)
    return {"closed": window["title"]}


@tool(risk=lambda a: say(f"'{a.get('program_name')}' 프로그램을 강제로 꺼요. 저장하지 않은 작업은 사라져요.",
                         f"Force-quits every '{a.get('program_name')}' process. Unsaved work is lost"))
def end_program(program_name: str) -> dict:
    """Force-quit a program that is frozen or won't close, e.g. "chrome.exe".
    Prefer close_window when the program still responds.

    Args:
      program_name: The program's process name, e.g. "chrome.exe" or "notepad".
    """
    import psutil
    target = program_name.lower().strip()
    if not target.endswith(".exe"):
        target += ".exe"
    if target in PROTECTED_PROCESSES:
        return {"error": f"{target} is a core Windows process and must not be ended."}
    ended = 0
    for proc in psutil.process_iter(["name"]):
        if (proc.info["name"] or "").lower() == target:
            try:
                proc.kill()
                ended += 1
            except Exception:
                pass
    if not ended:
        return {"error": f"No running process named {target}"}
    return {"ended_processes": ended}
