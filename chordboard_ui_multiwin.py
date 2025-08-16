# chordboard_ui_multiwin.py
# 3-Window Tkinter UI for ChordBoard (Windows)
#  • Window 1: Control (mode, toggles, language/hand, active)
#  • Window 2: Current Bits (LED + last info)
#  • Window 3: Binding & Layouts & Built-in Hotkeys
# PyInstaller-friendly: tries normal import first, falls back to file, supports sys._MEIPASS.

import os, sys, threading, tkinter as tk
from tkinter import ttk, messagebox

try:
    import keyboard
except Exception:
    keyboard = None

def _load_backend_fallback():
    import importlib.util
    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    path = os.path.join(base_dir, "chordboard_win11.py")
    if not os.path.exists(path):
        raise FileNotFoundError(f"chordboard_win11.py not found in {base_dir}")
    spec = importlib.util.spec_from_file_location("chordboard_win11", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

# --- Prefer static import so PyInstaller bundles it ---
try:
    import chordboard_win11 as backend  # bundled as module
except Exception:
    backend = _load_backend_fallback()  # dev/fallback

LED_ON = "#22c55e"
LED_OFF = "#334155"
LED_BG = "#0f172a"

class MultiWinApp:
    def __init__(self):
        # Hidden root
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("ChordBoard Controller")
        self.root.iconbitmap('ChordBoard.ico')

        # Start backend in daemon thread
        self.backend_thread = threading.Thread(target=backend.main, daemon=True)
        self.backend_thread.start()

        # Learn mode state
        self.learn_mode = False
        self.learn_keys = []
        self.learn_hook = None

        # ---------- Window 1: Control ----------
        self.win1 = tk.Toplevel(self.root)
        self.win1.title("ChordBoard • Control")
        self.win1.geometry("740x300")
        self.win1.iconbitmap('ChordBoard.ico')
        self._apply_bg(self.win1)

        top = ttk.Frame(self.win1, padding=10)
        top.pack(fill="x")
        self.state_lab = ttk.Label(top, text="state: -")
        self.state_lab.grid(row=0, column=0, sticky="w")
        ttk.Button(top, text="Toggle Active (Ctrl+Alt+M)", command=self.toggle_active).grid(row=0, column=1, padx=6)
        ttk.Button(top, text="Quit", command=self.do_quit).grid(row=0, column=2, padx=6)

        row1 = ttk.Frame(self.win1, padding=10)
        row1.pack(fill="x")
        ttk.Button(row1, text="EN↔KO (Ctrl+Alt+L)", command=lambda: backend.toggle_lang()).grid(row=0, column=0, padx=6, sticky="w")
        ttk.Button(row1, text="Hand LEFT/RIGHT (Ctrl+Alt+H)", command=lambda: backend.toggle_hand()).grid(row=0, column=1, padx=6, sticky="w")
        ttk.Button(row1, text="Hand = LEFT (Ctrl+Alt+←)", command=lambda: backend.set_hand('LEFT')).grid(row=0, column=2, padx=6, sticky="w")
        ttk.Button(row1, text="Hand = RIGHT (Ctrl+Alt+→)", command=lambda: backend.set_hand('RIGHT')).grid(row=0, column=3, padx=6, sticky="w")

        row2 = ttk.LabelFrame(self.win1, text="Mode", padding=10)
        row2.pack(fill="x", padx=10, pady=6)
        self.mode_var = tk.StringVar(value="기본")
        for i, m in enumerate(["기본", "SHIFT", "SWITCH", "Fn"]):
            ttk.Radiobutton(row2, text=m, value=m, variable=self.mode_var, command=self.apply_mode).grid(row=0, column=i, padx=8, pady=4, sticky="w")

        row3 = ttk.LabelFrame(self.win1, text="Toggles", padding=10)
        row3.pack(fill="x", padx=10, pady=6)
        ttk.Button(row3, text="CTRL mode", command=lambda: backend.run_command("toggle_ctrl")).grid(row=0, column=0, padx=6, pady=4, sticky="w")
        ttk.Button(row3, text="Fn layer", command=lambda: backend.run_command("toggle_fn")).grid(row=0, column=1, padx=6, pady=4, sticky="w")

        # ---------- Window 2: Current Bits ----------
        self.win2 = tk.Toplevel(self.root)
        self.win2.title("ChordBoard • Current Bits")
        self.win2.geometry("360x170")
        self.win2.iconbitmap("ChordBoard.ico")
        self._apply_bg(self.win2)

        led_frame = ttk.LabelFrame(self.win2, text="Current Bits", padding=10)
        led_frame.pack(fill="x", padx=10, pady=6)
        self.led_canvas = tk.Canvas(led_frame, width=5*60, height=60, bg=LED_BG, highlightthickness=0)
        self.led_canvas.pack(fill="x")
        self.led_ids = []
        for i in range(5):
            x0 = 18 + i*60
            y0 = 10
            x1 = x0 + 38
            y1 = y0 + 30
            oid = self.led_canvas.create_oval(x0, y0, x1, y1, fill=LED_OFF, outline="#1f2937", width=2)
            self.led_ids.append(oid)
        for i in range(5):
            x0 = 18 + i*60 + 19
            self.led_canvas.create_text(x0, 54, text=f"b{i+1}", fill="#cbd5e1", font=("Segoe UI", 9))

        self.last_lab = ttk.Label(led_frame, text="Last: -")
        self.last_lab.pack(anchor="w", pady=(6,0))

        # ---------- Window 3: Bindings/Layouts/Hotkeys ----------
        self.win3 = tk.Toplevel(self.root)
        self.win3.title("ChordBoard • Bindings & Layouts")
        self.win3.geometry("680x490")
        self.win3.iconbitmap("ChordBoard.ico")
        self._apply_bg(self.win3)

        learn_box = ttk.LabelFrame(self.win3, text="5-Key Binding (Learn Mode)", padding=10)
        learn_box.pack(fill="x", padx=10, pady=6)
        self.learn_lab = ttk.Label(learn_box, text="현재 손(Hand)의 5개 키를 순서대로 눌러서 등록합니다. (학습 중 ESC 취소)")
        self.learn_lab.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0,6))
        ttk.Button(learn_box, text="Start Learn (Current Hand)", command=self.start_learn).grid(row=1, column=0, sticky="w", padx=6)
        ttk.Button(learn_box, text="Cancel", command=self.cancel_learn).grid(row=1, column=1, sticky="w", padx=6)
        self.learn_progress = ttk.Label(learn_box, text="Not learning")
        self.learn_progress.grid(row=1, column=2, sticky="e")

        layout = ttk.LabelFrame(self.win3, text="Current Hand Layouts", padding=10)
        layout.pack(fill="x", padx=10, pady=6)
        self.layout_lab = ttk.Label(layout, text="-")
        self.layout_lab.pack(anchor="w")

        hk = ttk.LabelFrame(self.win3, text="Built-in Hotkeys", padding=10)
        hk.pack(fill="both", expand=True, padx=10, pady=6)
        self.hk_text = tk.Text(hk, height=10, wrap="word")
        self.hk_text.pack(fill="both", expand=True)
        self.hk_text.insert("1.0",
            "• Ctrl+Alt+M  : Toggle chord mode\n"
            "• Ctrl+Alt+L  : Toggle language (EN↔KO)\n"
            "• Ctrl+Alt+H  : Toggle hand (LEFT↔RIGHT)\n"
            "• Ctrl+Alt+←  : Hand = LEFT\n"
            "• Ctrl+Alt+→  : Hand = RIGHT\n"
            "• Ctrl+Alt+Q  : Exit\n"
            "\n"
            "Mapping commands (use in mapping value):\n"
            "• cmd:toggle_active, cmd:toggle_lang, cmd:toggle_hand\n"
            "• cmd:set_mode=기본/SHIFT/SWITCH/Fn\n"
            "• cmd:set_lang=EN/KO, cmd:set_active=on/off, cmd:set_hand=LEFT/RIGHT\n"
            "• cmd:toggle_ctrl, cmd:toggle_fn, cmd:exit\n"
        )
        self.hk_text.configure(state="disabled")

        # start refresh loop
        self.root.after(120, self.refresh_all)

    def _apply_bg(self, win):
        try:
            win.configure(bg="#0f172a")
        except Exception:
            pass

    # -------- Learn mode --------
    def start_learn(self):
        if keyboard is None:
            messagebox.showwarning("Keyboard module", "python-keyboard 모듈을 사용할 수 없습니다.\n관리자 권한 또는 모듈 설치를 확인하세요.")
            return
        if self.learn_mode:
            return
        self.learn_mode = True
        self.learn_keys = []
        self.learn_progress.configure(text="Learning: 0/5  (ESC to cancel)")
        try:
            if getattr(backend, "active", False):
                backend.set_active(False)
        except Exception:
            pass
        def on_ev(e):
            if e.event_type != "down":
                return
            name = e.name
            if name == "esc":
                self.cancel_learn(); return
            if name not in self.learn_keys:
                self.learn_keys.append(name)
                self.learn_progress.configure(text=f"Learning: {len(self.learn_keys)}/5  -> {self.learn_keys}")
            if len(self.learn_keys) >= 5:
                self.finish_learn()
        self.learn_hook = keyboard.hook(on_ev)

    def cancel_learn(self):
        if not self.learn_mode: return
        self.learn_mode = False
        self.learn_progress.configure(text="Canceled")
        try:
            if self.learn_hook and keyboard: keyboard.unhook(self.learn_hook)
        except Exception: pass
        self.learn_hook = None

    def finish_learn(self):
        try:
            if self.learn_hook and keyboard: keyboard.unhook(self.learn_hook)
        except Exception: pass
        self.learn_hook = None
        self.learn_mode = False
        keys = self.learn_keys[:5]
        self.learn_progress.configure(text=f"Applied: {keys}")
        try:
            hand = getattr(backend, "hand", "RIGHT")
            if hand == "RIGHT":
                backend.RIGHT_CHORD_KEYS = keys
            else:
                backend.LEFT_CHORD_KEYS = keys
            backend.ALL_KEYS = sorted(set(backend.RIGHT_CHORD_KEYS + backend.LEFT_CHORD_KEYS))
            backend.set_hand(hand)
        except Exception as e:
            messagebox.showerror("Apply error", str(e))

    # -------- Control handlers --------
    def toggle_active(self):
        try:
            backend.set_active(not backend.active)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def do_quit(self):
        try: backend.set_active(False)
        except Exception: pass
        self.win1.destroy(); self.win2.destroy(); self.win3.destroy()
        self.root.destroy()

    def apply_mode(self):
        m = self.mode_var.get()
        try:
            if m == "Fn":
                if not getattr(backend, "fn_mode", False):
                    backend.run_command("toggle_fn")
            else:
                if getattr(backend, "fn_mode", False):
                    backend.run_command("toggle_fn")
                backend.run_command(f"set_mode={m}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # -------- Periodic refresh --------
    def refresh_all(self):
        try:
            active = "ON" if getattr(backend, "active", False) else "OFF"
            lang   = getattr(backend, "lang", "-")
            mode   = getattr(backend, "mode", "-")
            hand   = getattr(backend, "hand", "-")
            ctrl   = "ON" if getattr(backend, "ctrl_mode", False) else "OFF"
            fn     = "ON" if getattr(backend, "fn_mode", False) else "OFF"
            mode_display = f"Fn → {mode}" if fn == "ON" else mode
            self.state_lab.configure(text=f"Chord: {active}   |   Lang: {lang}   |   Mode: {mode_display}   |   Hand: {hand}   |   CTRL: {ctrl}  FN: {fn}")
            want = "Fn" if fn == "ON" else mode
            if self.mode_var.get() != want:
                self.mode_var.set(want)

            bits = getattr(backend, "bits", [0,0,0,0,0])
            for i, oid in enumerate(getattr(self, "led_ids", [])):
                val = bits[i] if i < len(bits) else 0
                self.led_canvas.itemconfigure(oid, fill=LED_ON if val else LED_OFF)

            try:
                r = getattr(backend, "RIGHT_CHORD_KEYS", [])
                l = getattr(backend, "LEFT_CHORD_KEYS", [])
                self.layout_lab.configure(text=f"RIGHT: {r}\nLEFT : {l}")
            except Exception:
                pass
            try:
                lb = getattr(backend, 'last_bits', [0,0,0,0,0])
                lc = getattr(backend, 'last_cnt', 0)
                lv = getattr(backend, 'last_value', None)
                lv_disp = lv if lv is not None else '(MISS)'
                self.last_lab.configure(text=f"Last: {''.join(str(x) for x in lb)}  cnt={lc}  →  {lv_disp}")
            except Exception:
                pass
        except Exception:
            pass
        self.root.after(120, self.refresh_all)

    def run(self):
        # Basic tiling
        try:
            self.win1.update_idletasks(); self.win2.update_idletasks(); self.win3.update_idletasks()
            x0, y0 = 40, 40
            self.win1.geometry(f"+{x0}+{y0}")
            self.win2.geometry(f"+{x0}+{y0 + self.win1.winfo_height() + 20}")
            self.win3.geometry(f"+{x0 + self.win1.winfo_width() + 20}+{y0}")
        except Exception:
            pass
        self.root.mainloop()

if __name__ == "__main__":
    MultiWinApp().run()
