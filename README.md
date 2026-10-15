# Desktop Agent

An AI agent for Windows that understands what you **say or type** (Korean, English, German, or a mix)
and does it on your computer: files, apps, settings, **clicking and typing inside any app** by
looking at the screen (Stage 2), and **working on websites in its own browser** (Stage 3):
research, collecting data into Excel, filling forms, downloads, and watching pages for changes.

It lives in the **system tray** (the small icons next to the clock). Hold a hotkey and speak, or type
in the popup. It asks your permission before anything risky, and it can undo file moves.

**Brains:** by default it thinks with a **local AI model in LM Studio** (free, private, no limits).
When the local model is off or gets stuck, a **cheap cloud model** takes over (default: GLM-4.6V from
Z.ai), with a **monthly budget cap**. Voice is transcribed by Gemini's free API: one small request
per voice command.

| Stage | What | Status |
|---|---|---|
| 1 | Voice/text commands, files and folders, apps and windows, system controls, memory, spoken replies | done |
| 2 | Screen control (see, click, type in any app), local brain + cloud backup, cost tracking | done |
| 3 | Web: own browser, research, data to Excel, forms, downloads, page watching | **this version** |
| 4 | Writing into apps, repeatable workflows | next |

---

## 1. Install or update

You need **Windows 10/11** and **Python 3.10+**.

**Updating from an earlier stage?** Quit the agent, copy the new files over the old folder (your
`.env`, `settings.json` and `data` folder are kept), then run **`install.bat`** again to add the new
libraries. Your settings are upgraded automatically.

The web tools use **Microsoft Edge**, which is built into Windows, so no extra browser download is
needed. (Prefer Chrome? Set `"browser_channel": "chrome"` in `settings.json`.)

**New install:** unzip the project to a simple folder such as `C:\Agent`, then double-click
**`install.bat`**. When Notepad opens the `.env` file, paste your keys (see below), save, and close it.

### 1a. Local brain: LM Studio (free)

1. Install **LM Studio** from <https://lmstudio.ai>.
2. In LM Studio, search for **`qwen3-vl-8b`** and download it (pick a **Q4_K_M** version, about 5-6 GB).
   It can read screenshots and use tools, and fits an 8-12 GB graphics card.
3. Go to the **Developer** tab, select the model to load, and before loading set:
   - **Context Length: 16384** at least. For web research **32768** works much better (the
     agent's instructions and tools alone take about 7,500 tokens). With an 8 GB card, turn on
     Flash Attention and K/V cache quantization (Q8) in the load settings, if your LM Studio
     version offers them, to make the larger context fit.
   - **GPU Offload: maximum**
4. Load the model and switch the server **on** (it runs at `http://localhost:1234`).
5. Run **`check_setup.bat`**. It lists the model names LM Studio reports. If the line says
   `Model '...' is not in that list`, copy the exact name into `settings.json` under
   `brains > lmstudio > model`.

LM Studio must be running with the model loaded while you use the agent. If it isn't, the agent
uses the cloud brain instead and tells you.

### 1b. Cloud backup brain: Z.ai GLM (cheap)

1. Create an account at <https://z.ai>, open **API Keys**, create a key.
2. Put it in `.env` as `ZAI_API_KEY=...`
3. Add a small amount of credit in your Z.ai account. The default model `glm-4.6v` costs about
   $0.30 per million input tokens and $0.90 per million output tokens (Z.ai price page, Oct 2026).
   `glm-4.6v-flash` is listed as free: set `"cloud_brain": "glm-flash"` to try it.

### 1c. Voice: Gemini (free)

Keep `GEMINI_API_KEY=...` in `.env` (free at <https://aistudio.google.com/apikey>). It is only used
to turn your voice into text, once per voice command. Without it, typing still works.

Run **`check_setup.bat`** after any change. `[FAIL]` lines tell you what to fix.

## 2. Start

Double-click **`start.bat`**. A round purple icon appears in the tray and the popup opens.

- Start with Windows: double-click **`add_to_startup.bat`** once.
- Something wrong? Use **`start_debug.bat`** to see errors, or open `data\agent.log`.

## 3. Use it

| Do this | To |
|---|---|
| **Hold `Ctrl + Alt + Space`**, speak, release | Voice command (Korean keyboard: use the **left** Alt) |
| `Ctrl + Alt + A` or click the tray icon | Open the popup to type |
| **`Esc`** | Stop the agent immediately |
| Right-click the tray icon | **Brain** (auto / local only / cloud only), this month's cloud cost, new conversation, settings, memory, action log, quit |

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

### How web control works

The agent has **its own browser window** (a separate Edge profile, stored in `data\browser-profile`).
It is separate from your normal browser and its logins. To let the agent use a site that needs
a login, log in **once in that window** when the agent asks; it stays logged in.

Instead of screenshots, the agent reads each page as short text with a number on every link,
button and field, e.g. `[12] link "뉴스"`. The main content comes first, menus and footer last.
It then says "click 12" or "type into 3". That's fast, cheap, and works well even with the local
model. When the layout matters, it can also take a screenshot of the page (`web_look`).

### How screen control works

1. The agent hides its popup and looks at the **front window**.
2. Windows itself tells the agent what buttons, fields and menus that window contains (UI
   Automation). The agent draws a **numbered box** on each one in a screenshot.
3. The AI answers with "click 7" or "type into 3". That is far more reliable than guessing pixel
   positions, especially for small local models.
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
- `Alt+F4`, `Shift+Delete`

**On the web it also:**

- **never types passwords or card numbers, never solves CAPTCHAs, never logs in or pays.** At
  that point it shows the browser and a **"Your turn"** box. Do your part in the browser, then
  click **Done**.
- asks before **submitting a form** (search boxes excepted), before clicking buy / order / send /
  delete-like buttons, and before downloading programs (`.exe`, `.msi`...)
- refuses to open **banking and payment sites** (`web_blocked_sites` in settings: major Korean and
  German banks, Toss, KakaoBank, PayPal; add your own)

**Privacy guards:**

- Screenshots are never taken while a window from `screenshot_blocklist` (password managers,
  banking) is visible, and the agent refuses to read such a window at all.
- The agent treats text on screen, in files and in web pages as *data*, never as orders. This
  matters most on the web, where anyone can write "ignore your instructions and..." on a page.

**Honest limits:** the agent can't know what *every* click does. A button named "OK" in an
online shop can still confirm an order. Watch the first runs in new apps, and remember **Esc**.
Every action is written to `data\actions.log`.

## 5. Brains and costs

| Brain (settings name) | Cost (per 1M tokens, input / output) | Sees screenshots | Notes |
|---|---|---|---|
| `lmstudio` (default local) | free | yes (Qwen3-VL) | private: nothing leaves your PC |
| `glm` (default cloud) | ~$0.30 / $0.90 | yes | Z.ai official price page |
| `glm-flash` | listed as free | yes | rate limits likely |
| `qwen` | ~$0.20 / $1.60 (unverified) | yes | Alibaba Cloud (international) |
| `deepseek` | ~$0.30 / $1.20 (unverified) | no | uses the element list instead of pictures |
| `gemini` | free tier | yes | the free limits that ran out in Stage 1 |

- **Auto mode** (default): the local brain works first. The cloud takes over when LM Studio is off,
  or when the local model is stuck (3 failed actions in a row, or 12 steps without finishing; both
  adjustable). Choose *Local only* in the tray if you never want to pay.
- **Budget:** paid cloud use stops when `cloud_monthly_budget_usd` (default **$6**, about 8,000 KRW) is
  reached. The tray menu shows this month's spending. Details are in `data\usage.json`.
- **Rough cost:** one cloud step sends about 6,000-10,000 tokens (instructions, tools, conversation,
  screenshot). With GLM-4.6V that's around $0.003 per step, so a 5-step task is about 1-2 cents.
  This is an estimate; your real numbers appear in the tray.
- **Prices in `settings.json` are estimates** used for the budget. Correct them if your
  provider's page says otherwise.
- **Privacy:** with a cloud brain, your commands, file contents the agent reads, and screenshots go
  to that company's servers. Z.ai (Zhipu), Alibaba and DeepSeek are Chinese companies. If that
  matters for a task, switch the tray to **Local only** first.

## 6. Settings

Tray > **Edit settings** opens `settings.json`. Save it, then restart the agent (tray > Quit, then `start.bat`).

| Setting | What it does |
|---|---|
| `brain_mode` | `"auto"`, `"local"` or `"cloud"` (also in the tray menu) |
| `local_brain`, `cloud_brain` | Which entries of `brains` to use |
| `brains` | Each brain's address, model name, price, and whether it can see images |
| `escalate_after_steps`, `escalate_after_errors` | When auto mode hands a task to the cloud |
| `cloud_monthly_budget_usd` | Monthly spending cap for paid brains |
| `voice_model` | Gemini model for voice recognition |
| `risky_click_words`, `messaging_apps` | Words and apps that make clicks / Enter ask first |
| `screenshot_blocklist` | Window titles that are never captured |
| `screenshot_max_width` | Screenshot size sent to the AI (smaller = cheaper and faster) |
| `always_confirm_tools`, `never_confirm_tools` | Make any tool always / never ask |
| `push_to_talk_hotkey`, `open_popup_hotkey`, `stop_key` | Shortcuts |
| `speak_replies`, `speech_rate` | Spoken replies |
| `browser_channel`, `browser_executable`, `browser_visible` | Which browser the agent uses, and whether you see it |
| `web_search_engine` | `"google"`, `"naver"`, `"duckduckgo"` or `"bing"` |
| `web_page_chars` | How much page text the AI reads at a time (lower = less memory for the local model) |
| `web_blocked_sites` | Sites the agent must never open |
| `watch_announcement` | What it says when a watched page changes |

Paths in `settings.json` use `\\` for each `\`.

## 7. Troubleshooting

| Problem | Fix |
|---|---|
| "can't reach LM Studio" | Open LM Studio, load the model, switch the server on (Developer tab) |
| "model ... not found" | Run `check_setup.bat`, copy the exact model name into `settings.json` |
| "conversation is too long for the model" | Reload the model in LM Studio with a bigger Context Length; or tray > New conversation |
| Local model is slow | Make sure GPU Offload is at maximum; close games/other GPU apps; try a smaller Context Length |
| Local model clicks the wrong thing | Name the button in your command; or switch to Cloud for that task |
| It clicked inside its own popup / typed in the wrong window | Click the app you want first so it's in front, then give the command |
| "this month's cloud budget is used up" | Raise `cloud_monthly_budget_usd`, or use Local only |
| Hotkey doesn't work | It doesn't work while an *administrator* window (e.g. Task Manager) is in front |
| Can't control an app at all | Apps running as administrator can't be controlled by a normal program |
| "Gemini's free voice limit is used up" | Type instead; it resets daily (about 4-5 pm in Korea) |
| "Could not start a browser" | Set `browser_channel` to `"chrome"` (or `"msedge"`). If neither is installed: `.venv\Scripts\python -m playwright install chromium`, then set `browser_channel` to `""` |
| The site shows a robot check / CAPTCHA | The agent asks you to solve it in its browser window, then continues |
| Web research hands over to the cloud a lot | The local model's context is full: use Context Length 32768 in LM Studio, or lower `web_page_chars` |
| Watched page alerts never come | Watches only run while the agent is running; check `list_watches` ("지켜보는 페이지 보여줘") |

When asking Claude for help, send the error text and the last lines of `data\agent.log`.

## 8. How it works (for the curious)

```
 You (voice / text)
      |
      v
 popup / hotkeys / tray -> App -> worker thread -> Agent loop ------------------+
       (voice -> Gemini -> text)                       |                        |
                                                       v                        |
                                  brain (local LM Studio, or cloud backup)      |
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
| `agent/agent.py` | The agent loop, system prompt, local -> cloud hand-off |
| `agent/brains.py` | OpenAI-compatible brains: retries, budget, image fallback |
| `agent/usage.py` | Monthly token and cost tracking |
| `agent/transcriber.py` | Voice -> text with Gemini |
| `agent/tooling.py` | The `@tool` system (docstring + type hints -> tool description) |
| `agent/safety.py` | Protected folders, action log, stop switch |
| `agent/tools/files.py`, `apps.py`, `system.py`, `memory_tools.py` | Stage 1 actions |
| `agent/tools/screen.py` | Stage 2: look at the screen, click, type, keys, scroll |
| `agent/tools/web.py` | Stage 3: the agent's browser, page reading, forms, tables, downloads, page watching |
| `agent/voice.py`, `agent/ui.py`, `agent/memory.py`, `agent/check.py` | Microphone and speech, popup and tray, memory, setup check |

**Adding a new ability** = one Python function with `@tool(...)`, type hints and a clear docstring
in `agent/tools/`. Every brain sees it automatically.

### Tests

```
.venv\Scripts\python -m pip install pytest
.venv\Scripts\python -m pytest tests
```

The tests simulate the AI, so they need no LM Studio, API key or microphone. `tests/test_web.py`
drives a hidden browser against a small built-in test website (it is skipped if no browser starts).
