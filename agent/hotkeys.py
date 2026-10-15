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
        self.talk_keys = [key.strip() for key in self.talk_hotkey.split("+") if key.strip()]
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
        # The keyboard hook must return quickly (Windows drops slow hooks), so the work runs in a thread.
        threading.Thread(target=self._record_while_held, daemon=True, name="push-to-talk").start()

    def _record_while_held(self):
        """Recording lasts while ALL keys of the hotkey are held; letting go of any one of them sends it."""
        try:
            self.on_talk_start()
            started = time.time()
            while self._all_held() and time.time() - started < self.max_seconds:
                time.sleep(0.03)
            self.on_talk_end()
        finally:
            self._talking = False

    def _all_held(self) -> bool:
        try:
            return all(self._keyboard.is_pressed(key) for key in self.talk_keys)
        except Exception:  # unknown key name: fall back to the last key only
            return self._keyboard.is_pressed(self.talk_keys[-1])

    def remove(self):
        self._keyboard.unhook_all()
