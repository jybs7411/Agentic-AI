"""Put an API key into the .env file without editing it by hand.

Run it from install.bat, from the tray menu ("API 키 설정"), or yourself:
    .venv\\Scripts\\python.exe setup_key.py            (choose a service)
    .venv\\Scripts\\python.exe setup_key.py gemini     (straight to Gemini)

It opens the page where you create the key, asks you to paste it, checks it with one free request,
and saves it. The key stays on your computer, in .env.
"""

import shutil
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
EXAMPLE_FILE = ROOT / ".env.example"

SERVICES = {
    "gemini": {
        "name": "Gemini (Google, 무료)", "env": "GEMINI_API_KEY", "page": "https://aistudio.google.com/apikey",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "prefix": "AIza",
        "steps": "Google 계정으로 로그인 → [API 키 만들기 / Create API key] → 만들어진 키 옆의 복사 버튼",
    },
    "zai": {
        "name": "Z.ai GLM", "env": "ZAI_API_KEY", "page": "https://z.ai/manage-apikey/apikey-list",
        "base_url": "https://api.z.ai/api/paas/v4/", "prefix": "",
        "steps": "가입/로그인 → API Keys → [Create a new API key] → 복사",
    },
    "openrouter": {
        "name": "OpenRouter", "env": "OPENROUTER_API_KEY", "page": "https://openrouter.ai/settings/keys",
        "base_url": "https://openrouter.ai/api/v1", "prefix": "sk-or-",
        "steps": "가입/로그인 → Keys → [Create Key] → 복사",
    },
    "deepseek": {
        "name": "DeepSeek", "env": "DEEPSEEK_API_KEY", "page": "https://platform.deepseek.com/api_keys",
        "base_url": "https://api.deepseek.com", "prefix": "sk-",
        "steps": "가입/로그인 → API keys → [Create new API key] → 복사",
    },
    "qwen": {
        "name": "Qwen (Alibaba Cloud)", "env": "DASHSCOPE_API_KEY",
        "page": "https://modelstudio.console.alibabacloud.com/",
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "prefix": "sk-",
        "steps": "가입/로그인 → API Key → [Create API Key] → 복사",
    },
}


def choose() -> str:
    print("어떤 AI의 키를 넣을까요? / Which key?")
    names = list(SERVICES)
    for i, key in enumerate(names, 1):
        print(f"  {i}. {SERVICES[key]['name']}")
    answer = input("번호 (Enter = 1): ").strip() or "1"
    try:
        return names[int(answer) - 1]
    except (ValueError, IndexError):
        print("잘못된 번호예요.")
        return ""


def check_key(service: dict, key: str) -> str:
    """'ok', 'refused', or a short reason why it couldn't be checked."""
    if service["env"] == "OPENROUTER_API_KEY":  # its model list is public, so ask about the key itself
        try:
            import httpx
            response = httpx.get("https://openrouter.ai/api/v1/key", timeout=20,
                                 headers={"Authorization": f"Bearer {key}"})
            return "ok" if response.status_code == 200 else "refused" if response.status_code in (401, 403) \
                else f"HTTP {response.status_code}"
        except Exception as e:  # noqa: BLE001
            return type(e).__name__
    try:
        import openai
        client = openai.OpenAI(api_key=key, base_url=service["base_url"], timeout=20, max_retries=0)
        client.models.list()
        return "ok"
    except Exception as e:  # noqa: BLE001 - any failure is reported, the key is still saved if you want
        status = getattr(e, "status_code", None)
        if status in (400, 401, 403):
            return "refused"
        if status == 404:
            return "ok"  # this service has no model list; the key itself was accepted
        return type(e).__name__


def save_key(env_name: str, key: str):
    if not ENV_FILE.exists():
        if EXAMPLE_FILE.exists():
            shutil.copyfile(EXAMPLE_FILE, ENV_FILE)
        else:
            ENV_FILE.write_text("", encoding="utf-8")
    from dotenv import set_key
    set_key(str(ENV_FILE), env_name, key, quote_mode="never")


def main() -> int:
    print()
    print("=== API 키 설정 / API key setup ===")
    print()
    choice = sys.argv[1].lower() if len(sys.argv) > 1 else choose()
    service = SERVICES.get(choice)
    if not service:
        return 1
    print()
    print(f"{service['name']} 키 만드는 페이지를 브라우저로 열게요.")
    print(f"  방법: {service['steps']}")
    print(f"  페이지: {service['page']}")
    webbrowser.open(service["page"])
    print()
    while True:
        key = input("복사한 키를 여기에 붙여넣고 Enter (마우스 오른쪽 클릭 = 붙여넣기, 빈칸 Enter = 취소):\n> ")
        key = key.strip().strip('"').strip("'")
        if not key:
            print("취소했어요. 키는 바뀌지 않았어요.")
            return 1
        if " " in key or len(key) < 20:
            print("키 같지 않아요. 키 전체를 다시 복사해 주세요.\n")
            continue
        if service["prefix"] and not key.startswith(service["prefix"]):
            print(f"보통 {service['name']} 키는 '{service['prefix']}'로 시작해요. 다른 키를 붙여넣은 것 같아요.")
            if input("그래도 저장할까요? (y/N) ").strip().lower() != "y":
                continue
        print("키를 확인하는 중…")
        result = check_key(service, key)
        if result == "refused":
            print("서비스가 이 키를 거절했어요. 키를 다시 복사해서 붙여넣어 주세요.\n")
            continue
        if result != "ok":
            print(f"지금은 확인하지 못했어요 ({result}). 인터넷 연결 문제일 수 있어요. 일단 저장할게요.")
        save_key(service["env"], key)
        print()
        print(f"저장했어요! ({service['env']}, 파일: {ENV_FILE})")
        print("에이전트가 실행 중이면 다음 명령부터 바로 이 키를 써요.")
        return 0


if __name__ == "__main__":
    try:
        code = main()
    except (KeyboardInterrupt, EOFError):
        code = 1
    input("\n아무 키나 누르면 창이 닫혀요. (Enter)")
    sys.exit(code)
