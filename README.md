# Desktop Agent

An AI agent for Windows that understands what you **say or type** (Korean, English, German, or a mix)
and does it on your computer, using the free Gemini API.

It lives in the **system tray** (the small icons next to the clock). Hold a hotkey and speak, or type
in the popup. It asks your permission before anything risky, and it can undo file moves.

> **Stage 1** (this version): voice and text commands, files and folders, apps and windows, system
> controls, memory, spoken replies.
> Coming next: Stage 2 (screen vision, mouse and keyboard control), Stage 3 (web automation),
> Stage 4 (writing into apps).

---

## 1. Install (one time)

You need **Windows 10/11**, **Python 3.10+** and a **Gemini API key** (free at
<https://aistudio.google.com/apikey>).

1. Download this project: on GitHub click **Code > Download ZIP**, then unzip it somewhere simple,
   for example `C:\Agent`. Avoid folders that contain Korean characters or spaces if you can.
2. Double-click **`install.bat`**. It sets everything up, which takes a few minutes the first time.
3. When Notepad opens, paste your key after `GEMINI_API_KEY=`, then save with `Ctrl+S` and close Notepad.
4. A check runs automatically. Every line should say `[ OK ]` (`[WARN]` is fine).

If anything says `[FAIL]`, the line under it tells you how to fix it. Run **`check_setup.bat`** again
any time.

## 2. Start

Double-click **`start.bat`**. A round purple icon appears in the tray and the popup opens.

- Want it to start with Windows? Double-click **`add_to_startup.bat`** once.
- Something wrong? Use **`start_debug.bat`** instead, which shows errors in a black window.

## 3. Use it

| Do this | To |
|---|---|
| **Hold `Ctrl + Alt + Space`**, speak, then release | Give a voice command |
| `Ctrl + Alt + A` (or click the tray icon) | Open the popup to type |
| **`Esc`** | Stop the agent immediately |
| Right-click the tray icon | New conversation, settings, memory, action log, quit |

> **Korean keyboard:** the right `Alt` key is the 한/영 key, so use the **left** `Ctrl` + **left** `Alt` + `Space`.

The tray icon's color shows what it's doing: **purple** = ready, **red** = listening,
**yellow** = working.

### Things you can say

- `다운로드 폴더에 있는 PDF들을 "PDF" 폴더로 정리해줘`
- `어제 수정한 보고서 찾아서 요약해줘`
- `크롬 열어줘` / `메모장 닫아줘` / `볼륨 30으로 해줘` / `화면 밝기 70`
- `방금 옮긴 거 되돌려줘` (undo)
- `기억해: 내 프로젝트 폴더는 D:\Work야` (it remembers this next time too)
- `Find the biggest files on my desktop`
- `Öffne den Rechner` / `Wie viel Speicherplatz habe ich noch?`
- `What's using all my memory?`

## 4. Safety: what it may do alone, and what it asks first

**Runs automatically:** opening, reading, searching, listing; creating folders; copying; moving and
renaming (these can be undone); volume, brightness, settings pages, web pages.

**Asks you first** (a yellow box with **Yes** / **No**, and a beep):

- deleting (it goes to the **Recycle Bin**, so you can restore it)
- replacing or overwriting an existing file (the old one goes to the Recycle Bin)
- anything inside system folders (`C:\Windows`, `Program Files`, `AppData`, ...)
- moving more than 25 items at once
- closing windows (unsaved work) and force-quitting programs
- running `.exe`, `.bat` or script files
- running commands
- shut down, restart, sleep, sign out

**No** is the default button, so pressing Enter by accident never approves anything.

Other safety features:

- **Undo:** every move and rename is recorded. Say "undo that" / "되돌려줘".
- **Action log:** every action is written to `data\actions.log` (tray > *Open action log*).
- **Step limit:** a command stops after 20 steps.
- **Prompt-injection guard:** the agent is told that text inside files, web pages and command output
  is *data*, not orders. If a document says "delete everything", it reports this to you and does nothing.

You can make it stricter or looser in `settings.json` (below).

## 5. Settings

Tray > **Edit settings** opens `settings.json`. Save it, then restart the agent (tray > Quit, then `start.bat`).

| Setting | What it does |
|---|---|
| `model` | Gemini model. `gemini-flash-latest` always points to Google's newest Flash model |
| `push_to_talk_hotkey`, `open_popup_hotkey`, `stop_key` | Your shortcuts |
| `speak_replies`, `speech_rate` | Spoken replies on/off, speed from -10 to 10 |
| `always_confirm_tools` | Tool names that must always ask, e.g. `["move_item", "move_many"]` |
| `never_confirm_tools` | Tool names that never ask (careful!) |
| `extra_protected_folders` | Your own "ask before touching" folders, e.g. `["D:\\Important"]` |
| `max_steps_per_command` | Safety limit per command |
| `conversation_turns_to_keep` | How many recent commands it keeps in mind |

`settings.json` uses `\\` for each `\` in paths.

## 6. Voices (spoken replies)

Replies are read aloud with the voices installed in Windows. The agent picks a Korean, German or
English voice to match the language of the reply. If no voice is installed for a language, that
reply is only shown, not spoken.

**To add a voice:** Settings > Time & language > Speech > *Manage voices* > **Add voices**, then choose Korean
(한국어) or German (Deutsch). Then run `check_setup.bat` to see which voices the agent can use.

Some newer Windows voices don't appear to older programs. If the voice you added doesn't show in
`check_setup.bat`, tell me (Claude) and I'll switch the agent to the newer Windows voice system.

## 7. About the free Gemini API

- **Limits.** Every step of a task is one request, and the free tier allows only a limited number of
  requests per minute and per day. When the per-minute limit is hit, the agent waits and shows a
  countdown. When the daily limit is hit, it switches to another free Flash model if one is
  available. Daily limits reset at midnight Pacific time (about 4–5 pm in Korea). See your exact
  limits in Google AI Studio.
- **Privacy.** On the free tier, Google may use what you send (your commands, file contents the agent
  reads and, in Stage 2, screenshots) to improve its products, and people may review it. Don't ask it
  to read documents you would not want Google to see. A paid key changes these terms.
- **Model names change often.** If your model stops working, the agent picks another available Flash
  model automatically and tells you.

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| Nothing happens when I double-click `start.bat` | Run `start_debug.bat` and read the error, or open `data\agent.log` |
| Hotkey doesn't work | It doesn't work while an *administrator* window is in front (e.g. Task Manager). Click elsewhere first. Check that no other program uses the same shortcut |
| "No microphone found" | Settings > Privacy & security > Microphone: allow **desktop apps** to use it |
| "Too short - hold the keys while you speak" | Keep holding until you finish talking |
| "Your Gemini API key is not valid" | Re-copy the key into `.env` with no spaces or quotes |
| "The agent is already running" | Look for the round icon in the tray (click ^ next to the clock) |
| It opened the wrong app | Say the exact Start-menu name, or ask "list my apps with 'adobe'" |

When asking Claude for help, send the text of the error and the last lines of `data\agent.log`.

## 9. How it works (for the curious)

```
 You (voice / text)
      |
      v
 popup / hotkeys / tray ---> App ---> Agent loop ---------------------+
                                          |                           |
                                          v                           |
                                Gemini: answer, or call tools         |
                                          |                           |
                                          v                           |
                         safety check -> ask you? -> run tool --------+
                                          |
                                          v
                            short answer, shown + spoken
```

| File | Role |
|---|---|
| `agent/app.py` | Starts everything and connects the parts |
| `agent/agent.py` | The agent loop and its instructions (system prompt) |
| `agent/brain.py` | Gemini connection: rate limits, retries, model fallback |
| `agent/tooling.py` | The `@tool` system: a docstring becomes the tool's description for Gemini |
| `agent/safety.py` | Protected folders, action log, stop switch |
| `agent/tools/*.py` | The actual actions (files, apps, system, memory) |
| `agent/voice.py` | Microphone recording and spoken replies |
| `agent/ui.py` | The popup and the tray icon |
| `agent/memory.py` | Long-term memory (`data\memory.json`, editable in Notepad) |
| `agent/check.py` | The setup checker |

**Adding a new ability** = writing one Python function with `@tool(...)` and a clear docstring in
`agent/tools/`. Gemini sees it automatically.

### Tests

```
.venv\Scripts\python -m pip install pytest
.venv\Scripts\python -m pytest tests
```

The tests simulate Gemini, so they need no API key or microphone.
