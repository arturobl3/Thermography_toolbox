
"""
Standalone Test for Filter Wheel Movement Sequence

This script replicates the exact movement logic from main.py but runs
independently without needing hyperspectral.cpp to send serial commands.

It will:
1. Initialize motors and encoders (same as main.py)
2. Move to home position [0,0] (same as calibration)
3. Test moving through all filter combinations
4. Return to home position

Use this to debug motor movement issues without running the full system.
"""

import time
from machine import Pin, I2C

# ============================================================================
# CLASSES (copied exactly from main.py)
# ============================================================================

class AS5600Encoder:
    def __init__(self, i2c):
        """
        Class which handles encoder output.
        """
        self.i2c = i2c
        self.addr = 0x36

    def read_angle(self):
        """
        Method which read raw output of the encoder and convert it to angle.
        """
        try:
            raw = self.i2c.readfrom_mem(self.addr, 0x0E, 2)
            angle = (raw[0] << 8 | raw[1]) & 0x0FFF
            return angle * 360.0 / 4096
        except:
            return -1


class StepperMotor:
    def __init__(self, dir_pin, step_pin, ms1, ms2, ms3, invert_direction=False):
        """
        Class which handles stepper motor motion.
        """
        self.dir = Pin(dir_pin, Pin.OUT)
        self.step = Pin(step_pin, Pin.OUT)
        self.invert_direction = invert_direction
        Pin(ms1, Pin.OUT).value(1)
        Pin(ms2, Pin.OUT).value(0)
        Pin(ms3, Pin.OUT).value(0)
        self.step_delay = 0.003  # Increased from 0.002 to reduce overshoot

    def move_steps(self, steps, direction):
        """
        Method which given number of steps and direction will rotate motor.
        """
        actual_direction = (1 - direction) if self.invert_direction else direction
        self.dir.value(actual_direction)
        for _ in range(steps):
            self.step.value(1)
            time.sleep(self.step_delay)
            self.step.value(0)
            time.sleep(self.step_delay)

    def move_to_angle_with_encoder(self, target_angle, encoder, debug=False):
        """
        Feedback loop position control of the stepper motor.
        """
        max_attempts = 1000
        tolerance = 2  # Degrees - acceptable positioning error
        encoder_error_count = 0
        max_encoder_errors = 5
        stuck_counter = 0
        last_position = -999
        
        if debug:
            print(f"[DEBUG] Moving to target: {target_angle:.2f}°")

        for attempt in range(max_attempts):
            current_angle = encoder.read_angle()
            
            if current_angle == -1:
                encoder_error_count += 1
                if debug:
                    print(f"[DEBUG] Encoder read error {encoder_error_count}/{max_encoder_errors}")
                if encoder_error_count >= max_encoder_errors:
                    print(f"[ERROR] Encoder failed after {max_encoder_errors} consecutive errors")
                    return False
                time.sleep(0.01)
                continue
            
            encoder_error_count = 0
            
            # Check if motor is stuck
            if abs(current_angle - last_position) < 0.5 and attempt > 10:
                stuck_counter += 1
                if stuck_counter > 50:
                    print(f"[ERROR] Motor stuck at {current_angle:.2f}°, target {target_angle:.2f}°")
                    return False
            else:
                stuck_counter = 0
            last_position = current_angle
            
            diff = (target_angle - current_angle + 360) % 360
            if diff > 180:
                diff -= 360

            if debug and attempt % 50 == 0:  # Changed from 20
                direction_str = "CW" if diff > 0 else "CCW"
                print(f"[DEBUG] Attempt {attempt}: Current={current_angle:.2f}°, Diff={diff:.2f}° ({direction_str})")

            if abs(diff) < tolerance:
                if debug:
                    print(f"[DEBUG] Target reached! Final angle: {current_angle:.2f}°")
                return True

            # Calculate direction (will be inverted by move_steps if self.invert_direction=True)
            direction = 1 if diff > 0 else 0
            
            # Adaptive step size - smaller steps to reduce overshoot
            if abs(diff) > 30:
                steps = 5  # Reduced from 10
            elif abs(diff) > 10:
                steps = 2  # Reduced from 3
            else:
                steps = 1
            
            if debug and attempt == 0:
                dir_str = "CLOCKWISE" if direction == 1 else "COUNTER-CLOCKWISE"
                print(f"[DEBUG] First move: {steps} steps {dir_str} (DIR={direction})")
            
            self.move_steps(steps, direction)
            time.sleep(0.01)
        
        final_angle = encoder.read_angle()
        print(f"[WARNING] Max attempts reached. Target={target_angle:.2f}°, Final={final_angle:.2f}°")
        return False


# ============================================================================
# INITIALIZATION (same as main.py)
# ============================================================================

print("\n" + "="*70)
print("  FILTER WHEEL MOVEMENT TEST (Standalone)")
print("="*70)

print("\n[INFO] Initializing I2C buses and encoders...")
i2c_top = I2C(0, scl=Pin(21), sda=Pin(20))
i2c_bottom = I2C(1, scl=Pin(27), sda=Pin(26))

encoder_top = AS5600Encoder(i2c_top)
encoder_bottom = AS5600Encoder(i2c_bottom)

print("[INFO] Testing encoder connections...")
test_top = encoder_top.read_angle()
test_bottom = encoder_bottom.read_angle()

if test_top == -1:
    print("[ERROR] TOP encoder not responding! Check I2C0 wiring")
else:
    print(f"[INFO] TOP encoder OK - reading {test_top:.2f}°")

if test_bottom == -1:
    print("[ERROR] BOTTOM encoder not responding! Check I2C1 wiring")
else:
    print(f"[INFO] BOTTOM encoder OK - reading {test_bottom:.2f}°")

print("\n[INFO] Initializing motors...")
motor_top = StepperMotor(dir_pin=2, step_pin=3, ms1=6, ms2=7, ms3=8, invert_direction=False)
motor_bottom = StepperMotor(dir_pin=4, step_pin=5, ms1=10, ms2=11, ms3=12, invert_direction=True)

print("[INFO] Motors initialized:")
print("  TOP motor: Standard direction (invert_direction=False)")
print("  BOTTOM motor: Inverted direction (invert_direction=True)")

# Hard coded positions (same as main.py)
top_angles = [344.88, 19.78, 55.68, 91.58, 127.58, 163.92, 198.98, 235.02]
bottom_angles = [116.89, 152.75, 183.87, 225.09, 264.64, 297.51, 334.6, 11.6]


def move_filter_wheels_to(i, j, debug=False):
    """Move both filter wheels to position [i, j]"""
    target_top = top_angles[i]
    target_bottom = bottom_angles[j]

    if debug:
        print(f"\n[INFO] Moving to position [{i},{j}]: TOP={target_top:.2f}°, BOTTOM={target_bottom:.2f}°")
    
    success_top = motor_top.move_to_angle_with_encoder(target_top, encoder_top, debug)
    if not success_top:
        print(f"[ERROR] Top motor failed to reach position {i}")
    
    time.sleep(0.5)
    
    success_bottom = motor_bottom.move_to_angle_with_encoder(target_bottom, encoder_bottom, debug)
    if not success_bottom:
        print(f"[ERROR] Bottom motor failed to reach position {j}")
    
    time.sleep(0.5)
    
    return success_top and success_bottom


# ============================================================================
# TEST SEQUENCE
# ============================================================================

print("\n" + "="*70)
print("  CALIBRATION PHASE")
print("="*70)

print("\n[INFO] Reading current encoder positions...")
top_current = encoder_top.read_angle()
bottom_current = encoder_bottom.read_angle()
print(f"[INFO] TOP encoder: {top_current:.2f}°")
print(f"[INFO] BOTTOM encoder: {bottom_current:.2f}°")

time.sleep(0.5)
print("\n[INFO] Moving to home position [0,0]...")
success = move_filter_wheels_to(0, 0, debug=True)

if success:
    print("\n✓ Calibration complete - motors at home position")
else:
    print("\n✗ Calibration FAILED!")
    print("Cannot continue with test if calibration fails.")
    print("\nCheck:")
    print("  1. Encoder readings are valid")
    print("  2. Motors can physically move")
    print("  3. Target positions are reachable")
    input("\nPress ENTER to exit...")
    import sys
    sys.exit(1)

time.sleep(1)

# ============================================================================
# INTERACTIVE TEST MENU
# ============================================================================

print("\n" + "="*70)
print("  TEST MENU")
print("="*70)
print("\nChoose a test:")
print("  1. Test all 64 positions (full scan)")
print("  2. Test specific position [i,j]")
print("  3. Test first row (i=0, j=0..7)")
print("  4. Test diagonal (i=j)")
print("  5. Return to home [0,0]")
print("  6. Show current position")
print("  q. Quit")

while True:
    print("\n" + "-"*70)
    choice = input("Enter choice: ").strip()
    
    if choice == 'q':
        print("\n[INFO] Returning to home position before exit...")
        move_filter_wheels_to(0, 0, debug=False)
        print("[INFO] Test complete. Goodbye!")
        break
    
    elif choice == '1':
        print("\n[INFO] Testing all 64 positions...")
        print("[INFO] This will take several minutes.")
        confirm = input("Continue? (y/n): ").strip().lower()
        if confirm != 'y':
            continue
        
        failed_positions = []
        for i in range(8):
            for j in range(8):
                print(f"\n--- Position [{i},{j}] ---")
                success = move_filter_wheels_to(i, j, debug=False)
                
                # Verify position
                top_actual = encoder_top.read_angle()
                bottom_actual = encoder_bottom.read_angle()
                top_error = abs(top_angles[i] - top_actual)
                bottom_error = abs(bottom_angles[j] - bottom_actual)
                
                if top_error > 180:
                    top_error = 360 - top_error
                if bottom_error > 180:
                    bottom_error = 360 - bottom_error
                
                print(f"  TOP: Target={top_angles[i]:.2f}°, Actual={top_actual:.2f}°, Error={top_error:.2f}°")
                print(f"  BOTTOM: Target={bottom_angles[j]:.2f}°, Actual={bottom_actual:.2f}°, Error={bottom_error:.2f}°")
                
                if not success or top_error > 2 or bottom_error > 2:
                    failed_positions.append((i, j))
                    print(f"  ✗ FAILED")
                else:
                    print(f"  ✓ OK")
                
                time.sleep(0.5)
        
        print("\n" + "="*70)
        print("  FULL SCAN RESULTS")
        print("="*70)
        if not failed_positions:
            print("✓ All 64 positions reached successfully!")
        else:
            print(f"✗ {len(failed_positions)} positions failed:")
            for i, j in failed_positions:
                print(f"  [{i},{j}]")
    
    elif choice == '2':
        try:
            pos_input = input("Enter position as 'i j' (e.g., '3 5'): ").strip()
            i, j = map(int, pos_input.split())
            if i < 0 or i >= 8 or j < 0 or j >= 8:
                print("[ERROR] Invalid position. Must be 0-7.")
                continue
            
            print(f"\n[INFO] Moving to position [{i},{j}]...")
            success = move_filter_wheels_to(i, j, debug=True)
            
            if success:
                print(f"\n✓ Successfully moved to [{i},{j}]")
            else:
                print(f"\n✗ Failed to reach [{i},{j}]")
        except:
            print("[ERROR] Invalid input. Use format: i j")
    
    elif choice == '3':
        print("\n[INFO] Testing first row (j=0..7)...")
        for j in range(8):
            print(f"\n--- Position [0,{j}] ---")
            success = move_filter_wheels_to(0, j, debug=False)
            top_actual = encoder_top.read_angle()
            bottom_actual = encoder_bottom.read_angle()
            print(f"  TOP: {top_actual:.2f}° (target: {top_angles[0]:.2f}°)")
            print(f"  BOTTOM: {bottom_actual:.2f}° (target: {bottom_angles[j]:.2f}°)")
            print(f"  {'✓ OK' if success else '✗ FAILED'}")
            time.sleep(0.5)
    
    elif choice == '4':
        print("\n[INFO] Testing diagonal (i=j)...")
        for i in range(8):
            print(f"\n--- Position [{i},{i}] ---")
            success = move_filter_wheels_to(i, i, debug=False)
            top_actual = encoder_top.read_angle()
            bottom_actual = encoder_bottom.read_angle()
            print(f"  TOP: {top_actual:.2f}° (target: {top_angles[i]:.2f}°)")
            print(f"  BOTTOM: {bottom_actual:.2f}° (target: {bottom_angles[i]:.2f}°)")
            print(f"  {'✓ OK' if success else '✗ FAILED'}")
            time.sleep(0.5)
    
    elif choice == '5':
        print("\n[INFO] Returning to home [0,0]...")
        success = move_filter_wheels_to(0, 0, debug=True)
        if success:
            print("✓ Home position reached")
        else:
            print("✗ Failed to reach home")
    
    elif choice == '6':
        top_pos = encoder_top.read_angle()
        bottom_pos = encoder_bottom.read_angle()
        print(f"\n[INFO] Current positions:")
        print(f"  TOP: {top_pos:.2f}°")
        print(f"  BOTTOM: {bottom_pos:.2f}°")
        
        # Find closest programmed positions
        top_closest = min(range(8), key=lambda i: min(abs(top_angles[i] - top_pos), 360 - abs(top_angles[i] - top_pos)))
        bottom_closest = min(range(8), key=lambda j: min(abs(bottom_angles[j] - bottom_pos), 360 - abs(bottom_angles[j] - bottom_pos)))
        
        print(f"  Closest to position: [{top_closest},{bottom_closest}]")
        print(f"  TOP target: {top_angles[top_closest]:.2f}°")
        print(f"  BOTTOM target: {bottom_angles[bottom_closest]:.2f}°")
    
    else:
        print("[ERROR] Invalid choice. Please try again.")

print("\n" + "="*70)
