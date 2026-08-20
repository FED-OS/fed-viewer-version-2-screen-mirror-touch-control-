# Fed Viewer — ADB USB Screen Mirror & Control

Full control of your Android phone from a PC over a USB cable. No app
required on the phone. Mouse clicks become taps, drags become swipes,
and your PC keyboard types directly into the phone's active text field.

## 1. One-time setup

1. **Install Android platform-tools** (gives you `adb`):
   https://developer.android.com/tools/releases/platform-tools
   Unzip it somewhere, and add that folder to your system PATH
   (or just drop `adb.exe`, `AdbWinApi.dll`, `AdbWinUsbApi.dll` next to
   `fed_viewer.py` / `fed_viewer.exe`).

2. **On the phone:** Settings → About phone → tap "Build number" 7 times
   to unlock Developer Options → Settings → Developer Options → enable
   **USB debugging**.

3. **Plug in via USB.** A prompt appears on the phone asking to trust
   this computer — check "Always allow" and tap Allow.

4. **Install Python deps** (skip if using the prebuilt `.exe`):
   ```
   pip install -r requirements.txt
   ```

## 2. Run it

```
python fed_viewer.py
```

- Pick your device from the dropdown, click **Connect**.
- The mirror window appears. Click it once to give it keyboard focus.
- Click/drag on the mirror to tap/swipe on the phone.
- Type on your PC keyboard — text goes straight into whatever field is
  focused on the phone. Enter, Backspace, Delete, Tab, Escape, and the
  arrow keys are also mapped.

## 3. Build a standalone .exe

```
build.bat
```

Produces `dist\fed_viewer.exe`. Ship `adb.exe` (and its two DLLs) in the
same folder if the target machine doesn't already have platform-tools
on its PATH.

## Files

| File | Purpose |
|---|---|
| `fed_viewer.py` | Tkinter GUI: mirror display, mouse/keyboard handling |
| `adb_utils.py` | All ADB calls: device listing, screencap, tap/swipe, key/text injection, persistent shell |
| `requirements.txt` | Python dependencies |
| `build.bat` | PyInstaller packaging script for a single-file .exe |

## Notes / known limits

- **Refresh rate** is polling-based (~6-7 fps by default, set via
  `REFRESH_INTERVAL_SEC` in `fed_viewer.py`). This keeps CPU/USB load
  low and works reliably over a USB cable; it's not meant to be
  video-smooth. For a much higher frame rate you'd want to move to an
  `adb shell screenrecord` pipe or a `scrcpy`-style H.264 stream —
  ask if you want that upgraded later.
- **Text injection** covers standard printable ASCII reliably. Emoji
  and some non-Latin scripts can fail to escape cleanly through
  `input text`; if you need those, the next step is swapping in a
  broadcast-based IME (e.g. an "ADB Keyboard" style app) which accepts
  raw text without shell escaping.
- Only one device is controlled at a time; the dropdown just lets you
  pick which one if several are plugged in.
