"""The popup window (tkinter) and the system tray icon (pystray).

tkinter only allows changes from its own thread, so other threads (the agent, hotkeys, tray)
never touch widgets directly: they call Popup.call(...), which queues the change for the UI thread.
"""

import queue
import threading
import time
import tkinter as tk
from tkinter import scrolledtext, ttk

FONT = ("Malgun Gothic", 10)  # Windows font with Korean support
FONT_BOLD = ("Malgun Gothic", 10, "bold")
FONT_SMALL = ("Malgun Gothic", 9)
WIDTH, HEIGHT = 440, 560

COLORS = {
    "bg": "#f6f5fb", "panel": "#ffffff", "accent": "#5b3fd1", "text": "#1d1b26",
    "muted": "#6b6880", "error": "#c62828", "info": "#a15c00", "confirm": "#fff4d6",
}


class Popup:
    def __init__(self, stop, on_send, on_mic, on_stop, brains=(), current_brain="", on_brain_change=None):
        self.stop = stop
        self.brains = list(brains)  # [(name, label)]
        self.on_brain_change = on_brain_change or (lambda name: None)
        self.on_send = on_send
        self.on_mic = on_mic
        self.on_stop = on_stop
        self._calls = queue.Queue()
        self._confirm_result = None
        self._confirm_event = threading.Event()

        root = self.root = tk.Tk()
        root.title("Agent")
        root.configure(bg=COLORS["bg"])
        root.attributes("-topmost", True)
        root.protocol("WM_DELETE_WINDOW", self.hide)
        self._place_bottom_right()

        # --- header: status + stop button
        header = tk.Frame(root, bg=COLORS["accent"])
        header.pack(fill="x")
        self.status_label = tk.Label(header, text="Ready", fg="white", bg=COLORS["accent"], font=FONT_BOLD,
                                     anchor="w", padx=10, pady=6)
        self.status_label.pack(side="left", fill="x", expand=True)
        tk.Button(header, text="Stop (Esc)", command=self.on_stop, relief="flat", bg="#ffffff",
                  fg=COLORS["accent"], font=FONT_SMALL, padx=8).pack(side="right", padx=8, pady=4)

        # --- which AI thinks (main AI); the backup AI is chosen in the tray menu
        brain_row = tk.Frame(root, bg=COLORS["bg"])
        brain_row.pack(fill="x", padx=8, pady=(6, 0))
        tk.Label(brain_row, text="AI:", bg=COLORS["bg"], fg=COLORS["muted"], font=FONT_SMALL).pack(side="left")
        self.brain_var = tk.StringVar(value=self._label_of(current_brain))
        self.brain_box = ttk.Combobox(brain_row, textvariable=self.brain_var, state="readonly", font=FONT_SMALL,
                                      values=[label for _, label in self.brains], width=34)
        self.brain_box.pack(side="left", padx=(4, 0))
        self.brain_box.bind("<<ComboboxSelected>>", self._brain_selected)

        # --- conversation log
        self.log = scrolledtext.ScrolledText(root, wrap="word", font=FONT, bg=COLORS["panel"],
                                             fg=COLORS["text"], relief="flat", padx=10, pady=8, state="disabled")
        self.log.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        self.log.tag_config("you", foreground=COLORS["accent"], font=FONT_BOLD, spacing1=8)
        self.log.tag_config("agent", foreground=COLORS["text"], spacing1=4)
        self.log.tag_config("action", foreground=COLORS["muted"], font=FONT_SMALL, lmargin1=14, lmargin2=14)
        self.log.tag_config("error", foreground=COLORS["error"], font=FONT_SMALL, lmargin1=14, lmargin2=14)
        self.log.tag_config("info", foreground=COLORS["info"], font=FONT_SMALL, lmargin1=14, lmargin2=14)

        # --- confirmation box (hidden until needed)
        self.confirm_frame = tk.Frame(root, bg=COLORS["confirm"], padx=10, pady=8,
                                      highlightbackground="#e0b84d", highlightthickness=1)
        self.confirm_title = tk.Label(self.confirm_frame, text="Allow this action?", bg=COLORS["confirm"],
                                      font=FONT_BOLD, anchor="w")
        self.confirm_title.pack(fill="x")
        self.confirm_text = tk.Label(self.confirm_frame, text="", bg=COLORS["confirm"], font=FONT_SMALL,
                                     justify="left", anchor="w", wraplength=WIDTH - 50)
        self.confirm_text.pack(fill="x", pady=(2, 6))
        buttons = tk.Frame(self.confirm_frame, bg=COLORS["confirm"])
        buttons.pack(fill="x")
        self.no_button = tk.Button(buttons, text="No", width=10, command=lambda: self._answer(False))
        self.no_button.pack(side="right", padx=4)
        self.yes_button = tk.Button(buttons, text="Yes, do it", width=10, bg="#2e7d32", fg="white",
                                    command=lambda: self._answer(True))
        self.yes_button.pack(side="right", padx=4)

        # --- selected-text panel (hidden until the selection hotkey is used)
        self.selection_frame = tk.Frame(root, bg="#eef3ff", padx=10, pady=8,
                                        highlightbackground="#9db4ff", highlightthickness=1)
        self.selection_label = tk.Label(self.selection_frame, text="", bg="#eef3ff", font=FONT_SMALL,
                                        justify="left", anchor="w", wraplength=WIDTH - 50)
        self.selection_label.pack(fill="x")
        self.selection_buttons = tk.Frame(self.selection_frame, bg="#eef3ff")
        self.selection_buttons.pack(fill="x", pady=(6, 0))

        # --- input row
        self.input_row = tk.Frame(root, bg=COLORS["bg"])
        self.input_row.pack(fill="x", padx=8, pady=(4, 8))
        self.entry = tk.Entry(self.input_row, font=FONT, relief="flat")
        self.entry.pack(side="left", fill="x", expand=True, ipady=6)
        self.entry.bind("<Return>", lambda _: self._send())
        self.mic_button = tk.Button(self.input_row, text="Mic", width=5, command=self.on_mic)
        self.mic_button.pack(side="left", padx=(6, 0))
        tk.Button(self.input_row, text="Send", width=6, bg=COLORS["accent"], fg="white",
                  command=self._send).pack(side="left", padx=(6, 0))

        root.after(50, self._drain)

    # ------------------------------------------------------------------ thread-safe API

    def call(self, fn, *args):
        """Run fn(*args) on the UI thread."""
        self._calls.put((fn, args))

    def show(self, kind: str, text: str):
        self.call(self._append, kind, text)

    def status(self, text: str):
        self.call(self.status_label.config, {"text": text})

    def show_selection(self, text: str, window: str, actions: dict):
        """Show the captured selection with quick-action buttons (called from any thread)."""
        self.call(self._show_selection, text, window, actions)

    def _show_selection(self, text: str, window: str, actions: dict):
        preview = " ".join(text.split())
        preview = preview[:160] + ("..." if len(preview) > 160 else "")
        self.selection_label.config(text=f'Selected in "{window[:40]}" ({len(text)} chars):\n{preview}\n'
                                         "Pick an action, or type / say what to do with it.")
        for child in self.selection_buttons.winfo_children():
            child.destroy()
        row = None
        for i, (label, command) in enumerate(actions.items()):
            if i % 3 == 0:
                row = tk.Frame(self.selection_buttons, bg="#eef3ff")
                row.pack(fill="x")
            tk.Button(row, text=label, width=12, font=FONT_SMALL,
                      command=lambda c=command: self._selection_action(c)).pack(side="left", padx=2, pady=2)
        tk.Button(self.selection_buttons, text="Close", font=FONT_SMALL, relief="flat", bg="#eef3ff",
                  command=self.selection_frame.pack_forget).pack(anchor="e")
        self.selection_frame.pack(fill="x", padx=8, pady=4, before=self.input_row)
        self._show_window(focus=True)

    def _selection_action(self, command: str):
        self.selection_frame.pack_forget()
        self.on_send(command)

    def set_brain(self, name: str):
        self.call(self.brain_var.set, self._label_of(name))

    def _label_of(self, name: str) -> str:
        return next((label for n, label in self.brains if n == name), name)

    def _brain_selected(self, _event=None):
        label = self.brain_var.get()
        name = next((n for n, lab in self.brains if lab == label), None)
        if name:
            self.on_brain_change(name)
        self.entry.focus_set()

    def set_mic_active(self, active: bool):
        self.call(self.mic_button.config, {"text": "Done" if active else "Mic",
                                           "bg": "#c62828" if active else "SystemButtonFace",
                                           "fg": "white" if active else "black"})

    def confirm(self, reason: str, described: str, title: str = "Allow this action?",
                yes_text: str = "Yes, do it", no_text: str = "No") -> bool:
        """Ask Yes/No and wait for the answer (called from the agent thread)."""
        self._confirm_event.clear()
        self._confirm_result = False
        self.call(self._show_confirm, reason, described, title, yes_text, no_text)
        while not self._confirm_event.wait(0.2):
            if self.stop.pressed:
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
                fn(*args)
        except queue.Empty:
            pass
        self.root.after(50, self._drain)

    def _append(self, kind: str, text: str):
        prefix = {"you": "You: ", "agent": "", "action": "-> ", "error": "! ", "info": "- "}.get(kind, "")
        self.log.config(state="normal")
        self.log.insert("end", prefix + text + "\n", kind)
        self.log.config(state="disabled")
        self.log.see("end")

    def _show_confirm(self, reason: str, described: str, title: str, yes_text: str, no_text: str):
        self.confirm_title.config(text=title)
        self.yes_button.config(text=yes_text)
        self.no_button.config(text=no_text)
        self.confirm_text.config(text=f"{reason}\n\n{described}" if described else reason)
        self.confirm_frame.pack(fill="x", padx=8, pady=4, before=self.input_row)
        self._show_window(focus=True)
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
            if not self.confirm_frame.winfo_ismapped():
                self.entry.focus_set()
        elif previous:
            _set_foreground(previous)  # show the popup but leave the keyboard with the app you were using

    def _send(self):
        text = self.entry.get().strip()
        if text:
            self.entry.delete(0, "end")
            self.selection_frame.pack_forget()
            self.on_send(text)

    def _place_bottom_right(self):
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = screen_w - WIDTH - 16
        y = screen_h - HEIGHT - 72  # leave room for the taskbar
        self.root.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")


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
                 brains, get_main, set_main, get_backup, set_backup, cost_text):
        import pystray
        self.normal_image = _icon_image(COLORS["accent"])
        self.listening_image = _icon_image("#c62828")
        self.busy_image = _icon_image("#e0a100")

        def choice(label, name, get, set_):
            return pystray.MenuItem(label, lambda: set_(name), checked=lambda item: get() == name, radio=True)

        main_items = [choice(label, name, get_main, set_main) for name, label in brains]
        backup_items = [choice("None", "", get_backup, set_backup)] + [
            choice(label, name, get_backup, set_backup) for name, label in brains]

        menu = pystray.Menu(
            pystray.MenuItem("Open", lambda: on_open(), default=True),
            pystray.MenuItem("New conversation", lambda: on_new_conversation()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Main AI", pystray.Menu(*main_items)),
            pystray.MenuItem("Backup AI", pystray.Menu(*backup_items)),
            pystray.MenuItem(lambda item: cost_text(), lambda: None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Edit settings", lambda: on_settings()),
            pystray.MenuItem("Open memory", lambda: on_memory()),
            pystray.MenuItem("Open action log", lambda: on_log()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda: on_quit()),
        )
        self.icon = pystray.Icon("desktop-agent", self.normal_image, "Desktop Agent", menu)
        self.icon.run_detached()

    def set_state(self, state: str):
        self.icon.icon = {"listening": self.listening_image, "busy": self.busy_image}.get(state, self.normal_image)
        try:
            self.icon.update_menu()  # refresh the cost line and the selected brain
        except Exception:
            pass

    def stop(self):
        self.icon.stop()
