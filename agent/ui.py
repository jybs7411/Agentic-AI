"""The popup window (tkinter) and the system tray icon (pystray).

tkinter only allows changes from its own thread, so other threads (the agent, hotkeys, tray)
never touch widgets directly: they call Popup.call(...), which queues the change for the UI thread.

Layout (top to bottom): header (status, stop) - AI choice - conversation - [selected-text panel] -
[confirmation box] - input row. The input row and the boxes above it are packed from the bottom
first, so they always stay visible however large the text or the Windows display scaling is.
"""

import queue
import threading
import time
import tkinter as tk
from tkinter import scrolledtext, ttk

from agent.texts import t

BASE_WIDTH, BASE_HEIGHT = 460, 600

COLORS = {
    "bg": "#f6f5fb", "panel": "#ffffff", "accent": "#5b3fd1", "text": "#1d1b26", "muted": "#6b6880",
    "error": "#c62828", "info": "#8a5300", "confirm": "#fff4d6", "selection": "#eef3ff", "placeholder": "#9a97ab",
}


class Popup:
    def __init__(self, stop, on_send, on_mic, on_stop, brains=(), current_brain="", on_brain_change=None,
                 font_size: int = 10, geometry: str = "", on_geometry=None, talk_key: str = ""):
        self.stop = stop
        self.brains = list(brains)  # [(name, label)]
        self.on_brain_change = on_brain_change or (lambda name: None)
        self.on_send = on_send
        self.on_mic = on_mic
        self.on_stop = on_stop
        self.on_geometry = on_geometry or (lambda geometry: None)
        self._calls = queue.Queue()
        self._confirm_result = None
        self._confirm_event = threading.Event()
        self._last_answer = ""
        self._placeholder = t("placeholder", talk=talk_key)
        self._showing_placeholder = False

        self.font = ("Malgun Gothic", font_size)  # Windows font with Korean support
        self.font_bold = ("Malgun Gothic", font_size, "bold")
        self.font_small = ("Malgun Gothic", max(8, font_size - 1))

        root = self.root = tk.Tk()
        root.title("Agent")
        root.configure(bg=COLORS["bg"])
        root.attributes("-topmost", True)
        root.protocol("WM_DELETE_WINDOW", self.hide)
        root.minsize(320, 300)
        self._place(geometry)

        # --- header: status + stop
        header = tk.Frame(root, bg=COLORS["accent"])
        header.pack(side="top", fill="x")
        self.stop_button = tk.Button(header, text=t("stop_button"), command=self.on_stop, relief="flat",
                                     bg="#ffffff", fg=COLORS["accent"], font=self.font_small, padx=8, state="disabled")
        self.stop_button.pack(side="right", padx=8, pady=4)
        self.status_label = tk.Label(header, text=t("ready"), fg="white", bg=COLORS["accent"], font=self.font_bold,
                                     anchor="w", padx=10, pady=6)
        self.status_label.pack(side="left", fill="x", expand=True)

        # --- which AI thinks (main AI); the backup AI is chosen in the tray menu
        brain_row = tk.Frame(root, bg=COLORS["bg"])
        brain_row.pack(side="top", fill="x", padx=8, pady=(6, 0))
        tk.Label(brain_row, text=t("ai_label"), bg=COLORS["bg"], fg=COLORS["muted"],
                 font=self.font_small).pack(side="left")
        self.brain_var = tk.StringVar(value=self._label_of(current_brain))
        self.brain_box = ttk.Combobox(brain_row, textvariable=self.brain_var, state="readonly", font=self.font_small,
                                      values=[label for _, label in self.brains], width=32)
        self.brain_box.pack(side="left", padx=(4, 0))
        self.brain_box.bind("<<ComboboxSelected>>", self._brain_selected)

        # --- input row (packed from the bottom first, so it is always visible)
        self.input_row = tk.Frame(root, bg=COLORS["bg"])
        self.input_row.pack(side="bottom", fill="x", padx=8, pady=(4, 8))
        self.entry = tk.Entry(self.input_row, font=self.font, relief="flat")
        self.entry.pack(side="left", fill="x", expand=True, ipady=6)
        self.entry.bind("<Return>", lambda _: self._send())
        self.entry.bind("<FocusIn>", lambda _: self._clear_placeholder())
        self.entry.bind("<FocusOut>", lambda _: self._set_placeholder())
        self.mic_button = tk.Button(self.input_row, text=t("mic"), width=6, command=self.on_mic, font=self.font_small)
        self.mic_button.pack(side="left", padx=(6, 0))
        tk.Button(self.input_row, text=t("send"), width=6, bg=COLORS["accent"], fg="white", font=self.font_small,
                  command=self._send).pack(side="left", padx=(6, 0))
        self._set_placeholder()

        # --- confirmation box (hidden until needed)
        self.confirm_frame = tk.Frame(root, bg=COLORS["confirm"], padx=10, pady=8,
                                      highlightbackground="#e0b84d", highlightthickness=1)
        self.confirm_title = tk.Label(self.confirm_frame, text=t("confirm_title"), bg=COLORS["confirm"],
                                      font=("Malgun Gothic", font_size + 1, "bold"), anchor="w")
        self.confirm_title.pack(fill="x")
        self.confirm_text = tk.Label(self.confirm_frame, text="", bg=COLORS["confirm"], font=self.font,
                                     justify="left", anchor="w")
        self.confirm_text.pack(fill="x", pady=(2, 4))
        self.confirm_details = tk.Text(self.confirm_frame, height=4, font=("Consolas", max(8, font_size - 1)),
                                       wrap="word", relief="flat", bg="#fffaf0")
        self.confirm_buttons = tk.Frame(self.confirm_frame, bg=COLORS["confirm"])
        self.confirm_buttons.pack(fill="x", side="bottom")
        self.no_button = tk.Button(self.confirm_buttons, text=t("no"), width=10, font=self.font,
                                   command=lambda: self._answer(False))
        self.no_button.pack(side="right", padx=4)
        self.yes_button = tk.Button(self.confirm_buttons, text=t("yes_default"), width=12, bg="#2e7d32", fg="white",
                                    font=self.font, command=lambda: self._answer(True))
        self.yes_button.pack(side="right", padx=4)

        # --- selected-text panel (hidden until the selection hotkey is used)
        self.selection_frame = tk.Frame(root, bg=COLORS["selection"], padx=10, pady=8,
                                        highlightbackground="#9db4ff", highlightthickness=1)
        self.selection_label = tk.Label(self.selection_frame, text="", bg=COLORS["selection"], font=self.font_small,
                                        justify="left", anchor="w")
        self.selection_label.pack(fill="x")
        self.selection_buttons = tk.Frame(self.selection_frame, bg=COLORS["selection"])
        self.selection_buttons.pack(fill="x", pady=(6, 0))

        # --- conversation log (takes the remaining space)
        self.log = scrolledtext.ScrolledText(root, wrap="word", font=self.font, bg=COLORS["panel"], height=6,
                                             fg=COLORS["text"], relief="flat", padx=10, pady=8, state="disabled")
        self.log.pack(side="top", fill="both", expand=True, padx=8, pady=(8, 4))
        self.log.tag_config("you", foreground=COLORS["accent"], font=self.font_bold, spacing1=8)
        self.log.tag_config("agent", foreground=COLORS["text"], spacing1=4)
        self.log.tag_config("action", foreground=COLORS["muted"], font=self.font_small, lmargin1=14, lmargin2=14)
        self.log.tag_config("error", foreground=COLORS["error"], font=self.font_small, lmargin1=14, lmargin2=14)
        self.log.tag_config("info", foreground=COLORS["info"], font=self.font_small, lmargin1=14, lmargin2=14)
        menu = tk.Menu(root, tearoff=0)
        menu.add_command(label=t("copy"), command=self._copy_selection)
        menu.add_command(label=t("copy_answer"), command=self._copy_answer)
        self.log.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))

        root.bind("<Configure>", self._on_configure)
        root.after(50, self._drain)

    # ------------------------------------------------------------------ thread-safe API

    def call(self, fn, *args):
        """Run fn(*args) on the UI thread."""
        self._calls.put((fn, args))

    def show(self, kind: str, text: str):
        self.call(self._append, kind, text)

    def status(self, text: str):
        self.call(self.status_label.config, {"text": text})

    def set_busy(self, busy: bool):
        self.call(self.stop_button.config, {"state": "normal" if busy else "disabled"})

    def set_brain(self, name: str):
        self.call(self.brain_var.set, self._label_of(name))

    def set_mic_active(self, active: bool):
        self.call(self.mic_button.config, {"text": t("mic_done") if active else t("mic"),
                                           "bg": "#c62828" if active else "SystemButtonFace",
                                           "fg": "white" if active else "black"})

    def show_selection(self, text: str, window: str, actions: dict):
        """Show the captured selection with quick-action buttons (called from any thread)."""
        self.call(self._show_selection, text, window, actions)

    def confirm(self, reason: str, details: str = "", title: str = None, yes_text: str = None,
                no_text: str = None, timeout: float = None, focus: bool = True) -> bool:
        """Ask Yes/No and wait for the answer (called from the agent thread). With a timeout (scheduled
        runs nobody watches), no answer means No."""
        self._confirm_event.clear()
        self._confirm_result = False
        self.call(self._show_confirm, reason, details, title or t("confirm_title"), yes_text or t("yes_default"),
                  no_text or t("no"), focus)
        deadline = time.time() + timeout if timeout else None
        while not self._confirm_event.wait(0.2):
            if self.stop.pressed or (deadline and time.time() > deadline):
                self.call(self._hide_confirm)
                return False
        return self._confirm_result

    def show_window(self, focus: bool = False):
        self.call(self._show_window, focus)

    def hide(self):
        self.root.withdraw()

    def hide_and_wait(self):
        """Hide the popup before the agent looks at or clicks the screen (called from the worker)."""
        if not self._visible():
            return
        done = threading.Event()

        def do():
            self.root.withdraw()
            done.set()

        self.call(do)
        done.wait(1.0)
        time.sleep(0.2)  # let the windows underneath repaint

    def run(self):
        self.root.mainloop()

    # ------------------------------------------------------------------ UI-thread internals

    def _drain(self):
        try:
            while True:
                fn, args = self._calls.get_nowait()
                try:
                    fn(*args)
                except tk.TclError:
                    pass
        except queue.Empty:
            pass
        self.root.after(50, self._drain)

    def _append(self, kind: str, text: str):
        prefix = {"you": t("you_prefix"), "voice": t("voice_prefix"), "action": "· ", "error": "! "}.get(kind, "")
        tag = "you" if kind == "voice" else kind
        if kind == "agent":
            self._last_answer = text
        self.log.config(state="normal")
        self.log.insert("end", prefix + text + "\n", tag)
        self.log.config(state="disabled")
        self.log.see("end")

    def _copy_selection(self):
        try:
            text = self.log.get("sel.first", "sel.last")
        except tk.TclError:
            text = ""
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)

    def _copy_answer(self):
        if self._last_answer:
            self.root.clipboard_clear()
            self.root.clipboard_append(self._last_answer)
            self._append("info", t("copied"))

    def _show_confirm(self, reason: str, details: str, title: str, yes_text: str, no_text: str, focus: bool):
        self.confirm_title.config(text=title)
        self.yes_button.config(text=yes_text)
        self.no_button.config(text=no_text)
        self.confirm_text.config(text=reason)
        self.confirm_details.config(state="normal")
        self.confirm_details.delete("1.0", "end")
        if details:
            self.confirm_details.insert("1.0", details)
            self.confirm_details.config(height=min(6, max(2, details.count("\n") + 1)))
            self.confirm_details.pack(fill="x", pady=(0, 6), before=self.confirm_buttons)
        else:
            self.confirm_details.pack_forget()
        self.confirm_details.config(state="disabled")  # read-only, but scrollable and selectable
        self.confirm_frame.pack(side="bottom", fill="x", padx=8, pady=4, before=self.input_row)
        self._show_window(focus=focus)
        if focus:
            self.no_button.focus_set()  # Enter/Space on the default button means "No": the safe choice
        try:
            import winsound
            winsound.MessageBeep(0x30)  # MB_ICONEXCLAMATION
        except Exception:
            pass

    def _hide_confirm(self):
        self.confirm_frame.pack_forget()

    def _answer(self, approved: bool):
        self._confirm_result = approved
        self._hide_confirm()
        self._confirm_event.set()

    def _show_selection(self, text: str, window: str, actions: dict):
        preview = " ".join(text.split())
        preview = preview[:160] + ("…" if len(preview) > 160 else "")
        self.selection_label.config(text=t("selection_header", window=window[:40], n=len(text)) + "\n" + preview
                                    + "\n" + t("selection_hint"))
        for child in self.selection_buttons.winfo_children():
            child.destroy()
        row = None
        for i, (label, command) in enumerate(actions.items()):
            if i % 3 == 0:
                row = tk.Frame(self.selection_buttons, bg=COLORS["selection"])
                row.pack(fill="x")
            tk.Button(row, text=label, width=12, font=self.font_small,
                      command=lambda c=command, lab=label: self._selection_action(c, lab)).pack(side="left", padx=2, pady=2)
        tk.Button(self.selection_buttons, text=t("close"), font=self.font_small, relief="flat", bg=COLORS["selection"],
                  command=self.selection_frame.pack_forget).pack(anchor="e")
        self.selection_frame.pack(side="bottom", fill="x", padx=8, pady=4, before=self.input_row)
        self._show_window(focus=True)

    def _selection_action(self, command: str, label: str):
        self.selection_frame.pack_forget()
        self.on_send(command, shown=f"[{label}]")

    def _brain_selected(self, _event=None):
        label = self.brain_var.get()
        name = next((n for n, lab in self.brains if lab == label), None)
        if name:
            self.on_brain_change(name)
        self.entry.focus_set()

    def _label_of(self, name: str) -> str:
        return next((label for n, label in self.brains if n == name), name)

    def _visible(self) -> bool:
        try:
            return self.root.state() != "withdrawn"
        except tk.TclError:
            return False

    def _show_window(self, focus: bool):
        previous = _foreground_window()
        self.root.deiconify()
        self.root.lift()
        if focus:
            self.root.focus_force()
            _activate(self.root)  # Windows blocks focus_force for background programs
            if not self.confirm_frame.winfo_ismapped():
                self._clear_placeholder()
                self.entry.focus_set()
        elif previous:
            _set_foreground(previous)  # show the popup but leave the keyboard with the app you were using

    def _send(self):
        if self._showing_placeholder:
            return
        text = self.entry.get().strip()
        if text:
            self.entry.delete(0, "end")
            self.selection_frame.pack_forget()
            self.on_send(text)

    def _set_placeholder(self):
        try:
            focused = self.root.focus_get() is self.entry
        except (KeyError, tk.TclError):
            focused = False
        if not self.entry.get() and not focused:
            self.entry.insert(0, self._placeholder)
            self.entry.config(fg=COLORS["placeholder"])
            self._showing_placeholder = True

    def _clear_placeholder(self):
        if self._showing_placeholder:
            self.entry.delete(0, "end")
            self.entry.config(fg=COLORS["text"])
            self._showing_placeholder = False

    def _on_configure(self, event):
        if event.widget is not self.root:
            return
        width = max(200, self.root.winfo_width() - 60)
        self.confirm_text.config(wraplength=width)
        self.selection_label.config(wraplength=width)
        if self._visible():
            self.on_geometry(self.root.geometry())

    def _place(self, geometry: str):
        """Size the popup for the display scaling, and put it bottom-right above the taskbar (or where
        you left it last time, if that is still on screen)."""
        scale = max(1.0, self.root.winfo_fpixels("1i") / 96)
        left, top, right, bottom = _work_area(self.root)
        if geometry:
            try:
                size, x, y = geometry.split("+")[0], int(geometry.split("+")[1]), int(geometry.split("+")[2])
                if left - 50 <= x < right - 100 and top - 50 <= y < bottom - 100:
                    self.root.geometry(f"{size}+{x}+{y}")
                    return
            except (IndexError, ValueError):
                pass
        width = min(int(BASE_WIDTH * scale), right - left - 20)
        height = min(int(BASE_HEIGHT * scale), bottom - top - 20)
        self.root.geometry(f"{width}x{height}+{right - width - 12}+{bottom - height - 12}")


def _work_area(root):
    """The part of the main screen not covered by the taskbar."""
    try:
        import ctypes
        from ctypes import wintypes
        rect = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)  # SPI_GETWORKAREA
        return rect.left, rect.top, rect.right, rect.bottom
    except Exception:
        return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight() - 60


def _foreground_window():
    try:
        import ctypes
        return ctypes.windll.user32.GetForegroundWindow()
    except Exception:
        return None


def _set_foreground(hwnd):
    try:
        import ctypes
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


def _activate(root):
    try:
        from agent.tools.apps import bring_to_front
        bring_to_front(int(root.wm_frame(), 16))
    except Exception:
        pass


# ---------------------------------------------------------------------- tray icon

def _icon_image(color: str):
    from PIL import Image, ImageDraw
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((4, 4, 60, 60), fill=color)
    draw.ellipse((24, 24, 40, 40), fill="white")
    return image


class Tray:
    def __init__(self, on_open, on_new_conversation, on_settings, on_memory, on_log, on_quit,
                 brains, get_main, set_main, get_backup, set_backup, cost_text,
                 get_speak, toggle_speak, get_engine, set_engine, on_api_key, on_help):
        import pystray
        self._lock = threading.Lock()
        self._state = "normal"
        self.normal_image = _icon_image(COLORS["accent"])
        self.listening_image = _icon_image("#c62828")
        self.busy_image = _icon_image("#e0a100")

        def choice(label, value, get, set_):
            return pystray.MenuItem(label, lambda: set_(value), checked=lambda item: get() == value, radio=True)

        main_items = [choice(label, name, get_main, set_main) for name, label in brains]
        backup_items = [choice(t("tray_none"), "", get_backup, set_backup)] + [
            choice(label, name, get_backup, set_backup) for name, label in brains]
        engines = [choice(label, key, get_engine, set_engine)
                   for key, label in (("google", "Google"), ("naver", "Naver"), ("duckduckgo", "DuckDuckGo"),
                                      ("bing", "Bing"))]

        menu = pystray.Menu(
            pystray.MenuItem(t("tray_open"), lambda: on_open(), default=True),
            pystray.MenuItem(t("tray_new"), lambda: on_new_conversation()),
            pystray.MenuItem(t("tray_help"), lambda: on_help()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(t("tray_main_ai"), pystray.Menu(*main_items)),
            pystray.MenuItem(t("tray_backup_ai"), pystray.Menu(*backup_items)),
            pystray.MenuItem(lambda item: cost_text(), lambda: None, enabled=False),
            pystray.MenuItem(t("tray_api_key"), lambda: on_api_key()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(t("tray_speak"), lambda: toggle_speak(), checked=lambda item: get_speak()),
            pystray.MenuItem(t("tray_search"), pystray.Menu(*engines)),
            pystray.MenuItem(t("tray_settings"), lambda: on_settings()),
            pystray.MenuItem(t("tray_memory"), lambda: on_memory()),
            pystray.MenuItem(t("tray_log"), lambda: on_log()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(t("tray_quit"), lambda: on_quit()),
        )
        self.icon = pystray.Icon("desktop-agent", self.normal_image, "Desktop Agent", menu)
        self.icon.run_detached()

    def set_state(self, state: str):
        """Icon colour: normal / listening / busy. Thread-safe."""
        with self._lock:
            if state == self._state:
                return
            self._state = state
            self.icon.icon = {"listening": self.listening_image, "busy": self.busy_image}.get(state, self.normal_image)

    def refresh_menu(self):
        """Redraw the menu (cost line, checked items). Thread-safe."""
        with self._lock:
            try:
                self.icon.update_menu()
            except Exception:
                pass

    def stop(self):
        self.icon.stop()
