"""Last steps of install.bat, in Korean: API key, setup check, desktop shortcut, start with Windows."""

import os
import subprocess
import sys

from agent import config


def _ask(question: str) -> bool:
    try:
        return input(f"{question} (Y/n) ").strip().lower() in ("", "y", "yes", "예", "네", "ㅇ")
    except EOFError:
        return False


def _shortcut(folder_script: str, name: str) -> bool:
    """Create a Windows shortcut that starts the agent without a console window."""
    def quoted(value) -> str:  # a PowerShell '...' string (a ' inside is written twice)
        return "'" + str(value).replace("'", "''") + "'"

    pythonw = config.ROOT / ".venv" / "Scripts" / "pythonw.exe"
    script = (
        f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut({folder_script} + {quoted(chr(92) + name + '.lnk')});"
        f"$s.TargetPath = {quoted(pythonw)}; $s.Arguments = '-m agent'; $s.WorkingDirectory = {quoted(config.ROOT)};"
        "$s.Description = 'Desktop Agent'; $s.Save()"
    )
    result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                            capture_output=True)
    return result.returncode == 0


def main():
    sys.path.insert(0, str(config.ROOT))
    print()
    if not config.get_key("GEMINI_API_KEY"):
        print("Gemini API 키(무료)가 필요해요. 지금 넣을게요.")
        import setup_key
        sys.argv = [sys.argv[0], "gemini"]
        setup_key.main()
    else:
        print("Gemini API 키가 이미 있어요.")

    print()
    from agent import check
    check.main()

    if _shortcut("[Environment]::GetFolderPath('Desktop')", "Desktop Agent"):
        print("바탕화면에 'Desktop Agent' 바로가기를 만들었어요.")
    if _ask("Windows를 켤 때 에이전트가 자동으로 시작되게 할까요?"):
        if _shortcut("[Environment]::GetFolderPath('Startup')", "Desktop Agent"):
            print("자동 시작을 켰어요. 끄려면 Win+R → shell:startup → 'Desktop Agent' 삭제.")
    if _ask("지금 에이전트를 시작할까요?"):
        pythonw = config.ROOT / ".venv" / "Scripts" / "pythonw.exe"
        subprocess.Popen([str(pythonw), "-m", "agent"], cwd=str(config.ROOT))
        print("시작했어요. 화면 오른쪽 아래 트레이에 보라색 동그라미 아이콘이 생겨요.")
        print("(안 보이면 작업 표시줄의 ^ 화살표를 눌러 보세요.)")


if __name__ == "__main__":
    if os.name != "nt":
        print("Windows에서 실행하세요.")
        sys.exit(1)
    main()
