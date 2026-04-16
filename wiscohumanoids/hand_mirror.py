"""
hand_mirror.py -- WiscoHumanoids

Tracks the operator's hand via webcam (MediaPipe Tasks API) and maps the
detected joint angles onto the Aero Hand's 7-DOF compact joint
representation, respecting all hardware limits.

MediaPipe hand landmark indices:
    Wrist:  0
    Thumb:  1(CMC) 2(MCP) 3(IP) 4(TIP)
    Index:  5(MCP) 6(PIP) 7(DIP) 8(TIP)
    Middle: 9(MCP) 10(PIP) 11(DIP) 12(TIP)
    Ring:   13(MCP) 14(PIP) 15(DIP) 16(TIP)
    Pinky:  17(MCP) 18(PIP) 19(DIP) 20(TIP)

Aero 7-DOF compact representation:
    [0] thumb_cmc_abd  -- 0..100
    [1] thumb_cmc_flex -- 0..55
    [2] thumb_tendon   -- 0..30
    [3] index_tendon   -- 0..60
    [4] middle_tendon  -- 0..60
    [5] ring_tendon    -- 0..60
    [6] pinky_tendon   -- 0..60
"""

import os
import threading
import math
import time

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import mediapipe as mp
except ImportError:
    mp = None

OPEN_POSE = [0, 0, 0, 0, 0, 0, 0]

# Safe output ranges matching GUI presets
JOINT_SAFE_MAX = [100, 55, 30, 60, 60, 60, 60]
JOINT_SAFE_MIN = [0,   0,  0,  0,  0,  0,  0]

# Send rate: 15 Hz -- comfortable for the servos without flooding the bus
SEND_INTERVAL = 0.067

# Smoothing factor: how much of the new target to blend in each frame.
# Lower = smoother but more lag. 0.35 is a good middle ground.
ALPHA = 0.35

CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),        # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),         # index
    (0, 9), (9, 10), (10, 11), (11, 12),    # middle
    (0, 13), (13, 14), (14, 15), (15, 16),  # ring
    (0, 17), (17, 18), (18, 19), (19, 20),  # pinky
    (5, 9), (9, 13), (13, 17),              # palm
]


def _angle_between(a, b, c):
    """Angle in degrees at point b in the chain a-b-c."""
    ax, ay = a.x - b.x, a.y - b.y
    cx, cy = c.x - b.x, c.y - b.y
    dot   = ax * cx + ay * cy
    mag_a = math.sqrt(ax**2 + ay**2)
    mag_c = math.sqrt(cx**2 + cy**2)
    if mag_a < 1e-6 or mag_c < 1e-6:
        return 0.0
    return math.degrees(math.acos(max(-1.0, min(1.0, dot / (mag_a * mag_c)))))


def _finger_curl(lm, mcp_idx, pip_idx, tip_idx):
    """
    Curl in [0, 1]: 0 = straight, 1 = fully curled.
    Uses the angle at the PIP joint between MCP and TIP.
    """
    angle = _angle_between(lm[mcp_idx], lm[pip_idx], lm[tip_idx])
    # 170°+ = straight, ~45° = fully curled
    return 1.0 - max(0.0, min(1.0, (angle - 45.0) / 125.0))


def _thumb_curl(lm):
    """
    Thumb curl toward palm: measure how close the thumb tip (lm[4]) is to
    the index finger base (lm[5]) relative to how far it is when fully open.
    When the thumb curls across the palm toward the fingers, tip approaches
    lm[5]. This is robust to hand orientation and doesn't rely on Z depth.

    Reference distances (normalised by wrist-to-middle-MCP palm width):
      ~0.8  = thumb fully extended away from fingers
      ~0.15 = thumb tip touching index MCP (fully curled in)
    """
    wrist   = lm[0]
    tip     = lm[4]
    idx_mcp = lm[5]
    mid_mcp = lm[9]

    palm_w = math.sqrt((mid_mcp.x - wrist.x)**2 + (mid_mcp.y - wrist.y)**2)
    if palm_w < 1e-6:
        return 0.0

    dist = math.sqrt((tip.x - idx_mcp.x)**2 + (tip.y - idx_mcp.y)**2) / palm_w

    # Closer to index MCP = more curled. Invert and normalise.
    # 0.7 = extended, 0.1 = curled across palm
    return max(0.0, min(1.0, (0.7 - dist) / 0.55))


def _thumb_abduction(lm):
    """
    Thumb abduction: angle at the wrist (lm[0]) between thumb CMC (lm[1])
    and index MCP (lm[5]).
    ~20° = fully adducted, ~60° = fully spread (tighter window = more reactive)
    """
    angle = _angle_between(lm[1], lm[0], lm[5])
    return max(0.0, min(1.0, (angle - 20.0) / 40.0))


def landmarks_to_pose(lm):
    """Convert 21 MediaPipe landmarks to Aero 7-DOF compact pose (raw, unsmoothed)."""
    raw = [
        _thumb_abduction(lm),            # [0] thumb_cmc_abd
        _thumb_curl(lm),                 # [1] thumb_cmc_flex
        _thumb_curl(lm),                 # [2] thumb_tendon
        _finger_curl(lm, 5,  6,  8),    # [3] index
        _finger_curl(lm, 9,  10, 12),   # [4] middle
        _finger_curl(lm, 13, 14, 16),   # [5] ring
        _finger_curl(lm, 17, 18, 20),   # [6] pinky
    ]
    return [
        raw[i] * (JOINT_SAFE_MAX[i] - JOINT_SAFE_MIN[i]) + JOINT_SAFE_MIN[i]
        for i in range(7)
    ]


def _smooth(current, target, alpha=ALPHA):
    """Exponential smoothing: blend current toward target by alpha."""
    return [current[i] + alpha * (target[i] - current[i]) for i in range(7)]


def _to_int_pose(pose):
    return [int(round(v)) for v in pose]


def _draw_landmarks(frame, lm, h, w):
    pts = [(int(p.x * w), int(p.y * h)) for p in lm]
    for s, e in CONNECTIONS:
        cv2.line(frame, pts[s], pts[e], (0, 200, 100), 2)
    for x, y in pts:
        cv2.circle(frame, (x, y), 4, (255, 255, 255), -1)


class HandMirror:
    """
    Toggle-able mirror loop: camera -> MediaPipe -> Aero Hand.

    Callbacks:
        status_cb(str)  -- status text for the GUI label
        stopped_cb()    -- fired whenever the loop exits (button, Q key,
                           or camera failure) so the GUI button stays in sync
    """

    def __init__(self, hand, hand_lock, status_cb=None, stopped_cb=None):
        self._hand       = hand
        self._lock       = hand_lock
        self._status_cb  = status_cb
        self._stopped_cb = stopped_cb
        self._running    = False
        self._thread     = None

    def is_running(self):
        return self._running

    def start(self):
        if self._running:
            return
        if cv2 is None or mp is None:
            self._set_status("Mirror requires: pip install opencv-python mediapipe")
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self._set_status("Mirror ON -- show your hand to the camera")

    def stop(self):
        self._running = False

    def toggle(self):
        if self._running:
            self.stop()
        else:
            self.start()

    def _set_status(self, msg):
        print(msg)
        if self._status_cb:
            self._status_cb(msg)

    def _on_stopped(self):
        self._set_status("Mirror OFF")
        if self._stopped_cb:
            self._stopped_cb()

    def _loop(self):
        from mediapipe.tasks.python import vision as mp_vision
        from mediapipe.tasks.python.core import base_options as mp_base

        model_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "sdk", "assets", "hand_landmarker.task")
        )
        if not os.path.exists(model_path):
            self._running = False
            self._set_status(f"Mirror: model not found at {model_path}")
            self._on_stopped()
            return

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            self._running = False
            self._set_status("Mirror: could not open camera")
            self._on_stopped()
            return

        options = mp_vision.HandLandmarkerOptions(
            base_options=mp_base.BaseOptions(model_asset_path=model_path),
            num_hands=1,
            min_hand_detection_confidence=0.7,
            min_hand_presence_confidence=0.7,
            min_tracking_confidence=0.6,
        )

        # Smoothed pose state (floats, not yet rounded to int)
        smoothed = [float(v) for v in OPEN_POSE]

        # Send open immediately on start
        with self._lock:
            self._hand.set_joint_positions(OPEN_POSE)

        last_send      = 0.0
        no_hand_frames = 0   # consecutive frames with no detection
        NO_HAND_THRESHOLD = 3  # frames before we treat hand as truly gone

        with mp_vision.HandLandmarker.create_from_options(options) as detector:
            while self._running:
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.01)
                    continue

                frame  = cv2.flip(frame, 1)
                h, w   = frame.shape[:2]
                rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                results = detector.detect(mp_img)
                now = time.time()

                if results.hand_landmarks:
                    no_hand_frames = 0
                    lm = results.hand_landmarks[0]
                    _draw_landmarks(frame, lm, h, w)

                    # Compute raw target and smooth toward it
                    target   = landmarks_to_pose(lm)
                    smoothed = _smooth(smoothed, target)

                    if now - last_send >= SEND_INTERVAL:
                        with self._lock:
                            self._hand.set_joint_positions(_to_int_pose(smoothed))
                        last_send = now

                else:
                    no_hand_frames += 1
                    if no_hand_frames >= NO_HAND_THRESHOLD:
                        # Smoothly drift back to open rather than snapping
                        smoothed = _smooth(smoothed, [float(v) for v in OPEN_POSE], alpha=0.2)
                        if now - last_send >= SEND_INTERVAL:
                            with self._lock:
                                self._hand.set_joint_positions(_to_int_pose(smoothed))
                            last_send = now

                cv2.imshow("Hand Mirror", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    self._running = False

        cap.release()
        cv2.destroyAllWindows()

        with self._lock:
            self._hand.set_joint_positions(OPEN_POSE)

        self._on_stopped()
