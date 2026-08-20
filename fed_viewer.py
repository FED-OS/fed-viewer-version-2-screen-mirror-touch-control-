"""
fed_viewer.py
Standalone USB screen mirror + remote control for Android devices via ADB.

Features
--------
- Live screen mirror (polled screenshots over adb exec-out screencap)
- Mouse click -> tap, mouse drag -> swipe (coordinates auto-scaled)
- PC keyboard -> injected directly into the device's focused text field
  (printable characters via `input text`, special keys via `input keyevent`)
- Runs off a persistent adb shell for low input latency

Requirements: Python 3.9+, Pillow, and `adb` (Android platform-tools) on PATH.
"""

import io
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from PIL import Image, ImageTk

import adb_utils


REFRESH_INTERVAL_SEC = 0.15   # ~6-7 fps; lower = smoother but more USB/CPU load
MAX_DISPLAY_WIDTH = 420        # window sized to fit alongside your other work


class FedViewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Fed Viewer — ADB Screen Control")
        self.root.resizable(False, False)

        self.serial = None
        self.shell = None
        self.device_w = None
        self.device_h = None
        self.display_w = None
        self.display_h = None
        self.scale = 1.0

        self.running = False
        self.photo_image = None  # keep a reference or Tk garbage-collects it
        self.drag_start = None

        self._build_device_picker()

    # ------------------------------------------------------------------
    # Device selection
    # ------------------------------------------------------------------
    def _build_device_picker(self):
        frame = ttk.Frame(self.root, padding=16)
        frame.pack()

        ttk.Label(frame, text="Connected devices:").pack(anchor="w")

        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(
            frame, textvariable=self.device_var, state="readonly", width=40
        )
        self.device_combo.pack(pady=(4, 8))

        btn_row = ttk.Frame(frame)
        btn_row.pack()
        ttk.Button(btn_row, text="Refresh", command=self._refresh_devices).pack(
            side="left", padx=4
        )
        ttk.Button(btn_row, text="Connect", command=self._connect).pack(
            side="left", padx=4
        )

        self._refresh_devices()

    def _refresh_devices(self):
        try:
            devices = adb_utils.list_devices()
        except RuntimeError as e:
            messagebox.showerror("adb not found", str(e))
            return
        self.device_combo["values"] = devices
        if devices:
            self.device_combo.current(0)
        else:
            messagebox.showwarning(
                "No devices",
                "No authorized ADB devices found.\n\n"
                "Check: USB debugging enabled, cable connected, "
                "and you accepted the RSA prompt on the phone.",
            )

    def _connect(self):
        serial = self.device_var.get()
        if not serial:
            messagebox.showwarning("Pick a device", "Select a device first.")
            return
        self.serial = serial
        try:
            self.device_w, self.device_h = adb_utils.get_screen_size(serial)
        except Exception as e:
            messagebox.showerror("Could not read screen size", str(e))
            return

        self.shell = adb_utils.PersistentAdbShell(serial)

        # tear down the picker, build the viewer
        for w in self.root.winfo_children():
            w.destroy()
        self._build_viewer()

    # ------------------------------------------------------------------
    # Viewer / control surface
    # ------------------------------------------------------------------
    def _build_viewer(self):
        self.scale = MAX_DISPLAY_WIDTH / self.device_w
        self.display_w = MAX_DISPLAY_WIDTH
        self.display_h = int(self.device_h * self.scale)

        self.canvas = tk.Canvas(
            self.root, width=self.display_w, height=self.display_h,
            bg="black", highlightthickness=0
        )
        self.canvas.pack()

        status = ttk.Label(
            self.root,
            text=f"{self.serial}  •  {self.device_w}x{self.device_h}  •  "
                 f"keyboard is live — click the mirror, then type",
            padding=4,
        )
        status.pack(fill="x")

        # Mouse -> tap / swipe
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        # Keyboard -> injected text / keyevents
        self.canvas.bind("<Key>", self._on_key)
        self.canvas.focus_set()
        self.canvas.bind("<Button-1>", lambda e: self.canvas.focus_set(), add="+")

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.running = True
        threading.Thread(target=self._mirror_loop, daemon=True).start()

    # ------------------------------------------------------------------
    # Screen mirror loop (background thread; UI updates marshalled via .after)
    # ------------------------------------------------------------------
    def _mirror_loop(self):
        while self.running:
            start = time.time()
            try:
                png_bytes = adb_utils.screencap_png(self.serial)
                if png_bytes:
                    img = Image.open(io.BytesIO(png_bytes))
                    img = img.resize((self.display_w, self.display_h), Image.BILINEAR)
                    self.root.after(0, self._update_frame, img)
            except Exception:
                pass  # transient USB hiccup; just retry next tick
            elapsed = time.time() - start
            time.sleep(max(0, REFRESH_INTERVAL_SEC - elapsed))

    def _update_frame(self, img):
        self.photo_image = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo_image)

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------
    def _to_device_coords(self, x, y):
        return int(x / self.scale), int(y / self.scale)

    def _on_press(self, event):
        self.drag_start = (event.x, event.y, time.time())

    def _on_release(self, event):
        if self.drag_start is None:
            return
        x1, y1, t0 = self.drag_start
        x2, y2 = event.x, event.y
        self.drag_start = None

        dx1, dy1 = self._to_device_coords(x1, y1)
        dx2, dy2 = self._to_device_coords(x2, y2)

        moved = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        if moved < 8:
            self.shell.tap(dx1, dy1)
        else:
            duration_ms = max(80, int((time.time() - t0) * 1000))
            self.shell.swipe(dx1, dy1, dx2, dy2, duration_ms)

    def _on_key(self, event):
        keysym = event.keysym
        if keysym in adb_utils.KEYEVENT_MAP:
            self.shell.keyevent(adb_utils.KEYEVENT_MAP[keysym])
        elif len(event.char) == 1 and event.char.isprintable():
            self.shell.input_text(event.char)

    # ------------------------------------------------------------------
    def _on_close(self):
        self.running = False
        if self.shell:
            self.shell.close()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = FedViewerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
