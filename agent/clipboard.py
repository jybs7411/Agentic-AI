"""Clipboard helpers that put back what you had copied - text, images and copied files - after the
agent used the clipboard to paste or copy something."""

import struct
import time

CF_UNICODETEXT, CF_DIB, CF_HDROP = 13, 8, 15
_KEPT_FORMATS = (CF_UNICODETEXT, CF_DIB, CF_HDROP)


def _open():
    import win32clipboard
    for _ in range(20):  # another app may be holding the clipboard for a moment
        try:
            win32clipboard.OpenClipboard()
            return win32clipboard
        except Exception:
            time.sleep(0.05)
    raise RuntimeError("The clipboard is busy.")


def save():
    """Remember the current clipboard (text, image, files). Returns None if it can't be read."""
    try:
        clip = _open()
    except ImportError:
        import pyperclip
        return {"text": pyperclip.paste()}
    except Exception:
        return None
    try:
        saved = {}
        for fmt in _KEPT_FORMATS:
            if clip.IsClipboardFormatAvailable(fmt):
                try:
                    saved[fmt] = clip.GetClipboardData(fmt)
                except Exception:
                    pass
        return saved
    finally:
        clip.CloseClipboard()


def restore(saved):
    if saved is None:
        return
    try:
        clip = _open()
    except ImportError:
        import pyperclip
        pyperclip.copy(saved.get("text", ""))
        return
    except Exception:
        return
    try:
        clip.EmptyClipboard()
        for fmt, value in saved.items():
            if fmt == CF_HDROP:  # a list of copied files must be rebuilt as a DROPFILES structure
                header = struct.pack("<IiiII", 20, 0, 0, 0, 1)
                value = header + ("\0".join(value) + "\0\0").encode("utf-16-le")
            clip.SetClipboardData(fmt, value)
    except Exception:
        pass
    finally:
        clip.CloseClipboard()


def set_text(text: str):
    try:
        clip = _open()
    except ImportError:
        import pyperclip
        pyperclip.copy(text)
        return
    try:
        clip.EmptyClipboard()
        clip.SetClipboardData(CF_UNICODETEXT, text)
    finally:
        clip.CloseClipboard()


def get_text() -> str:
    try:
        clip = _open()
    except ImportError:
        import pyperclip
        return pyperclip.paste()
    except Exception:
        return ""
    try:
        if clip.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return clip.GetClipboardData(CF_UNICODETEXT) or ""
        return ""
    finally:
        clip.CloseClipboard()
