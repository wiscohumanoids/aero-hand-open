"""
heal_finger.py -- WiscoHumanoids

Interactive recovery script for a stuck/unresponsive finger.
Run this standalone if a finger is not responding to commands.

Aero 7-DOF actuator index reference:
    0: thumb_cmc_abd
    1: thumb_cmc_flex
    2: thumb_tendon
    3: index_tendon
    4: middle_tendon
    5: ring_tendon      <-- most likely culprit
    6: pinky_tendon

Usage:
    python wiscohumanoids/heal_finger.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk", "src"))
from aero_open_sdk.aero_hand import AeroHand

PORT = "COM5"  # CHANGE if needed

FINGER_NAMES = {
    0: "thumb_cmc_abd",
    1: "thumb_cmc_flex",
    2: "thumb_tendon",
    3: "index_tendon",
    4: "middle_tendon",
    5: "ring_tendon",
    6: "pinky_tendon",
}

def prompt(msg):
    return input(f"\n{msg} [Enter to continue, q to quit]: ").strip().lower()

def open_all(hand):
    hand.set_joint_positions([0] * 7)
    time.sleep(1.0)

def step1_drop_torque(hand, finger_id):
    """
    Drop torque on the stuck finger to near zero so the tendon
    can relax without fighting the motor. Hold for a few seconds.
    """
    print(f"\n[Step 1] Dropping torque on actuator {finger_id} ({FINGER_NAMES[finger_id]}) to let it relax...")
    # Set all others to normal, stuck finger to minimal holding torque
    for i in range(7):
        hand.set_torque(i, 50 if i == finger_id else 400)
    hand.set_joint_positions([0] * 7)
    time.sleep(3.0)
    print("  Done. Finger should have relaxed slightly.")

def step2_slow_open(hand, finger_id):
    """
    Very slowly command the finger to open at low speed and low torque.
    Avoids forcing it -- just nudges it.
    """
    print(f"\n[Step 2] Slowly nudging actuator {finger_id} open at low speed + low torque...")
    hand.set_speed(finger_id, 10)   # very slow
    hand.set_torque(finger_id, 150) # low force
    pose = [0] * 7
    hand.set_joint_positions(pose)
    time.sleep(4.0)
    print("  Done.")

def step3_gentle_flex(hand, finger_id):
    """
    Gently flex the finger a small amount then back to open, a few times.
    This can break a stuck tendon loose without over-pulling.
    """
    print(f"\n[Step 3] Gentle flex/extend cycles on actuator {finger_id}...")
    hand.set_speed(finger_id, 15)
    hand.set_torque(finger_id, 150)

    for cycle in range(4):
        print(f"  Cycle {cycle + 1}/4 -- closing slightly...")
        pose = [0] * 7
        pose[finger_id] = 20   # small curl, not full close
        hand.set_joint_positions(pose)
        time.sleep(2.0)

        print(f"  Cycle {cycle + 1}/4 -- opening...")
        pose[finger_id] = 0
        hand.set_joint_positions(pose)
        time.sleep(2.0)

    print("  Gentle flex cycles done.")

def step4_restore_and_check(hand, finger_id):
    """
    Restore normal speed/torque, open all fingers, read back positions.
    """
    print(f"\n[Step 4] Restoring normal speed and torque...")
    for i in range(7):
        hand.set_speed(i, 80)
        hand.set_torque(i, 400)
    open_all(hand)

    print("\n  Reading back current actuator positions:")
    try:
        pos = hand.get_actuations()
        for i, v in enumerate(pos):
            marker = "  <-- healed finger" if i == finger_id else ""
            print(f"    Actuator {i} ({FINGER_NAMES[i]}): {v:.1f} deg{marker}")
    except Exception as e:
        print(f"  Could not read positions: {e}")

def step5_homing(hand):
    """
    Full homing sequence as a last resort -- clears all internal state.
    """
    print("\n[Step 5] Running full homing sequence (~3 min)...")
    print("  Make sure no fingers are obstructed before continuing.")
    if prompt("Ready to home?") == "q":
        return
    success = hand.send_homing()
    if success:
        print("  Homing complete.")
    else:
        print("  Homing timed out or failed. Try power cycling the hand.")

def main():
    print("=" * 55)
    print("  Aero Hand -- Finger Recovery Script")
    print("  WiscoHumanoids")
    print("=" * 55)
    print("\nActuator index map:")
    for idx, name in FINGER_NAMES.items():
        print(f"  {idx}: {name}")

    raw = input("\nWhich actuator is stuck? (default 5 = ring): ").strip()
    finger_id = int(raw) if raw.isdigit() and 0 <= int(raw) <= 6 else 5
    print(f"\nTargeting actuator {finger_id}: {FINGER_NAMES[finger_id]}")

    print(f"\nConnecting on {PORT}...")
    hand = AeroHand(port=PORT)
    print("Connected.")

    # Always set all fingers to a safe baseline speed/torque first
    for i in range(7):
        hand.set_speed(i, 80)
        hand.set_torque(i, 400)

    print("\nStarting recovery sequence. Follow each step carefully.")
    print("The hand will be commanded to open between each step.")

    # --- Step 1: drop torque, let it relax ---
    if prompt("Step 1: Drop torque and relax the finger?") == "q":
        hand.close(); return
    step1_drop_torque(hand, finger_id)

    # --- Step 2: slow open ---
    if prompt("Step 2: Slowly command it open at low speed/torque?") == "q":
        hand.close(); return
    step2_slow_open(hand, finger_id)

    # --- Step 3: gentle flex cycles ---
    if prompt("Step 3: Run gentle flex/extend cycles to loosen it?") == "q":
        hand.close(); return
    step3_gentle_flex(hand, finger_id)

    # --- Step 4: restore and check ---
    if prompt("Step 4: Restore normal settings and check positions?") == "q":
        hand.close(); return
    step4_restore_and_check(hand, finger_id)

    # --- Step 5: full homing (optional) ---
    print("\nIf the finger is still not responding well, a full homing")
    print("sequence will reset all internal servo state.")
    if prompt("Step 5: Run full homing? (only if still stuck)") != "q":
        step5_homing(hand)

    # Final open
    print("\nOpening all fingers and closing connection...")
    open_all(hand)
    hand.close()
    print("Done. If the finger is still unresponsive after homing,")
    print("check the physical tendon routing and consider contacting TetherIA.")

if __name__ == "__main__":
    main()
