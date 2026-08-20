"""
adb_utils.py
Low-level ADB helpers used by fed_viewer.py.

Requires the Android platform-tools `adb` binary to be on PATH
(or pass its full path via ADB_PATH below).
"""

import subprocess
import threading
import shutil
import io

ADB_PATH = shutil.which("adb") or "adb"

# ---------------------------------------------------------------------------
# Keyevent map: Tkinter keysym -> Android KEYCODE
# https://developer.android.com/reference/android/view/KeyEvent
# ---------------------------------------------------------------------------
KEYEVENT_MAP = {
    "Return":    66,   # KEYCODE_ENTER
    "KP_Enter":  66,
    "BackSpace": 67,   # KEYCODE_DEL
    "Delete":    112,  # KEYCODE_FORWARD_DEL
    "Tab":       61,   # KEYCODE_TAB
    "Escape":    111,  # KEYCODE_ESCAPE
    "Up":        19,   # KEYCODE_DPAD_UP
    "Down":      20,   # KEYCODE_DPAD_DOWN
    "Left":      21,   # KEYCODE_DPAD_LEFT
    "Right":     22,   # KEYCODE_DPAD_RIGHT
    "Home":      3,    # KEYCODE_HOME
    "End":       123,  # KEYCODE_MOVE_END
}


def list_devices():
    """Return a list of connected/authorized device serials."""
    try:
        out = subprocess.run(
            [ADB_PATH, "devices"], capture_output=True, text=True, check=False
        ).stdout
    except FileNotFoundError:
        raise RuntimeError(
            "adb not found. Install Android platform-tools and ensure "
            "'adb' is on your PATH."
        )
    devices = []
    for line in out.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices


def get_screen_size(serial):
    """Return (width, height) of the device's physical screen."""
    out = subprocess.run(
        [ADB_PATH, "-s", serial, "shell", "wm", "size"],
        capture_output=True, text=True, check=False
    ).stdout
    # Typical output: "Physical size: 1080x2400"
    for line in out.splitlines():
        if ":" in line:
            dims = line.split(":")[-1].strip()
            if "x" in dims:
                w, h = dims.split("x")
                return int(w), int(h)
    raise RuntimeError(f"Could not parse screen size from: {out!r}")


def screencap_png(serial):
    """Grab a single PNG frame from the device as raw bytes."""
    result = subprocess.run(
        [ADB_PATH, "-s", serial, "exec-out", "screencap", "-p"],
        capture_output=True, check=False
    )
    return result.stdout


def tap(serial, x, y):
    subprocess.run(
        [ADB_PATH, "-s", serial, "shell", "input", "tap", str(x), str(y)],
        check=False
    )


def swipe(serial, x1, y1, x2, y2, duration_ms=150):
    subprocess.run(
        [ADB_PATH, "-s", serial, "shell", "input", "swipe",
         str(x1), str(y1), str(x2), str(y2), str(duration_ms)],
        check=False
    )


def keyevent(serial, code):
    subprocess.run(
        [ADB_PATH, "-s", serial, "shell", "input", "keyevent", str(code)],
        check=False
    )


def _escape_for_input_text(text):
    """Escape characters that the on-device shell would otherwise misparse."""
    return (
        text.replace("\\", "\\\\")
            .replace(" ", "%s")
            .replace("&", "\\&")
            .replace("(", "\\(")
            .replace(")", "\\)")
            .replace("<", "\\<")
            .replace(">", "\\>")
            .replace(";", "\\;")
            .replace("'", "")   # single quotes aren't reliably escapable, strip
            .replace('"', "")
    )


def input_text(serial, text):
    escaped = _escape_for_input_text(text)
    if not escaped:
        return
    subprocess.run(
        [ADB_PATH, "-s", serial, "shell", "input", "text", escaped],
        check=False
    )


# ---------------------------------------------------------------------------
# Persistent shell — avoids spawning a new adb process per keystroke/tap.
# Optional, higher-throughput alternative to the one-shot calls above.
# ---------------------------------------------------------------------------
class PersistentAdbShell:
    def __init__(self, serial):
        self.serial = serial
        self._lock = threading.Lock()
        self._proc = subprocess.Popen(
            [ADB_PATH, "-s", serial, "shell"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def send(self, command):
        with self._lock:
            if self._proc.poll() is not None:
                return  # shell died; caller can recreate
            try:
                self._proc.stdin.write((command + "\n").encode())
                self._proc.stdin.flush()
            except (BrokenPipeError, OSError):
                pass

    def tap(self, x, y):
        self.send(f"input tap {x} {y}")

    def swipe(self, x1, y1, x2, y2, duration_ms=150):
        self.send(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")

    def keyevent(self, code):
        self.send(f"input keyevent {code}")

    def input_text(self, text):
        escaped = _escape_for_input_text(text)
        if escaped:
            self.send(f"input text {escaped}")

    def close(self):
        with self._lock:
            try:
                self._proc.stdin.close()
            except Exception:
                pass
            self._proc.terminate()
