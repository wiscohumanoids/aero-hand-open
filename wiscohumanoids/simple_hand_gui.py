import tkinter as tk
import sys
import os
import time
import threading
import random

# Add the SDK source to the path so we can import aero_open_sdk
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk", "src"))

from aero_open_sdk.aero_hand import AeroHand
from hand_mirror import HandMirror

# --- CONFIG ---
PORT = "COM5"   # CHANGE THIS to your port (e.g. COM3, COM12, etc.)

# --- COLORS ---
BG = "#1a1a2e"
CARD_BG = "#16213e"
ACCENT = "#0f3460"
ACCENT_HOVER = "#1a4a8a"
TEXT = "#e0e0e0"
TITLE_COLOR = "#e94560"
STATUS_COLOR = "#a0a0b8"
HOMING_BG = "#5c1a1a"
HOMING_HOVER = "#7a2a2a"
SEQ_BG = "#1a3a1a"
SEQ_HOVER = "#2a5a2a"

# --- POSES (7 joint compact representation) ---
# [thumb_abd, thumb_flex, thumb_tendon, index, middle, ring, pinky]
OPEN_POSE = [0, 0, 0, 0, 0, 0, 0]
FIST_POSE = [100, 55, 30, 60, 60, 60, 60]
PEACE_POSE = [90, 45, 60, 0, 0, 90, 90]
ROCK_POSE = [0, 0, 0, 0, 90, 90, 0]
PINCH_POSE = [75, 25, 30, 50, 0, 0, 0]

# Count poses: fist, then extend one more finger each press
COUNT_POSES = [
    FIST_POSE,                                  # 0 - fist
    [100, 55, 30, 0, 60, 60, 60],              # 1 - index out
    [100, 55, 30, 0, 0, 60, 60],               # 2 - index + middle out
    [100, 55, 30, 0, 0, 0, 60],                # 3 - index + middle + ring out
    [100, 55, 30, 0, 0, 0, 0],                 # 4 - all fingers out, thumb still in
    OPEN_POSE,                                  # 5 - everything open including thumb
]

# Beckoning: index finger extended, others closed
BECKON_OUT = [90, 45, 60, 0, 90, 90, 90]
BECKON_IN = [90, 45, 60, 60, 90, 90, 90]

# --- INIT HAND ---
print("Connecting to Aero Hand...")
hand = AeroHand(port=PORT)
print("Connected.")

for i in range(7):
    hand.set_speed(i, 80)
    hand.set_torque(i, 400)

hand_lock = threading.Lock()
mirror = HandMirror(hand, hand_lock, status_cb=None, stopped_cb=None)  # callbacks wired after root is created

# --- FUNCTIONS ---
def set_pose(name, pose):
    print(name)
    with hand_lock:
        hand.set_joint_positions(pose)

def open_hand():
    set_pose("Open", OPEN_POSE)

def close_hand():
    set_pose("Fist", FIST_POSE)

def peace_sign():
    set_pose("Peace", PEACE_POSE)

def rock_sign():
    set_pose("Rock", ROCK_POSE)

def pinch_pose():
    set_pose("Pinch", PINCH_POSE)

count_state = [0]

def run_greet():
    """Countdown 3-2-1 (thumb curled) then wave with full hand."""
    countdown = [
        [100, 55, 30, 0, 0, 0, 60],    # 3 - index+middle+ring out, thumb+pinky in
        [100, 55, 30, 0, 0, 60, 60],    # 2 - index+middle out, thumb+ring+pinky in
        [100, 55, 30, 0, 60, 60, 60],   # 1 - index out, thumb+middle+ring+pinky in
    ]
    for n, pose in zip([3, 2, 1], countdown):
        set_pose(f"Count {n}", pose)
        time.sleep(0.8)

    # Wave: rolling curl that travels across all fingers
    # Each frame shifts which finger is most curled, creating a ripple
    # Fingers: index=3, middle=4, ring=5, pinky=6
    wave_frames = [
        [0, 0, 0, 80, 40, 10, 0],   # index fully curled, middle half, ring slight
        [0, 0, 0, 40, 80, 40, 10],   # middle fully curled, wave moves over
        [0, 0, 0, 10, 40, 80, 40],   # ring fully curled
        [0, 0, 0, 0,  10, 40, 80],   # pinky fully curled
        [0, 0, 0, 10, 0,  10, 40],   # trailing off
        [0, 0, 0, 40, 10, 0,  10],   # wave coming back
        [0, 0, 0, 80, 40, 10, 0],    # back to index
    ]
    set_pose("Wave-start", OPEN_POSE)
    time.sleep(0.2)
    for cycle in range(3):
        for i, frame in enumerate(wave_frames):
            set_pose(f"wave-{cycle}-{i}", frame)
            time.sleep(0.12)

    set_pose("Open", OPEN_POSE)

def start_greet():
    threading.Thread(target=run_greet, daemon=True).start()

def run_finger_tap():
    """Piano tap: curl each finger one at a time, then open all."""
    for _ in range(3):
        for finger_idx, label in [(3, "index"), (4, "middle"), (5, "ring"), (6, "pinky")]:
            pose = list(OPEN_POSE)
            pose[finger_idx] = 70
            set_pose(f"tap-{label}", pose)
            time.sleep(0.2)
        set_pose("tap-open", OPEN_POSE)
        time.sleep(0.15)

def start_finger_tap():
    threading.Thread(target=run_finger_tap, daemon=True).start()

def do_count():
    """Cycle through 0-5 on each press, then reset."""
    set_pose(f"Count {count_state[0]}", COUNT_POSES[count_state[0]])
    count_state[0] = (count_state[0] + 1) % 6

def run_beckon():
    """Beckoning motion: curl index finger in and out repeatedly."""
    for _ in range(4):
        set_pose("Beckon-out", BECKON_OUT)
        time.sleep(0.35)
        set_pose("Beckon-in", BECKON_IN)
        time.sleep(0.35)
    set_pose("Beckon-out", BECKON_OUT)

def start_beckon():
    threading.Thread(target=run_beckon, daemon=True).start()

def run_puppet_talk():
    """Mouth open/close: fingers vs thumb, like a talking puppet."""
    # Thumb stays still (open), fingers alternate between open and half-closed
    mouth_open = [0, 0, 0, 0, 0, 0, 0]             # all open
    mouth_closed = [0, 0, 0, 45, 45, 45, 45]        # fingers half-curled, thumb stays open
    for _ in range(6):
        set_pose("Talk-close", mouth_closed)
        time.sleep(0.25)
        set_pose("Talk-open", mouth_open)
        time.sleep(0.25)
    set_pose("Talk-done", OPEN_POSE)

def start_puppet_talk():
    threading.Thread(target=run_puppet_talk, daemon=True).start()

def run_grab():
    """Reach out open, slowly curl into a grab, hold, release."""
    set_pose("Grab-open", OPEN_POSE)
    time.sleep(0.5)
    # Slowly close in stages
    set_pose("Grab-1", [0, 0, 0, 15, 15, 15, 15])
    time.sleep(0.3)
    set_pose("Grab-2", [30, 15, 10, 30, 30, 30, 30])
    time.sleep(0.3)
    set_pose("Grab-3", [60, 30, 20, 45, 45, 45, 45])
    time.sleep(0.3)
    set_pose("Grab-grip", FIST_POSE)
    time.sleep(1.0)
    # Release
    set_pose("Grab-release", OPEN_POSE)

def start_grab():
    threading.Thread(target=run_grab, daemon=True).start()

def run_rps():
    """Rock-paper-scissors: thumb tucked, quick quiver x3, fluid throw."""
    THUMB_TUCKED    = [100, 55, 30, 0, 0, 0, 0]
    THUMB_TUCKED_IN = [100, 55, 30, 35, 35, 35, 35]

    # Human-realistic speed -- deliberate, not robotic
    with hand_lock:
        for i in range(7):
            hand.set_speed(i, 160)

    set_pose("rps-ready", THUMB_TUCKED)
    time.sleep(0.9)   # pause after thumb tucks -- "okay ready?"

    move = random.choice(["rock", "paper", "scissors"])

    # 3 quivers -- last one transitions directly into the throw
    for i in range(3):
        set_pose("rps-in", THUMB_TUCKED_IN)
        time.sleep(0.20)
        if i < 2:
            set_pose("rps-out", THUMB_TUCKED)
            time.sleep(0.26)
        else:
            # Beat before the throw
            time.sleep(0.25)
            if move == "rock":
                set_pose("RPS: Rock", FIST_POSE)
            elif move == "paper":
                set_pose("RPS: Paper", OPEN_POSE)
            else:
                set_pose("RPS: Scissors", PEACE_POSE)

    # Restore normal speed
    with hand_lock:
        for i in range(7):
            hand.set_speed(i, 80)

    root.after(0, lambda: status_label.config(text=f"RPS threw: {move.upper()}!"))

def start_rps():
    threading.Thread(target=run_rps, daemon=True).start()

def run_homing():
    status_label.config(text="Homing... (don't touch the hand)")
    root.update_idletasks()
    with hand_lock:
        success = hand.send_homing()
    if success:
        status_label.config(text="Homing complete!")
    else:
        status_label.config(text="Homing failed or timed out.")

def start_homing():
    threading.Thread(target=run_homing, daemon=True).start()

# --- GUI SETUP ---
root = tk.Tk()
root.title("Aero Hand Control")
root.configure(bg=BG)
root.state("zoomed")

# --- Scrollable container ---
canvas = tk.Canvas(root, bg=BG, highlightthickness=0)
scrollbar = tk.Scrollbar(root, orient="vertical", command=canvas.yview)
canvas.configure(yscrollcommand=scrollbar.set)

scrollbar.pack(side="right", fill="y")
canvas.pack(side="left", fill="both", expand=True)

content = tk.Frame(canvas, bg=BG)
canvas_window = canvas.create_window((0, 0), window=content, anchor="n")

def on_canvas_configure(e):
    canvas.itemconfigure(canvas_window, width=e.width)

canvas.bind("<Configure>", on_canvas_configure)
content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

# Mousewheel scrolling
def on_mousewheel(e):
    canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

canvas.bind_all("<MouseWheel>", on_mousewheel)

# --- STYLED BUTTON HELPER ---
BTN_PAD_X = 12
BTN_PAD_Y = 8

def make_button(parent, text, command, bg_color=ACCENT, hover_color=ACCENT_HOVER, row=0, col=0, colspan=1):
    btn = tk.Button(
        parent,
        text=text,
        font=("Segoe UI", 16, "bold"),
        height=2,
        command=command,
        bg=bg_color,
        fg=TEXT,
        activebackground=hover_color,
        activeforeground="#ffffff",
        bd=0,
        relief="flat",
        cursor="hand2",
    )
    btn.grid(row=row, column=col, columnspan=colspan, padx=BTN_PAD_X, pady=BTN_PAD_Y, sticky="ew")
    btn.bind("<Enter>", lambda e: btn.config(bg=hover_color))
    btn.bind("<Leave>", lambda e: btn.config(bg=bg_color))
    return btn

# Title
title_frame = tk.Frame(content, bg=BG)
title_frame.pack(pady=(30, 4))
tk.Label(
    title_frame,
    text="AERO HAND",
    font=("Segoe UI", 32, "bold"),
    fg=TITLE_COLOR,
    bg=BG,
).pack()
tk.Label(
    title_frame,
    text="WiscoHumanoids",
    font=("Segoe UI", 13),
    fg=STATUS_COLOR,
    bg=BG,
).pack()

# Separator
tk.Frame(content, bg=ACCENT, height=2).pack(fill="x", padx=60, pady=(16, 8))

# --- Poses Section ---
tk.Label(content, text="POSES", font=("Segoe UI", 12, "bold"), fg=STATUS_COLOR, bg=BG).pack(pady=(8, 4))

pose_frame = tk.Frame(content, bg=BG)
pose_frame.pack(fill="x", padx=60)
pose_frame.columnconfigure(0, weight=1)
pose_frame.columnconfigure(1, weight=1)

make_button(pose_frame, "OPEN",  open_hand,   row=0, col=0)
make_button(pose_frame, "FIST",  close_hand,  row=0, col=1)
make_button(pose_frame, "PEACE", peace_sign,  row=1, col=0)
make_button(pose_frame, "ROCK",  rock_sign,   row=1, col=1)
make_button(pose_frame, "PINCH", pinch_pose,  row=2, col=0)
make_button(pose_frame, "COUNT", do_count,    row=2, col=1)

# Separator
tk.Frame(content, bg=ACCENT, height=2).pack(fill="x", padx=60, pady=(16, 8))

# --- Sequences Section ---
tk.Label(content, text="SEQUENCES", font=("Segoe UI", 12, "bold"), fg=STATUS_COLOR, bg=BG).pack(pady=(8, 4))

seq_frame = tk.Frame(content, bg=BG)
seq_frame.pack(fill="x", padx=60)
seq_frame.columnconfigure(0, weight=1)
seq_frame.columnconfigure(1, weight=1)

make_button(seq_frame, "GREET",       start_greet,       bg_color=SEQ_BG, hover_color=SEQ_HOVER, row=0, col=0)
make_button(seq_frame, "FINGER TAP",  start_finger_tap,  bg_color=SEQ_BG, hover_color=SEQ_HOVER, row=0, col=1)
make_button(seq_frame, "BECKON",      start_beckon,      bg_color=SEQ_BG, hover_color=SEQ_HOVER, row=1, col=0)
make_button(seq_frame, "PUPPET TALK", start_puppet_talk,  bg_color=SEQ_BG, hover_color=SEQ_HOVER, row=1, col=1)
make_button(seq_frame, "GRAB",        start_grab,        bg_color=SEQ_BG, hover_color=SEQ_HOVER, row=2, col=0)
make_button(seq_frame, "ROCK PAPER SCISSORS", start_rps, bg_color=SEQ_BG, hover_color=SEQ_HOVER, row=2, col=1)

# Separator
tk.Frame(content, bg=ACCENT, height=2).pack(fill="x", padx=60, pady=(16, 8))

# --- System Section ---
tk.Label(content, text="SYSTEM", font=("Segoe UI", 12, "bold"), fg=STATUS_COLOR, bg=BG).pack(pady=(8, 4))

sys_frame = tk.Frame(content, bg=BG)
sys_frame.pack(fill="x", padx=60)
sys_frame.columnconfigure(0, weight=1)
sys_frame.columnconfigure(1, weight=1)

make_button(sys_frame, "HOMING", start_homing, bg_color=HOMING_BG, hover_color=HOMING_HOVER, row=0, col=0)

MIRROR_ON_BG    = "#1a1a5c"
MIRROR_ON_HOVER = "#2a2a8a"

def _set_mirror_btn_off():
    btn_mirror.config(bg=SEQ_BG, text="MIRROR  OFF")
    btn_mirror.bind("<Leave>", lambda e: btn_mirror.config(bg=SEQ_BG))
    btn_mirror.bind("<Enter>", lambda e: btn_mirror.config(bg=SEQ_HOVER))

def _set_mirror_btn_on():
    btn_mirror.config(bg=MIRROR_ON_BG, text="MIRROR  ON")
    btn_mirror.bind("<Leave>", lambda e: btn_mirror.config(bg=MIRROR_ON_BG))
    btn_mirror.bind("<Enter>", lambda e: btn_mirror.config(bg=MIRROR_ON_HOVER))

def toggle_mirror():
    mirror.toggle()
    if mirror.is_running():
        _set_mirror_btn_on()
    else:
        _set_mirror_btn_off()

btn_mirror = make_button(sys_frame, "MIRROR  OFF", toggle_mirror, bg_color=SEQ_BG, hover_color=SEQ_HOVER, row=0, col=1)

# Status bar
status_label = tk.Label(
    content,
    text="Ready",
    font=("Segoe UI", 13),
    fg=STATUS_COLOR,
    bg=CARD_BG,
    anchor="center",
    padx=20,
    pady=10,
)
status_label.pack(fill="x", padx=60, pady=(20, 30))

# Wire callbacks now that status_label and btn_mirror exist
mirror._status_cb = lambda msg: root.after(0, lambda: status_label.config(text=msg))
mirror._stopped_cb = lambda: root.after(0, _set_mirror_btn_off)

# --- CLEAN EXIT ---
def on_close():
    print("Closing...")
    hand.set_joint_positions([0] * 7)
    hand.close()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)
root.mainloop()
