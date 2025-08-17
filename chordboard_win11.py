# chordboard_win11.py
# Windows 11 + python-keyboard 기반 5버튼 합주 키보드
# - LEFT/RIGHT 손 모드
# - Fn 레이어 (mode 'Fn' 우선 조회)
# - 매핑 명령(cmd:...) 지원
# - 합주 ON일 때만 per-key hook+suppress 적용
# - 합성 이벤트 루프 방지(injecting)
# - 멀티탭(count=1/2/3) 로직 (bits의 1개수와 무관)
# - PyInstaller 친화적: mapping_clean.json 경로에 sys._MEIPASS 사용

import json, os, sys, time, threading
import keyboard

# ── 설정 ───────────────────────────────────────────────────────
BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
MAPPING_PATH = os.path.join(BASE_DIR, "mapping_clean.json")

# 오른손/왼손에 사용할 5개 키 (버튼 1(엄지)→버튼 5(새끼) 순서)
RIGHT_CHORD_KEYS = ['0', '7', '8', '9', '+'] #넘버패드
LEFT_CHORD_KEYS  = ['space', 'f', 'd', 's', 'a']

DEFAULT_HAND = 'RIGHT'                         # 'RIGHT' or 'LEFT'
DEBOUNCE = 0.02                                # 20ms 안정화 대기
TAP_GAP = 0.25                                 # 같은 패턴 멀티탭 인정 간격(초)
# ───────────────────────────────────────────────────────────────

# 매핑 로드
with open(MAPPING_PATH, encoding="utf-8") as f:
    MAP = json.load(f)

# 상태
active = False       # 합주 모드 ON/OFF
lang = "EN"          # "EN" / "KO"
mode = "기본"        # "기본" / "SHIFT" / "SWITCH"
ctrl_mode = False
fn_mode = False

hand = DEFAULT_HAND  # 'RIGHT' / 'LEFT'
CHORD_KEYS = RIGHT_CHORD_KEYS if hand == 'RIGHT' else LEFT_CHORD_KEYS
ALL_KEYS = sorted(set(RIGHT_CHORD_KEYS + LEFT_CHORD_KEYS))

KEY_INDEX = {k: i for i, k in enumerate(CHORD_KEYS)}

bits = [0, 0, 0, 0, 0]
last_change_ts = 0.0
pressing = False           # 현재 하나 이상 누름?

# 최근 전송 디버깅용
last_bits = [0,0,0,0,0]
last_cnt = 0              # 멀티탭 카운트(1/2/3)
last_value = None
last_ts = 0.0

# 훅 핸들
HOOK_PRESS = {}
HOOK_RELEASE = {}

# 합성 이벤트 보호
injecting = 0

# 멀티탭 상태
pending_chord_seen = False   # 이번 프레스에서 안정화된 비트패턴을 캡쳐했는가
pending_bits = [0,0,0,0,0]   # 이번 프레스에서 캡쳐된 비트패턴
series_bits = None           # 멀티탭 시리즈의 기준 비트패턴
tap_count = 0                # 누적 탭 수(1/2/3)
series_deadline = 0.0        # 이 시각까지 다음 탭이 없으면 확정 발사

# ── 유틸 ───────────────────────────────────────────────────────
WORDS_TO_CHARS = {"backslash": "\\"}

def normalize_value(v: str) -> str:
    nv = v
    if isinstance(nv, str) and nv.lower().startswith("window+"):
        nv = "windows+" + nv.split("+", 1)[1]
    if isinstance(nv, str) and nv.lower() in ("window+tap", "windows+tap"):
        nv = "windows+tab"
    nv = (nv
          .replace("Arrow Left", "left")
          .replace("Arrow Right", "right")
          .replace("Arrow Up", "up")
          .replace("Arrow Down", "down"))
    return nv

def emit(bits_list, count_int):
    global last_bits, last_cnt, last_value, last_ts
    bstr = "".join(str(b) for b in bits_list)
    cnt_key = str(max(1, min(3, count_int)))  # 1..3

    for mode_to_use in (('Fn' if fn_mode else None), mode):
        if mode_to_use is None:
            continue
        modesect = MAP.get(lang, {}).get(mode_to_use, {})
        val = modesect.get(cnt_key, {}).get(bstr)
        if val is not None:
            print(f"[SEND] ({lang},{mode_to_use}) hand={hand} bits={bits_list} cnt={cnt_key} → {val}")
            last_bits = bits_list[:]; last_cnt = int(cnt_key); last_value = val; last_ts = time.time()
            send_value(val)
            return
        else:
            for other_cnt, group in modesect.items():
                if other_cnt != cnt_key and bstr in group:
                    print(f"[HINT] same bits exist under count={other_cnt} (expected cnt={cnt_key})")
                    break
    print(f"[MISS] ({lang},{mode}) hand={hand} bits={bits_list} cnt={cnt_key} → 매핑 없음")
    last_bits = bits_list[:]; last_cnt = int(cnt_key); last_value = None; last_ts = time.time()

def run_command(cmd: str):
    global mode, lang, ctrl_mode, fn_mode, active
    name, _, arg = (cmd or "").partition('=')
    name = name.strip(); arg = arg.strip()

    if name == 'toggle_active':
        set_active(not active)
    elif name == 'toggle_lang':
        toggle_lang()
    elif name == 'toggle_hand':
        toggle_hand()
    elif name == 'set_active':
        val = arg.lower() in ('1','true','on','yes')
        set_active(val)
    elif name == 'set_hand':
        set_hand(arg.upper() if arg else arg)
    elif name == 'set_lang':
        if arg in ('EN','KO'):
            lang = arg; print(f"[STATE] lang = {lang}")
    elif name == 'set_mode':
        if arg in ('기본','SHIFT','SWITCH','Fn'):
            mode = arg; print(f"[STATE] mode = {mode}")
    elif name == 'toggle_ctrl':
        ctrl_mode = not ctrl_mode; print(f"[STATE] ctrl_mode = {ctrl_mode}")
    elif name == 'toggle_fn':
        fn_mode = not fn_mode; print(f"[STATE] fn_mode = {fn_mode}")
    elif name in ('exit','quit'):
        try: set_active(False)
        except Exception: pass
        os._exit(0)
    else:
        print(f"[CMD] Unknown command: {cmd!r}")

def send_value(val: str):
    global mode, ctrl_mode, fn_mode, injecting

    if val in ("shift", "switch", "ctrl", "Fn", "fn"):
        if val == "shift":
            mode = "SHIFT" if mode == "기본" else "기본"; print(f"[STATE] mode = {mode}")
        elif val == "switch":
            mode = "SWITCH" if mode != "SWITCH" else "기본"; print(f"[STATE] mode = {mode}")
        elif val == "ctrl":
            ctrl_mode = not ctrl_mode; print(f"[STATE] ctrl_mode = {ctrl_mode}")
        else:  # Fn
            fn_mode = not fn_mode; print(f"[STATE] fn_mode = {fn_mode}")
        return

    if isinstance(val, str) and val.startswith('cmd:'):
        run_command(val[4:]); return

    raw = WORDS_TO_CHARS.get(val, val)
    injecting += 1
    try:
        if isinstance(raw, str) and len(raw) == 1:
            if ctrl_mode:
                keyboard.send(f"ctrl+{raw}"); ctrl_mode = False
            else:
                keyboard.write(raw)
            return
        norm = normalize_value(raw)
        if ctrl_mode and isinstance(norm, str) and "+" not in norm and len(norm) == 1:
            keyboard.send(f"ctrl+{norm}"); ctrl_mode = False
        else:
            keyboard.send(norm)
    finally:
        injecting = max(0, injecting-1)

def _remove_hooks():
    global HOOK_PRESS, HOOK_RELEASE
    for d in (HOOK_PRESS, HOOK_RELEASE):
        for k, h in list(d.items()):
            try: keyboard.unhook(h)
            except Exception: pass
        d.clear()

def _install_hooks(suppress=True):
    global HOOK_PRESS, HOOK_RELEASE
    _remove_hooks()
    HOOK_PRESS, HOOK_RELEASE = {}, {}
    for k in CHORD_KEYS:
        try:
            HOOK_PRESS[k] = keyboard.on_press_key(k, on_press, suppress=suppress)
            HOOK_RELEASE[k] = keyboard.on_release_key(k, on_release, suppress=suppress)
        except Exception as e:
            print(f"[HOOK] install failed for {k}: {e}")

def set_active(on: bool):
    global active, bits, pressing, pending_chord_seen, tap_count, series_bits, series_deadline
    active = on
    if on:
        _install_hooks(suppress=True)
    else:
        _remove_hooks()
        bits = [0,0,0,0,0]; pressing = False
        pending_chord_seen = False; tap_count = 0
        series_bits = None; series_deadline = 0.0
    print(f"[MODE] Chord mode {'ON' if on else 'OFF'} (hand={hand})")

def toggle_active(): set_active(not active)

def set_hand(new_hand: str):
    global hand, CHORD_KEYS, KEY_INDEX, bits, pressing, pending_chord_seen, tap_count, series_bits, series_deadline
    if new_hand not in ('LEFT','RIGHT'): return
    if active: _remove_hooks()
    hand = new_hand
    CHORD_KEYS = RIGHT_CHORD_KEYS if hand == 'RIGHT' else LEFT_CHORD_KEYS
    KEY_INDEX = {k: i for i, k in enumerate(CHORD_KEYS)}
    bits = [0,0,0,0,0]; pressing = False
    pending_chord_seen = False; tap_count = 0; series_bits = None; series_deadline = 0.0
    if active: _install_hooks(suppress=True)
    print(f"[STATE] hand = {hand}  (keys={CHORD_KEYS})")

def toggle_hand(): set_hand('LEFT' if hand == 'RIGHT' else 'RIGHT')

def toggle_lang():
    global lang
    lang = "KO" if lang == "EN" else "EN"
    print(f"[STATE] lang = {lang}")

def on_press(e):
    global injecting, last_change_ts, pressing, pending_chord_seen
    if injecting > 0 or not active: return
    name = e.name
    if name in KEY_INDEX:
        i = KEY_INDEX[name]
        if bits[i] == 0:
            bits[i] = 1
            last_change_ts = time.time()
            pressing = True
            try: keyboard.suppress_event()
            except Exception: pass

def on_release(e):
    global injecting, last_change_ts, pressing, pending_chord_seen, pending_bits, series_bits, tap_count, series_deadline
    if injecting > 0 or not active: return
    name = e.name
    if name in KEY_INDEX:
        i = KEY_INDEX[name]
        if bits[i] == 1:
            bits[i] = 0
            last_change_ts = time.time()
            if sum(bits) == 0:
                # 전체 릴리즈: 이번 프레스의 안정 비트가 있다면 탭 누적
                if pending_chord_seen:
                    if series_bits is None:
                        series_bits = pending_bits[:]
                    else:
                        if "".join(str(b) for b in pending_bits) != "".join(str(b) for b in series_bits):
                            emit(series_bits, tap_count)
                            tap_count = 0
                            series_bits = pending_bits[:]
                    tap_count = min(3, tap_count + 1)
                    series_deadline = time.time() + TAP_GAP
                    pending_chord_seen = False
                pressing = False
            try: keyboard.suppress_event()
            except Exception: pass

def worker():
    global pending_chord_seen, pending_bits, series_deadline, last_bits, last_cnt, last_value, last_ts, series_bits, tap_count
    while True:
        now = time.time()
        if active:
            if pressing and not pending_chord_seen and (now - last_change_ts) >= DEBOUNCE:
                pending_bits = bits[:]
                pending_chord_seen = True
            if (not pressing) and series_bits is not None and tap_count>0 and series_deadline>0 and now >= series_deadline:
                emit(series_bits, tap_count)
                series_bits = None
                series_deadline = 0.0
                tap_count = 0
        time.sleep(0.003)

def main():
    keyboard.add_hotkey("ctrl+alt+m", lambda: set_active(not active))
    keyboard.add_hotkey("ctrl+alt+l", toggle_lang)
    keyboard.add_hotkey("ctrl+alt+h", toggle_hand)
    keyboard.add_hotkey("ctrl+alt+left", lambda: set_hand('LEFT'))
    keyboard.add_hotkey("ctrl+alt+right", lambda: set_hand('RIGHT'))
    keyboard.add_hotkey("ctrl+alt+q", lambda: os._exit(0))

    threading.Thread(target=worker, daemon=True).start()

    print("Ready.")
    print(f" - Chord keys (RIGHT): {RIGHT_CHORD_KEYS}")
    print(f" - Chord keys (LEFT) : {LEFT_CHORD_KEYS}")
    print(f" - Current hand      : {hand}")
    print(" - Toggle chord mode : Ctrl+Alt+M")
    print(" - Toggle language   : Ctrl+Alt+L")
    print(" - Toggle hand       : Ctrl+Alt+H (or Ctrl+Alt+←/→)")
    print(" - Quit              : Ctrl+Alt+Q")
    keyboard.wait()

if __name__ == "__main__":
    main()
