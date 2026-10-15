# Desktop Agent

말하거나 입력한 명령(한국어, 영어, 독일어, 섞어도 됨)을 알아듣고 **Windows 컴퓨터에서 직접 해 주는 AI 에이전트**입니다.
파일 정리, 앱 열기, 화면 속 버튼 클릭과 입력, 전용 브라우저로 웹 조사·엑셀 정리·양식 채우기, 선택한 글 다듬기·번역,
워드 문서와 메일 초안, 반복 작업 루틴까지 합니다. 위험한 작업은 **항상 먼저 물어봅니다**.

## 빠른 시작 (한국어)

1. **Python 3.10 이상**을 설치합니다 (<https://www.python.org/downloads/>, 설치 화면에서 **"Add python.exe to PATH"** 체크).
2. 받은 ZIP 파일을 **오른쪽 클릭 → 모두 압축 풀기**로 `C:\Agent` 같은 간단한 폴더에 풉니다.
   (ZIP 안에서 바로 실행하면 안 됩니다.)
3. 폴더 안의 **`install.bat`** 을 더블클릭합니다.
   - "Windows의 PC 보호" 파란 창이 뜨면 **추가 정보 → 실행**을 누르세요. (서명되지 않은 배치 파일이라 뜨는 일반 경고입니다.)
   - 라이브러리 설치(몇 분) → **Gemini API 키 설정**(브라우저가 열리면 키를 만들어 복사 → 검은 창에 붙여넣기) →
     설치 확인(2초 동안 마이크에 말해 보기) → 바탕화면 바로가기 → 자동 시작 여부 → 지금 시작 여부 순서로 진행됩니다.
4. 화면 오른쪽 아래 **트레이의 보라색 동그라미 아이콘**과 작은 창이 나타나면 준비 완료입니다.
   아이콘이 안 보이면 작업 표시줄의 **^** 화살표를 누르세요.

| 이렇게 하면 | 이렇게 돼요 |
|---|---|
| **`Ctrl + Alt + Space`를 누른 채** 말하고 떼기 | 음성 명령 (창의 [말하기] 버튼도 가능) |
| `Ctrl + Alt + A` 또는 트레이 아이콘 클릭 | 입력 창 열기 |
| 아무 앱에서 글을 선택하고 **`Ctrl + Alt + W`** | 다듬기·맞춤법·요약·번역 버튼 |
| **`Esc`** | 즉시 멈추기 |
| 트레이 아이콘 오른쪽 클릭 | 사용법, 기본/백업 AI, API 키 설정, 답변 읽어주기, 검색 엔진, 기억, 작업 기록, 종료 |

**말해 볼 만한 것:** `다운로드 폴더 PDF들 정리해줘` · `메모장 열고 장보기 목록 적어줘` ·
`전기차 배터리 화재 원인 검색해서 요약해줘` · `이 페이지 표를 엑셀로 저장해줘` ·
`김 팀장님께 일정 변경 메일 초안 써줘` · `평일 9시에 뉴스 요약하는 아침 루틴 만들어줘`

**알아 둘 점**
- 메일과 메시지는 **초안만** 만듭니다. 보내기는 직접 누르세요. 비밀번호·카드 번호·로그인·결제는 에이전트가 하지 않고 **[직접 해 주세요]** 창으로 넘깁니다.
- 노란 확인 창의 기본 버튼은 **[아니요]** 입니다. Enter를 그냥 눌러도 실행되지 않아요.
- 무료 Gemini는 하루 사용량이 정해져 있습니다(한국 시간 오후 4~5시쯤 초기화). 다 쓰면 트레이 > **백업 AI**에서 다른 AI를 고르세요.
- 관리자 권한으로 실행된 창(작업 관리자 등)은 조작할 수 없습니다.
- 화면 글자와 버튼 이름은 `settings.json`의 `"ui_language": "en"`으로 영어로 바꿀 수 있습니다.

문제가 생기면 `check_setup.bat`을 실행해 **[실패]** 줄을 확인하세요. 아래는 자세한 설명(영어)입니다.

---

## About (English)

An AI agent for Windows that understands what you **say or type** (Korean, English, German, or a mix)
and does it on your computer: files, apps, settings, **clicking and typing inside any app** by
looking at the screen (Stage 2), **working on websites in its own browser** (Stage 3): research,
collecting data into Excel, filling forms, downloads, watching pages for changes, and **writing and
routines** (Stage 4): fixing or translating selected text in any app, Word documents, email drafts
in your own style, and saved routines that run by name or on a schedule.

It lives in the **system tray** (the small icons next to the clock). Hold a hotkey and speak, or type
in the popup. It asks your permission before anything risky, and it can undo file moves.

**Which AI thinks:** you choose. The **main AI** (default: **Gemini**, free tier) does the work.
An optional **backup AI** takes over when the main one is unavailable. Pick both in the popup
(the "AI:" box) or the tray menu. Choices: Gemini, GLM (Z.ai), Qwen,
DeepSeek, or OpenRouter (one key for GPT, Claude and many more). Paid AIs have a **monthly budget cap**.
Voice is transcribed by Gemini: one small request per voice command.

| Stage | What | Status |
|---|---|---|
| 1 | Voice/text commands, files and folders, apps and windows, system controls, memory, spoken replies | done |
| 2 | Screen control (see, click, type in any app), main + backup AI, cost tracking | done |
| 3 | Web: own browser, research, data to Excel, forms, downloads, page watching | done |
| 4 | Writing: selected text, Word documents, email drafts, your style; routines (recorded or described, scheduled) | **this version** |

---

## 1. Install or update

You need **Windows 10/11** and **Python 3.10+**.

**Updating from an earlier stage?** Quit the agent, copy the new files over the old folder (your
`.env`, `settings.json` and `data` folder are kept), then run **`install.bat`** again to add the new
libraries. Your settings are upgraded automatically.

The web tools use **Microsoft Edge**, which is built into Windows, so no extra browser download is
needed. (Prefer Chrome? Set `"browser_channel": "chrome"` in `settings.json`.)

**New install:** extract the ZIP (right-click > Extract All) to a simple folder such as `C:\Agent`, then
double-click **`install.bat`**. It installs the libraries, opens the Gemini key page and asks you to paste
the key (it checks the key before saving it to `.env`), runs the setup check, puts a **Desktop Agent**
shortcut on the desktop, and asks whether to start with Windows and whether to start now.

If Windows shows "Windows protected your PC" (SmartScreen), click **More info > Run anyway**: the batch
files are not signed. Some antivirus programs warn about the global hotkeys (the `keyboard` library
listens to keys the same way a keylogger would); the agent only reacts to its own shortcuts and never
records your typing.

### 1a. Gemini (default main AI, free)

Run **`setup_key.bat`** (or tray > **API 키 설정 / Set API key**). It opens
<https://aistudio.google.com/apikey>, you create a key and paste it into the window, and it is checked
and saved to `.env` as `GEMINI_API_KEY`. The same key is used for voice recognition. That's all you need
to start. (You can also edit `.env` in Notepad yourself.)

**About the free limits:** each Gemini model has its own free daily and per-minute limits. When
one model's limit is reached, the agent automatically switches to another Gemini Flash model, and
goes back once the limit resets. Only when all of them are used up does the backup AI take over
(or, without a backup, it tells you). Daily limits reset at midnight Pacific time (about 4-5 pm in
Korea). With billing enabled on your Google account, the limits are much higher; then put the real
prices in `settings.json` so the budget counts them.

### 1b. Optional: other AIs (backup or main)

**Z.ai GLM (cheap, good backup):**

1. Create an account at <https://z.ai>, open **API Keys**, create a key.
2. Run `setup_key.bat` and choose Z.ai (or put it in `.env` as `ZAI_API_KEY=...`)
3. Add a small amount of credit in your Z.ai account. The default model `glm-4.6v` costs about
   $0.30 per million input tokens and $0.90 per million output tokens (Z.ai price page, Oct 2026).
   `glm-4.6v-flash` is listed as free: choose "GLM-4.6V-Flash (Z.ai, free)" to try it.

**OpenRouter (one key, many AIs: GPT, Claude, Gemini, Qwen...):** create a key at
<https://openrouter.ai>, add it with `setup_key.bat` (or `OPENROUTER_API_KEY=...` in `.env`), and choose "OpenRouter". The default
model `openrouter/auto` lets OpenRouter pick; to use a specific model, copy its name from
openrouter.ai/models into `settings.json` (`brains > openrouter > model`) together with its price.

**Qwen (Alibaba Cloud)** and **DeepSeek** work the same way (`DASHSCOPE_API_KEY`, `DEEPSEEK_API_KEY`).

A key added or changed while the agent runs is picked up on the next command.

Run **`check_setup.bat`** after any change. `[실패]` lines tell you what to fix.

### 1c. Voices (spoken replies)

Replies are read aloud with the voices installed in Windows. Korean replies need a **Korean voice**:
Settings > Time & language > Speech > **Add voices** > Korean (or: Language & region > add Korean with
"Text-to-speech"). `check_setup.bat` lists the voices the agent can use and warns if Korean is missing.
Some newer voices are only available to Windows' own apps; if the Korean voice doesn't appear in that
list after installing it, sign out and in again. Turn spoken replies on or off in the tray (**답변 읽어주기**).

## 2. Start

Double-click the **Desktop Agent** shortcut (or `start.bat`). A round purple icon appears in the tray and
the popup opens. Hidden icon? Click the **^** arrow next to the tray icons; you can drag the icon onto the taskbar.

- Start with Windows: answer yes during install, or double-click **`add_to_startup.bat`** once.
- Something wrong? Use **`start_debug.bat`** to see errors, or open `data\agent.log`.

## 3. Use it

| Do this | To |
|---|---|
| **Hold `Ctrl + Alt + Space`**, speak, release | Voice command (Korean keyboard: use the **left** Alt) |
| `Ctrl + Alt + A` or click the tray icon | Open the popup to type |
| Select text anywhere, then **`Ctrl + Alt + W`** | Quick actions for that text: 다듬기, 맞춤법, 요약, 한국어로, English, Deutsch, or type/say your own |
| **`Esc`** | Stop the agent immediately |
| "AI:" box at the top of the popup | Choose the main AI |
| Right-click the tray icon | How to use, new conversation, **Main AI**, **Backup AI**, this month's paid-AI cost, set API key, speak replies on/off, search engine, advanced settings, memory, action log, quit |
| Right-click the conversation | Copy, or copy the last answer |

Tray icon color: **purple** = ready, **red** = listening, **yellow** = working.

### Things you can say

Files, apps, system (Stage 1):

- `다운로드 폴더에 있는 PDF들을 "PDF" 폴더로 정리해줘` / `방금 옮긴 거 되돌려줘`
- `크롬 열어줘` / `볼륨 30으로 해줘` / `Öffne den Rechner`

Inside apps (Stage 2):

- `메모장 열고 "회의록"이라고 써줘`
- `지금 화면에 뭐가 있는지 알려줘`
- `이 에러 메시지 읽어줘` (reads the text of the front window)
- `탐색기에서 문서 폴더 열고 정렬을 날짜순으로 바꿔줘`
- `Click the Save button` / `저장 버튼 눌러줘`

On the web (Stage 3):

- `요즘 전기차 배터리 화재 원인에 대해 검색해서 3군데 이상 읽고 요약해줘`
- `다나와랑 쿠팡에서 갤럭시 버즈 가격 찾아서 엑셀로 정리해줘`
- `이 페이지 표를 엑셀로 저장해줘`
- `정부24 전입신고 양식 열어서 내 정보로 채워줘` (it stops before submitting)
- `이 사이트 공지사항 페이지에 새 글 올라오면 알려줘` (checks every hour)
- `Lade den Monatsbericht von dieser Seite herunter`

Writing (Stage 4):

- Select a paragraph in Word or Gmail, press `Ctrl+Alt+W`, click **다듬기**. The text is replaced in place (`Ctrl+Z` undoes it)
- Select text, hold the talk key and say `이거 독일어로 바꿔줘`
- `오늘 회의 내용으로 회의록 워드 파일 만들어줘: 참석자 3명, 예산 확정, 다음 주 금요일 마감`
- `김 팀장님께 회의 일정 변경 메일 초안 써줘` (Gmail opens with the draft filled in; you press Send)
- `내 문서 폴더의 블로그 글 3개 읽고 내 문체 배워줘` (it shows you the description and asks before saving it)

Routines (Stage 4):

- `아침 루틴 만들어줘: 날씨 알려주기, 네이버 뉴스 헤드라인 5개 요약, Gmail 열기. 평일 9시에 실행해줘`
- (after doing a task) `방금 한 거 '보고서 받기'로 저장해줘`
- `보고서 받기 실행해줘` / `루틴 목록 보여줘` / `아침 루틴은 8시 반으로 바꿔줘` / `아침 루틴 지워줘`

### How writing works

- **Selected text:** the agent copies your selection, writes the new version, and pastes it over the
  selection in the same app. Your clipboard is restored afterwards. If the app lost the selection
  in the meantime, the text is inserted at the cursor instead; `Ctrl+Z` in that app undoes it.
  Change or add quick buttons in `settings.json` (`selection_actions`).
- **Your style:** point the agent at a few texts you wrote (files, selected text, or the clipboard). It writes a
  short, concrete description (tone, 존댓말 level, sentence length, typical greetings and closings,
  favourite expressions, per language) to `data\style_guide.md` and follows it for drafts,
  documents and rewrites. You can edit that file in Notepad.
- **Word documents** get real headings, lists, tables and bold text, in a font that shows Korean properly.
- **Emails** open as a pre-filled draft in your normal browser (Gmail by default; Outlook or your mail
  app on request). The agent never sends anything; you do.

### How routines work

| | Described routine | Recorded routine |
|---|---|---|
| Made by | "아침 루틴 만들어줘: ..." (a list of steps in words) | "방금 한 거 저장해줘" (the actions of your previous command) |
| Each run | The AI carries out the steps, adapting to the situation | The actions are replayed directly: fast, very few AI requests |
| Best for | Changing content: news, mail, summaries | Fixed actions: open these apps and sites, click the same buttons, download the same report |

- Recorded routines remember buttons and links **by their name**, so they are found again even when
  the page or window changed a little. If a step still fails, the AI gets the original goal and
  finishes the job itself.
- Replays go through the **same safety checks**: risky steps still ask, and if you say **No** the
  routine stops.
- **Schedules** ("평일 9시", "월,수,금 18:30", "daily 07:00") run only while the agent is running. A run
  missed by more than 15 minutes is skipped until the next scheduled time. Routines are stored in
  `data\routines.json`.

### How web control works

The agent has **its own browser window** (a separate Edge profile, stored in `data\browser-profile`).
It is separate from your normal browser and its logins. To let the agent use a site that needs
a login, log in **once in that window** when the agent asks; it stays logged in.

Instead of screenshots, the agent reads each page as short text with a number on every link,
button and field, e.g. `[12] link "뉴스"`. The main content comes first, menus and footer last.
It then says "click 12" or "type into 3". That's fast and cheap. When the layout matters, it can also take a screenshot of the page (`web_look`).

### How screen control works

1. The agent hides its popup and looks at the **front window**.
2. Windows itself tells the agent what buttons, fields and menus that window contains (UI
   Automation). The agent draws a **numbered box** on each one in a screenshot.
3. The AI answers with "click 7" or "type into 3". That is far more reliable than guessing pixel
   positions.
4. If something has no number (a drawing canvas, some games), it clicks by position (percent of the screen).

Before each click the agent checks that the element is still there. If the screen changed, it
looks again instead of clicking blindly.

**Tips:** put the app you want controlled in front. Things go faster if you name the button
("저장 버튼 눌러"). Multi-monitor setups work: it uses the monitor the front window is on.

## 4. Safety

**Runs automatically:** opening, reading, searching, listing; creating folders; copying; moving and
renaming (undo-able); volume, brightness, settings pages, web pages; looking at the screen; normal
clicks and typing.

**Asks you first** (yellow box, **Yes** / **No**, beep; "No" is the default button):

- deleting (to the Recycle Bin), overwriting, anything in system folders, moving 25+ items
- closing windows, force-quitting programs, running programs or scripts, running commands
- shut down / restart / sleep / sign out
- **clicking a button named like send / 보내기 / delete / 삭제 / buy / 구매 / pay / 결제 / submit / install / 송금 ...**
  (the full list is `risky_click_words` in settings)
- **pressing Enter in messaging apps** (KakaoTalk, Slack, Discord, Teams, Outlook...): that usually *sends*
- `Alt+F4`, `Shift+Delete`, Windows-key shortcuts (`Win+R`...), and pressing Enter or typing in a
  command window (cmd, PowerShell, Windows Terminal)
- opening programs and scripts (`.exe`, `.bat`, `.ps1`, ...); files that are plain documents, pictures,
  music or videos open without asking, anything else asks first
- opening powerful system tools (cmd, PowerShell, Registry Editor, Task Manager, Control Panel...)
- **saving something to memory**, saving your style description, and saving, scheduling or deleting a
  routine (each shows exactly what will be stored)
- opening a web address that carries a lot of data in it, especially after the agent has read a private
  file, the clipboard or the screen in the same command (so nothing private can be smuggled out in a link)
- typing long text into a web page after reading something private
- scheduled routines that nobody answers: a question that is not answered within 3 minutes counts as **No**

**On the web it also:**

- **never types passwords or card numbers, never solves CAPTCHAs, never logs in or pays.** At
  that point it shows the browser and a **"Your turn"** box. Do your part in the browser, then
  click **Done**.
- asks before **submitting a form** (search boxes excepted), before clicking buy / order / send /
  delete-like buttons, and refuses to download programs (`.exe`, `.msi`, scripts...) unless you
  explicitly ask for one; downloads into system or startup folders always ask
- refuses to open **banking and payment sites** (`web_blocked_sites` in settings: major Korean and
  German banks, Toss, KakaoBank, PayPal; add your own)

**Privacy guards:**

- Screenshots are never taken while a window from `screenshot_blocklist` (password managers,
  banking) is visible, and the agent refuses to read such a window at all. Windows of
  `private_programs` (password managers) are never captured or controlled.
- The agent never reads its own secrets: `.env`, `settings.json`, its `data` folder, or key files
  (`.pem`, `.key`, `.kdbx`). Password, PIN, one-time-code and account-number fields on web pages are
  never filled by the agent.
- The action log hides long texts (only their length is written) and anything that looks like a key.
- The agent treats text on screen, in files and in web pages as *data*, never as orders. This
  matters most on the web, where anyone can write "ignore your instructions and..." on a page.

**Honest limits:** the agent can't know what *every* click does. A button named "OK" in an
online shop can still confirm an order. Watch the first runs in new apps, and remember **Esc**.
Every action is written to `data\actions.log`.

## 5. AIs and costs

| AI (settings name) | Cost (per 1M tokens, input / output) | Sees screenshots | Notes |
|---|---|---|---|
| `gemini` (default main) | free tier | yes | switches between Flash models when a limit is reached |
| `glm` | ~$0.30 / $0.90 | yes | Z.ai official price page; good cheap backup |
| `glm-flash` | listed as free | yes | rate limits likely |
| `qwen` | ~$0.20 / $1.60 (unverified) | yes | Alibaba Cloud (international) |
| `deepseek` | ~$0.30 / $1.20 (unverified) | no | uses the element list instead of pictures |
| `openrouter` | depends on the model | depends | one key for many AIs; set the model's price |

- **Main + backup:** the main AI does everything. The backup takes over only when the main one is
  unavailable: limits used up, no key, server error, or budget reached.
- **Suggested setups:** Gemini + GLM backup (free most of the time, a few cents when Gemini's
  limits run out). Gemini + no backup (always free; it stops when the limits run out).
- **Budget:** paid cloud use stops when `cloud_monthly_budget_usd` (default **$6**, about 8,000 KRW) is
  reached. The tray menu shows this month's spending. Details are in `data\usage.json`.
- **Rough cost:** one cloud step sends about 6,000-10,000 tokens (instructions, tools, conversation,
  screenshot). With GLM-4.6V that's around $0.003 per step, so a 5-step task is about 1-2 cents.
  This is an estimate; your real numbers appear in the tray.
- **Prices in `settings.json` are estimates** used for the budget. Correct them if your
  provider's page says otherwise.
- **Privacy:** with any cloud AI, your commands, file contents and web pages the agent reads, and
  screenshots go to that company's servers. On Gemini's free tier Google may use them to improve its
  products. Z.ai (Zhipu), Alibaba and DeepSeek are Chinese companies. Don't let the agent read
  documents or pages you would not want those companies to see.

## 6. Settings

Most everyday options are in the tray menu (AIs, speak replies, search engine, API keys). Tray >
**고급 설정 / Advanced settings** opens `settings.json`. Save it, then restart the agent (tray > Quit,
then the Desktop Agent shortcut). A broken value is replaced by its default instead of stopping the agent.

| Setting | What it does |
|---|---|
| `main_brain`, `backup_brain` | Which entries of `brains` to use (also in the popup and tray menu); `""` = no backup |
| `brains` | Each AI's address, model name, price, whether it can see images, and (Gemini) `auto_switch_models` |
| `cloud_monthly_budget_usd` | Monthly spending cap for paid brains |
| `voice_model` | Gemini model for voice recognition (a "lite" model, so voice doesn't use up the main AI's free limit) |
| `ui_language` | `"ko"` (default) or `"en"`: language of the popup, tray and messages |
| `ui_font_size` | Text size in the popup (default 10). Where you leave the popup is remembered (`popup_geometry`) |
| `max_steps_per_command` | Most AI steps one command may take (default 15) |
| `private_programs` | Programs whose windows are never captured or controlled |
| `risky_click_words`, `messaging_apps` | Words and apps that make clicks / Enter ask first |
| `screenshot_blocklist` | Window titles that are never captured |
| `screenshot_max_width` | Screenshot size sent to the AI (smaller = cheaper and faster) |
| `always_confirm_tools`, `never_confirm_tools` | Make any tool always / never ask |
| `push_to_talk_hotkey`, `open_popup_hotkey`, `stop_key` | Shortcuts |
| `speak_replies`, `speech_rate` | Spoken replies |
| `browser_channel`, `browser_executable`, `browser_visible` | Which browser the agent uses, and whether you see it |
| `web_search_engine` | `"google"`, `"naver"`, `"duckduckgo"` or `"bing"` |
| `web_page_chars` | How much page text the AI reads at a time (lower = fewer tokens) |
| `web_blocked_sites` | Sites the agent must never open |
| `watch_announcement` | What it says when a watched page changes |
| `selection_hotkey`, `selection_actions` | The selected-text shortcut and its quick buttons (label -> instruction) |

Paths in `settings.json` use `\\` for each `\`.

## 7. Troubleshooting

| Problem | Fix |
|---|---|
| "model ... not found" | Run `check_setup.bat`, copy the exact model name into `settings.json` |
| "conversation is too long for the model" | Tray > New conversation |
| It clicks the wrong thing | Name the button in your command ("저장 버튼 눌러") |
| It clicked inside its own popup / typed in the wrong window | Click the app you want first so it's in front, then give the command |
| "this month's cloud budget is used up" | Raise `cloud_monthly_budget_usd`, or choose a free AI |
| "Gemini: usage limit reached" | All free Gemini models are used up for now. Choose a backup AI in the tray, or wait for the reset |
| "... needs an API key" after choosing an AI | Tray > Set API key (or `setup_key.bat`); it's used from the next command |
| Hotkey doesn't work | It doesn't work while an *administrator* window (e.g. Task Manager) is in front |
| "마이크에서 소리가 들리지 않아요" / No sound from the microphone | Unmute it, pick the right input device in Windows sound settings, and allow desktop apps under Settings > Privacy > Microphone. `check_setup.bat` tests it |
| I can't find the tray icon | Click the **^** arrow next to the clock; drag the purple icon onto the taskbar to keep it visible |
| "Windows protected your PC" | Click **More info > Run anyway** (the files are not signed) |
| Antivirus warns about the agent | The hotkey library listens to the keyboard; allow the agent folder if you trust it |
| Can't control an app at all | Apps running as administrator can't be controlled by a normal program |
| "Gemini's free voice limit is used up" | Type instead; it resets daily (about 4-5 pm in Korea) |
| "Could not start a browser" | Set `browser_channel` to `"chrome"` (or `"msedge"`). If neither is installed: `.venv\Scripts\python -m playwright install chromium`, then set `browser_channel` to `""` |
| The site shows a robot check / CAPTCHA | The agent asks you to solve it in its browser window, then continues |
| Watched page alerts never come | Watches only run while the agent is running; check `list_watches` ("지켜보는 페이지 보여줘") |
| "No text is selected" with `Ctrl+Alt+W` | Highlight the text first. Some apps block copying; then copy it yourself and say "클립보드 글 다듬어줘" |
| `Ctrl+Alt+W` types a strange character | Your keyboard layout uses Ctrl+Alt (AltGr) for that key: change `selection_hotkey` in settings |
| The replaced text went to the wrong place | Click into the text again, select it, and retry; `Ctrl+Z` in the app undoes the paste |
| A scheduled routine didn't run | The agent must be running at that time (see `add_to_startup.bat`); check `루틴 목록 보여줘` |

When asking Claude for help, send the error text and the last lines of `data\agent.log`.

## 8. How it works (for the curious)

```
 You (voice / text)
      |
      v
 popup / hotkeys / tray -> App -> worker thread -> Agent loop ------------------+
       (voice -> Gemini -> text)                       |                        |
                                                       v                        |
                                  AI (main, or backup if main is unavailable)   |
                                         answers, or calls tools                |
                                                       |                        |
                                                       v                        |
                                  safety check -> ask you? -> run tool ---------+
                                  (look_at_screen adds a numbered screenshot)
                                                       |
                                                       v
                                         short answer, shown + spoken
```

| File | Role |
|---|---|
| `agent/app.py` | Starts everything, the worker thread, tray brain menu |
| `agent/agent.py` | The agent loop, system prompt, main -> backup hand-off |
| `agent/brains.py` | OpenAI-compatible AIs: main/backup, Gemini model switching, retries, budget, image fallback |
| `agent/usage.py` | Monthly token and cost tracking |
| `agent/transcriber.py` | Voice -> text with Gemini |
| `agent/tooling.py` | The `@tool` system (docstring + type hints -> tool description) |
| `agent/safety.py` | Protected folders, action log, stop switch |
| `agent/tools/files.py`, `apps.py`, `system.py`, `memory_tools.py` | Stage 1 actions |
| `agent/tools/screen.py` | Stage 2: look at the screen, click, type, keys, scroll |
| `agent/tools/web.py` | Stage 3: the agent's browser, page reading, forms, tables, downloads, page watching |
| `agent/tools/writing.py` | Stage 4: selected text, Word documents, email drafts, style guide |
| `agent/tools/routines.py` | Stage 4: saving, scheduling and replaying routines |
| `agent/voice.py`, `agent/ui.py`, `agent/memory.py`, `agent/check.py` | Microphone and speech, popup and tray, memory, setup check |
| `agent/texts.py` | Every text you see, in Korean and English |
| `agent/clipboard.py` | Saves and restores the clipboard (text, pictures, copied files) around copy/paste |
| `setup_key.py`, `agent/setup_finish.py` | API key helper; last steps of the installer |

**Adding a new ability** = one Python function with `@tool(...)`, type hints and a clear docstring
in `agent/tools/`. Every brain sees it automatically.

### Tests

```
.venv\Scripts\python -m pip install pytest
.venv\Scripts\python -m pytest tests
```

The tests simulate the AI, so they need no API key or microphone. `tests/test_web.py`
drives a hidden browser against a small built-in test website (it is skipped if no browser starts).
`tests/test_app.py` checks the wiring between the app, popup and tray with stand-ins for the Windows parts.
