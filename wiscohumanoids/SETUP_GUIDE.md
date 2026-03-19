# WiscoHumanoids - Aero Hand GUI Setup Guide

Get from zero to controlling the Aero Hand in ~5 minutes.

---

## Prerequisites

- **Python 3.10+** installed ([python.org/downloads](https://www.python.org/downloads/))
- **Aero Hand** connected to your PC via USB
- **Windows** (these instructions are Windows-focused, but Linux works too)

---

## Step-by-Step Setup

### 1. Clone the repo

```bash
git clone https://github.com/wiscohumanoids/aero-hand-open.git
cd aero-hand-open
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it:

```bash
# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Windows (CMD)
.\venv\Scripts\activate.bat

# Linux/Mac
source venv/bin/activate
```

### 3. Install the SDK

```bash
cd sdk
pip install -e .
cd ..
```

This installs the `aero-open-sdk` package (pyserial + the hand control library) in editable mode.

### 4. Install GUI dependencies

```bash
pip install -r wiscohumanoids/requirements.txt
```

(This is just pyserial, which the SDK already pulls in -- but it's here for completeness. In the future, it will include other libraries for our custom GUI.)

### 5. Find your COM port

1. Plug the Aero Hand into USB.
2. Open **Device Manager** (search for it in the Start menu).
3. Expand **Ports (COM & LPT)**.
4. Note the COM port number (e.g., `COM3`, `COM5`).

On Linux, check `ls /dev/ttyACM* /dev/ttyUSB*` instead.

### 6. Edit the port in the script

Open `wiscohumanoids/simple_hand_gui.py` and change this line near the top:

```python
PORT = "COM5"   # CHANGE THIS to your port
```

### 7. Run the GUI

```bash
python wiscohumanoids/simple_hand_gui.py
```

You should see a window with buttons: **OPEN, FIST, PEACE, ROCK, PINCH, HOMING**, and a text field for signing letters.

---

## First-Time Use: Homing

When the hand is first powered on, you **must** run the homing sequence before poses will work correctly:

1. Make sure the hand is in a safe position (fingers not jammed against anything).
2. Click the **HOMING** button in the GUI.
3. Wait ~3 minutes. The hand will calibrate all its motors. Do not touch it during this process.
4. Once homing completes, you're good to go -- try the gesture buttons!

---

## Button Reference

| Button | What it does |
|--------|-------------|
| OPEN | Fully opens all fingers |
| FIST | Closes into a fist |
| PEACE | Peace/victory sign |
| ROCK | Rock/horns sign (index + pinky out) |
| PINCH | Pinch grip (thumb + index) |
| HOMING | Runs the homing/calibration sequence (~3 min) |
| SIGN TEXT | Type text in the box, click to finger-spell each letter |

---

## Troubleshooting

**"Could not open port" / connection error:**
- Double-check your COM port in Device Manager.
- Make sure no other program (Arduino IDE, PuTTY, etc.) has the port open.
- Try unplugging and replugging the USB cable.

**Hand doesn't move after connecting:**
- You probably need to run homing first. Click the HOMING button.

**Python not found / pip not recognized:**
- Make sure Python 3.10+ is installed and added to your PATH.
- On Windows, try `py` instead of `python`.

**Permission denied (Linux):**
- Add yourself to the `dialout` group: `sudo usermod -a -G dialout $(whoami)`
- Log out and back in, then retry.

---

## Want to add your own gestures?

Look at the pose definitions at the top of `simple_hand_gui.py`. Each pose is a list of 7 numbers (0-100) representing joint positions:

```
[thumb_abd, thumb_flex, thumb_tendon, index, middle, ring, pinky]
```

- `0` = fully open
- Higher values = more closed/flexed

Just define a new pose list and wire up a button!
