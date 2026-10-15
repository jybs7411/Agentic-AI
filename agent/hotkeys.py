"""Global keyboard shortcuts that work while any app is in front."""

import threading
import time


class Hotkeys:
    def __init__(self, settings: dict, on_talk_start, on_talk_end, on_open_popup, on_stop, on_selection=None):
        import keyboard
        self._keyboard = keyboard
        self.on_talk_start = on_talk_start
        self.on_talk_end = on_talk_end
        self.talk_hotkey = settings["push_to_talk_hotkey"]
        self.max_seconds = settings["max_recording_seconds"]
        self._talking = False

        keyboard.add_hotkey(self.talk_hotkey, self._talk_pressed)
        keyboard.add_hotkey(settings["open_popup_hotkey"], on_open_popup)
        keyboard.add_hotkey(settings["stop_key"], on_stop)
        if on_selection and settings.get("selection_hotkey"):
            keyboard.add_hotkey(settings["selection_hotkey"], on_selection)

    def _talk_pressed(self):
        if self._talking:  # holding the keys repeats the event; ignore repeats
            return
        self._talking = True
        self.on_talk_start()
        threading.Thread(target=self._wait_for_release, daemon=True).start()

    def _wait_for_release(self):
        """Recording lasts while the last key of the hotkey (e.g. Space) is held down."""
        last_key = self.talk_hotkey.split("+")[-1].strip()
        started = time.time()
        while self._keyboard.is_pressed(last_key) and time.time() - started < self.max_seconds:
            time.sleep(0.03)
        self._talking = False
        self.on_talk_end()

    def remove(self):
        self._keyboard.unhook_all()
