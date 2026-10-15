"""Everything the USER sees, in Korean and English ("ui_language" in settings).

Only user-facing text lives here. What the AI reads (system prompt, tool descriptions, tool results)
stays in English on purpose: models follow English instructions most reliably.
"""

LANGUAGE = {"current": "ko"}

TEXTS = {
    # --- popup
    "ready": {"ko": "준비됨", "en": "Ready"},
    "stop_button": {"ko": "중지 (Esc)", "en": "Stop (Esc)"},
    "send": {"ko": "보내기", "en": "Send"},
    "mic": {"ko": "말하기", "en": "Mic"},
    "mic_done": {"ko": "끝", "en": "Done"},
    "ai_label": {"ko": "AI:", "en": "AI:"},
    "no_key_suffix": {"ko": " (키 없음)", "en": " (no key)"},
    "placeholder": {"ko": "무엇을 도와드릴까요? 입력하거나 {talk}를 누른 채 말하세요",
                    "en": "What can I do for you? Type, or hold {talk} and speak"},
    "you_prefix": {"ko": "나: ", "en": "You: "},
    "voice_prefix": {"ko": "나 (음성): ", "en": "You (voice): "},
    "copy": {"ko": "복사", "en": "Copy"},
    "copy_answer": {"ko": "답변 복사", "en": "Copy answer"},
    "copied": {"ko": "복사했어요.", "en": "Copied."},
    "details": {"ko": "자세히", "en": "Details"},
    "close": {"ko": "닫기", "en": "Close"},
    "confirm_title": {"ko": "이 작업을 할까요?", "en": "Allow this action?"},
    "yes_default": {"ko": "네, 진행", "en": "Yes, do it"},
    "no": {"ko": "아니요", "en": "No"},
    "your_turn_title": {"ko": "직접 해 주세요", "en": "Your turn"},
    "your_turn_body": {"ko": "브라우저에서 끝낸 뒤 [완료]를 눌러 주세요. 비밀번호와 결제 정보는 에이전트가 보거나 저장하지 않아요.",
                       "en": "When you are finished in the browser, click Done. The agent never sees or stores "
                             "passwords or payment details."},
    "done": {"ko": "완료", "en": "Done"},
    "cancel": {"ko": "취소", "en": "Cancel"},
    "selection_header": {"ko": "\"{window}\"에서 선택한 글 ({n}자):", "en": "Selected in \"{window}\" ({n} chars):"},
    "selection_hint": {"ko": "버튼을 누르거나, 원하는 작업을 입력하거나 말하세요.",
                       "en": "Pick an action, or type / say what to do with it."},

    # --- status line
    "thinking": {"ko": "생각 중 · {step}단계 · {brain}", "en": "Thinking · step {step} · {brain}"},
    "listening": {"ko": "듣고 있어요… 키를 떼면 보내요", "en": "Listening... release to send"},
    "listening_button": {"ko": "듣고 있어요… [끝]을 누르면 보내요", "en": "Listening... click Done to send"},
    "recognizing": {"ko": "음성 인식 중…", "en": "Recognizing speech..."},
    "stopping": {"ko": "멈추는 중…", "en": "Stopping..."},
    "retrying": {"ko": "다른 방법으로 다시 시도 중…", "en": "Trying another way..."},
    "waiting_limit": {"ko": "{why} · {left}초 기다리는 중 (Esc로 중지)", "en": "{why} - waiting {left}s (Esc to stop)"},
    "limit_reason": {"ko": "사용 한도 도달", "en": "Rate limit reached"},
    "server_reason": {"ko": "서버가 바빠요", "en": "Server busy"},
    "network_reason": {"ko": "연결 문제", "en": "Connection problem"},

    # --- messages in the log
    "welcome": {"ko": "준비됐어요. {talk}를 누른 채 말하거나 아래에 입력하세요. 멈추려면 {stop}. AI: {ai}",
                "en": "Ready. Hold {talk} and speak, or type below. Press {stop} to stop me. AI: {ai}"},
    "busy": {"ko": "아직 이전 명령을 처리 중이에요. 멈추려면 Esc를 누르세요.",
             "en": "Still working on the last command. Press Esc to stop it first."},
    "stopped": {"ko": "멈췄어요.", "en": "Stopped."},
    "skipped": {"ko": "건너뛰었어요.", "en": "Skipped (you said no)."},
    "new_conversation": {"ko": "새 대화를 시작했어요.", "en": "New conversation started."},
    "too_many_steps": {"ko": "단계가 너무 많아 멈췄어요. 어떻게 계속할지 알려 주세요.",
                       "en": "I stopped because this took too many steps. Tell me how to continue."},
    "repeating": {"ko": "같은 동작을 반복하고 있어서 멈췄어요. 다르게 설명해 주세요.",
                  "en": "I stopped because I kept repeating the same action. Please rephrase."},
    "unexpected": {"ko": "예상치 못한 문제가 생겼어요. 다시 시도해 보세요. (자세한 내용: data\\agent.log)",
                   "en": "Unexpected problem. Please try again. (details in data\\agent.log)"},
    "didnt_hear": {"ko": "잘 못 들었어요. 마이크에 조금 더 가까이 대고 다시 말해 주세요.",
                   "en": "I didn't catch that. Try again, a bit closer to the microphone."},
    "silent_mic": {"ko": "마이크에서 소리가 들리지 않아요. 마이크가 꺼져 있거나 Windows 마이크 권한이 꺼져 있을 수 있어요.",
                   "en": "No sound from the microphone. It may be muted, or Windows microphone access may be off."},
    "too_short": {"ko": "너무 짧아요. 말하는 동안 키를 계속 누르고 있어 주세요.",
                  "en": "Too short - hold the keys while you speak."},
    "mic_problem": {"ko": "마이크 문제: {error}", "en": "Microphone problem: {error}"},
    "no_selection": {"ko": "선택된 글이 없어요. 글을 드래그해서 선택한 뒤 {key}를 다시 눌러 주세요.",
                     "en": "No text is selected. Highlight some text, then press {key} again."},
    "selection_failed": {"ko": "선택한 글을 가져오지 못했어요: {error}", "en": "Could not read the selection: {error}"},
    "ai_changed": {"ko": "AI: {ai}", "en": "AI: {ai}"},
    "no_backup": {"ko": "백업 없음", "en": "no backup"},
    "backup": {"ko": "백업: {name}", "en": "backup: {name}"},
    "needs_key": {"ko": "{ai}를 쓰려면 API 키가 필요해요. 트레이 > API 키 설정에서 넣어 주세요. 다음 명령부터 바로 쓸 수 있어요.",
                  "en": "{ai} needs an API key. Use tray > Set API key. It's used from the next command."},
    "switching_brain": {"ko": "{reason}\n{ai}로 이어서 할게요.", "en": "{reason}\nSwitching to {ai}."},
    "routine_start": {"ko": "[루틴] 예약된 '{name}' 시작", "en": "[Routine] Starting '{name}' (scheduled)"},
    "routine_done": {"ko": "[루틴] '{name}' 완료 ({n}단계)", "en": "[Routine] '{name}' finished ({n} steps)"},
    "watch_new": {"ko": "[지켜보기] {message}", "en": "[Watch] {message}"},
    "watch_failed": {"ko": "[지켜보기] {url} 확인 실패: {error} (나중에 다시 시도해요)",
                     "en": "[Watch] Could not check {url}: {error} (will retry later)"},
    "replaced": {"ko": "바꿔 넣었어요. 되돌리려면 그 앱에서 Ctrl+Z.", "en": "Replaced. Press Ctrl+Z in that app to undo."},
    "settings_restart": {"ko": "settings.json을 저장한 뒤 에이전트를 다시 시작하세요.",
                         "en": "Save settings.json, then restart the agent."},
    "speak_on": {"ko": "답변을 소리로 읽어 줄게요.", "en": "Replies will be spoken."},
    "speak_off": {"ko": "답변을 소리 없이 보여 줄게요.", "en": "Replies will not be spoken."},
    "search_engine_set": {"ko": "검색 엔진: {name}", "en": "Search engine: {name}"},
    "admin_window": {"ko": "관리자 권한으로 실행된 창은 조작할 수 없어요.", "en": "Windows running as administrator can't be controlled."},

    # --- tray
    "tray_open": {"ko": "열기", "en": "Open"},
    "tray_new": {"ko": "새 대화", "en": "New conversation"},
    "tray_main_ai": {"ko": "기본 AI", "en": "Main AI"},
    "tray_backup_ai": {"ko": "백업 AI", "en": "Backup AI"},
    "tray_none": {"ko": "없음", "en": "None"},
    "tray_cost": {"ko": "유료 AI 이번 달: ${spent:.2f} / ${budget:.2f} (약 {krw:,}원)",
                  "en": "Paid AI this month: ${spent:.2f} / ${budget:.2f}"},
    "tray_speak": {"ko": "답변 읽어주기", "en": "Speak replies"},
    "tray_search": {"ko": "검색 엔진", "en": "Search engine"},
    "tray_api_key": {"ko": "API 키 설정", "en": "Set API key"},
    "tray_help": {"ko": "사용법", "en": "How to use"},
    "tray_settings": {"ko": "고급 설정 (settings.json)", "en": "Advanced settings (settings.json)"},
    "tray_memory": {"ko": "기억 보기", "en": "Open memory"},
    "tray_log": {"ko": "작업 기록", "en": "Open action log"},
    "tray_quit": {"ko": "종료", "en": "Quit"},

    # --- AI errors (shown to the user, never to the AI)
    "err_no_key": {"ko": "{ai}: API 키가 없어요. 트레이 > API 키 설정에서 넣어 주세요.",
                   "en": "{ai}: no API key. Use tray > Set API key."},
    "err_key_refused": {"ko": "{ai}: API 키가 맞지 않아요. 트레이 > API 키 설정에서 다시 넣어 주세요.",
                        "en": "{ai}: the API key was refused. Set it again in tray > Set API key."},
    "err_limit": {"ko": "{ai}: 무료 사용량을 다 썼어요. Gemini는 한국 시간 오후 4~5시쯤 초기화돼요. "
                        "트레이 > 백업 AI에서 다른 AI를 고르면 바로 계속할 수 있어요.",
                  "en": "{ai}: usage limit reached. Gemini resets around midnight Pacific time. "
                        "Pick a backup AI in the tray to continue now."},
    "err_budget": {"ko": "{ai}: 이번 달 유료 AI 예산을 다 썼어요 (settings.json의 cloud_monthly_budget_usd).",
                   "en": "{ai}: this month's paid-AI budget is used up (cloud_monthly_budget_usd)."},
    "err_model": {"ko": "{ai}: 모델 '{model}'을(를) 찾을 수 없어요. check_setup.bat으로 사용 가능한 이름을 확인하세요.",
                  "en": "{ai}: model '{model}' not found. Run check_setup.bat to see available names."},
    "err_too_long": {"ko": "{ai}: 대화가 너무 길어졌어요. 트레이 > 새 대화를 눌러 주세요.",
                     "en": "{ai}: the conversation is too long. Use tray > New conversation."},
    "err_network": {"ko": "{ai}: 연결할 수 없어요. 인터넷 연결을 확인하세요.", "en": "{ai}: can't connect. Check your internet."},
    "err_server": {"ko": "{ai}: 서버 오류예요. 잠시 후 다시 시도하세요.", "en": "{ai}: server error. Try again in a moment."},
    "err_rejected": {"ko": "{ai}가 요청을 거절했어요: {detail}", "en": "{ai} rejected the request: {detail}"},
    "err_blocked": {"ko": "{ai}의 안전 필터가 답변을 막았어요. 다르게 표현해 보세요.",
                    "en": "{ai}'s safety filter blocked the answer. Try rephrasing."},
    "err_empty": {"ko": "{ai}가 빈 답변을 보냈어요. 다시 시도해 보세요.", "en": "{ai} returned an empty answer. Please try again."},
    "err_unknown_ai": {"ko": "알 수 없는 AI '{name}'. 트레이 메뉴에서 고르세요.", "en": "Unknown AI '{name}'. Pick one in the tray menu."},
    "voice_no_key": {"ko": "음성 인식에는 Gemini 키가 필요해요. 트레이 > API 키 설정. 입력은 키 없이도 돼요.",
                     "en": "Voice needs a Gemini key (tray > Set API key). Typing still works."},
    "voice_limit": {"ko": "오늘 Gemini 음성 인식 무료 한도를 다 썼어요. 입력해서 명령해 주세요.",
                    "en": "Gemini's free voice limit is used up for today. Type your command instead."},
    "voice_failed": {"ko": "음성 인식에 실패했어요: {detail}", "en": "Voice recognition failed: {detail}"},
}

# What each tool does, in plain words: (log line while it runs, confirmation title, "yes" button).
# Tools not listed show their technical name.
FRIENDLY = {
    "delete_item": ({"ko": "삭제", "en": "Deleting"}, {"ko": "휴지통으로 옮길까요?", "en": "Move to the Recycle Bin?"},
                    {"ko": "네, 삭제", "en": "Yes, delete"}),
    "move_item": ({"ko": "이동", "en": "Moving"}, {"ko": "옮길까요?", "en": "Move this?"}, {"ko": "네, 이동", "en": "Yes, move"}),
    "move_many": ({"ko": "여러 항목 이동", "en": "Moving items"}, {"ko": "여러 항목을 옮길까요?", "en": "Move these items?"},
                  {"ko": "네, 이동", "en": "Yes, move"}),
    "copy_item": ({"ko": "복사", "en": "Copying"}, {"ko": "복사할까요?", "en": "Copy this?"}, {"ko": "네, 복사", "en": "Yes, copy"}),
    "rename_item": ({"ko": "이름 바꾸기", "en": "Renaming"}, {"ko": "이름을 바꿀까요?", "en": "Rename this?"},
                    {"ko": "네, 바꾸기", "en": "Yes, rename"}),
    "write_text_file": ({"ko": "파일 저장", "en": "Saving a file"}, {"ko": "파일을 덮어쓸까요?", "en": "Overwrite the file?"},
                        {"ko": "네, 저장", "en": "Yes, save"}),
    "create_folder": ({"ko": "폴더 만들기", "en": "Creating a folder"}, None, None),
    "open_path": ({"ko": "열기", "en": "Opening"}, {"ko": "이 파일을 실행할까요?", "en": "Run this file?"},
                  {"ko": "네, 실행", "en": "Yes, run"}),
    "run_command": ({"ko": "명령 실행", "en": "Running a command"},
                    {"ko": "시스템 명령을 실행할까요? (전문가용)", "en": "Run a system command? (advanced)"},
                    {"ko": "네, 실행", "en": "Yes, run"}),
    "open_app": ({"ko": "앱 열기", "en": "Opening an app"}, {"ko": "이 프로그램을 열까요?", "en": "Open this program?"},
                 {"ko": "네, 열기", "en": "Yes, open"}),
    "close_window": ({"ko": "창 닫기", "en": "Closing a window"}, {"ko": "창을 닫을까요?", "en": "Close the window?"},
                     {"ko": "네, 닫기", "en": "Yes, close"}),
    "end_program": ({"ko": "프로그램 강제 종료", "en": "Force-quitting"}, {"ko": "프로그램을 강제로 끌까요?", "en": "Force-quit?"},
                    {"ko": "네, 종료", "en": "Yes, quit it"}),
    "power_action": ({"ko": "전원", "en": "Power"}, {"ko": "전원 작업을 할까요?", "en": "Power action?"},
                     {"ko": "네, 진행", "en": "Yes"}),
    "look_at_screen": ({"ko": "화면 확인", "en": "Looking at the screen"}, None, None),
    "read_screen_text": ({"ko": "화면 글 읽기", "en": "Reading the screen"}, None, None),
    "click_element": ({"ko": "클릭", "en": "Clicking"}, {"ko": "이 버튼을 누를까요?", "en": "Click this?"},
                      {"ko": "네, 누르기", "en": "Yes, click"}),
    "find_and_click": ({"ko": "클릭", "en": "Clicking"}, {"ko": "이 버튼을 누를까요?", "en": "Click this?"},
                       {"ko": "네, 누르기", "en": "Yes, click"}),
    "click_at": ({"ko": "클릭", "en": "Clicking"}, {"ko": "여기를 누를까요?", "en": "Click here?"}, {"ko": "네, 누르기", "en": "Yes, click"}),
    "type_into_element": ({"ko": "입력", "en": "Typing"}, {"ko": "입력할까요?", "en": "Type this?"}, {"ko": "네, 입력", "en": "Yes, type"}),
    "type_text": ({"ko": "입력", "en": "Typing"}, {"ko": "입력할까요?", "en": "Type this?"}, {"ko": "네, 입력", "en": "Yes, type"}),
    "press_keys": ({"ko": "키 누르기", "en": "Pressing keys"}, {"ko": "이 키를 누를까요?", "en": "Press these keys?"},
                   {"ko": "네, 누르기", "en": "Yes, press"}),
    "web_open": ({"ko": "웹페이지 열기", "en": "Opening a page"}, {"ko": "이 주소를 열까요?", "en": "Open this address?"},
                 {"ko": "네, 열기", "en": "Yes, open"}),
    "web_search": ({"ko": "웹 검색", "en": "Searching the web"}, None, None),
    "web_read": ({"ko": "페이지 읽기", "en": "Reading the page"}, None, None),
    "web_click": ({"ko": "웹페이지 클릭", "en": "Clicking on the page"}, {"ko": "이 버튼을 누를까요?", "en": "Click this?"},
                  {"ko": "네, 누르기", "en": "Yes, click"}),
    "web_type": ({"ko": "웹페이지 입력", "en": "Typing on the page"}, {"ko": "입력하고 제출할까요?", "en": "Type and submit?"},
                 {"ko": "네, 진행", "en": "Yes"}),
    "web_download": ({"ko": "다운로드", "en": "Downloading"}, {"ko": "이 파일을 받을까요?", "en": "Download this file?"},
                     {"ko": "네, 받기", "en": "Yes, download"}),
    "open_url": ({"ko": "브라우저로 열기", "en": "Opening in your browser"}, {"ko": "이 주소를 열까요?", "en": "Open this address?"},
                 {"ko": "네, 열기", "en": "Yes, open"}),
    "watch_page": ({"ko": "페이지 지켜보기", "en": "Watching a page"}, {"ko": "이 페이지를 지켜볼까요?", "en": "Watch this page?"},
                   {"ko": "네, 지켜보기", "en": "Yes, watch"}),
    "remember": ({"ko": "기억하기", "en": "Remembering"}, {"ko": "이 내용을 기억할까요?", "en": "Remember this?"},
                 {"ko": "네, 기억", "en": "Yes, remember"}),
    "forget": ({"ko": "기억 지우기", "en": "Forgetting"}, {"ko": "이 기억을 지울까요?", "en": "Forget this?"},
               {"ko": "네, 지우기", "en": "Yes, forget"}),
    "save_style_guide": ({"ko": "문체 저장", "en": "Saving your style"}, {"ko": "이 문체 설명을 저장할까요?", "en": "Save this style?"},
                         {"ko": "네, 저장", "en": "Yes, save"}),
    "routine": ({"ko": "루틴", "en": "Routine"}, {"ko": "이 루틴을 저장할까요?", "en": "Save this routine?"},
                {"ko": "네, 저장", "en": "Yes, save"}),
    "create_word_document": ({"ko": "워드 문서 만들기", "en": "Creating a Word document"},
                             {"ko": "기존 파일을 덮어쓸까요?", "en": "Overwrite the existing file?"},
                             {"ko": "네, 저장", "en": "Yes, save"}),
    "save_spreadsheet": ({"ko": "엑셀 저장", "en": "Saving a spreadsheet"}, {"ko": "기존 파일을 덮어쓸까요?", "en": "Overwrite?"},
                         {"ko": "네, 저장", "en": "Yes, save"}),
    "web_save_table": ({"ko": "표 저장", "en": "Saving the table"}, {"ko": "기존 파일을 덮어쓸까요?", "en": "Overwrite?"},
                       {"ko": "네, 저장", "en": "Yes, save"}),
    "get_selected_text": ({"ko": "선택한 글 가져오기", "en": "Reading the selection"}, None, None),
    "replace_selected_text": ({"ko": "선택한 글 바꾸기", "en": "Replacing the selection"}, None, None),
    "read_file": ({"ko": "파일 읽기", "en": "Reading a file"}, None, None),
    "find_files": ({"ko": "파일 찾기", "en": "Finding files"}, None, None),
    "list_folder": ({"ko": "폴더 보기", "en": "Listing a folder"}, None, None),
    "set_volume": ({"ko": "볼륨 조절", "en": "Setting the volume"}, None, None),
    "run_routine": ({"ko": "루틴 실행", "en": "Running a routine"}, None, None),
}


def set_language(code: str):
    LANGUAGE["current"] = "en" if str(code).lower().startswith("en") else "ko"


def t(key: str, **values) -> str:
    entry = TEXTS.get(key)
    if entry is None:
        return key
    text = entry.get(LANGUAGE["current"]) or entry["en"]
    try:
        return text.format(**values)
    except (KeyError, IndexError, ValueError):
        return text


def friendly(tool_name: str):
    """(log phrase, confirmation title, yes-button text) for a tool, in the current language."""
    key = tool_name
    if tool_name in ("save_routine", "record_routine", "set_routine_schedule", "delete_routine"):
        key = "routine"
    entry = FRIENDLY.get(key)
    lang = LANGUAGE["current"]
    if entry is None:
        return tool_name, t("confirm_title"), t("yes_default")
    phrase, title, yes = entry
    return (phrase[lang] if phrase else tool_name,
            title[lang] if title else t("confirm_title"),
            yes[lang] if yes else t("yes_default"))


def say(ko: str, en: str) -> str:
    """Inline two-language text, for messages that only appear in one place (e.g. risk reasons)."""
    return en if LANGUAGE["current"] == "en" else ko
