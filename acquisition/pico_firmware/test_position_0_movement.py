
"""
Test moving bottom motor from current position to target position 0

This replicates exactly what main.py is trying to do.
"""

import time
from machine import Pin, I2C

class AS5600Encoder:
    def __init__(self, i2c):
        self.i2c = i2c
        self.addr = 0x36

    def read_angle(self):
        try:
            raw = self.i2c.readfrom_mem(self.addr, 0x0E, 2)
            angle = (raw[0] << 8 | raw[1]) & 0x0FFF
            return angle * 360.0 / 4096
        except:
            return -1

class StepperMotor:
    def __init__(self, dir_pin, step_pin, ms1, ms2, ms3, invert_direction=False):
        self.dir = Pin(dir_pin, Pin.OUT)
        self.step = Pin(step_pin, Pin.OUT)
        self.invert_direction = invert_direction
        Pin(ms1, Pin.OUT).value(1)
        Pin(ms2, Pin.OUT).value(0)
        Pin(ms3, Pin.OUT).value(0)
        self.step_delay = 0.002

    def move_steps(self, steps, direction):
        # Apply direction inversion if needed
        actual_direction = (1 - direction) if self.invert_direction else direction
        self.dir.value(actual_direction)
        for _ in range(steps):
            self.step.value(1)
            time.sleep(self.step_delay)
            self.step.value(0)
            time.sleep(self.step_delay)

    def move_to_angle_with_encoder(self, target_angle, encoder, debug=False):
        max_attempts = 500
        tolerance = 2
        encoder_error_count = 0
        max_encoder_errors = 5
        
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
            
            diff = (target_angle - current_angle + 360) % 360
            if diff > 180:
                diff -= 360

            if debug and attempt % 20 == 0:
                direction_str = "CW" if diff > 0 else "CCW"
                print(f"[DEBUG] Attempt {attempt}: Current={current_angle:.2f}°, Diff={diff:.2f}° ({direction_str})")

            if abs(diff) < tolerance:
                if debug:
                    print(f"[DEBUG] Target reached! Final angle: {current_angle:.2f}°")
                return True

            direction = 1 if diff > 0 else 0
            
            if abs(diff) > 20:
                steps = 10
            elif abs(diff) > 5:
                steps = 3
            else:
                steps = 1
            
            if debug and attempt == 0:
                dir_str = "CLOCKWISE" if direction == 1 else "COUNTER-CLOCKWISE"
                print(f"[DEBUG] First move: {steps} steps {dir_str} (DIR={direction})")
                print(f"[DEBUG] STEP pin is GPIO5, DIR pin is GPIO4")
            
            # EXTRA DEBUG: Show we're actually calling move_steps
            if debug and attempt < 3:
                print(f"[DEBUG] Calling move_steps({steps}, {direction})")
            
            self.move_steps(steps, direction)
            time.sleep(0.01)
        
        final_angle = encoder.read_angle()
        print(f"[WARNING] Max attempts reached. Target={target_angle:.2f}°, Final={final_angle:.2f}°")
        return False


print("\n" + "="*60)
print("  TEST: Move bottom motor from current position to 116.89°")
print("="*60)

i2c_bottom = I2C(1, scl=Pin(27), sda=Pin(26))
encoder_bottom = AS5600Encoder(i2c_bottom)
motor_bottom = StepperMotor(dir_pin=4, step_pin=5, ms1=10, ms2=11, ms3=12, invert_direction=True)

print("[INFO] Bottom motor initialized with INVERTED direction")
print("      (compensates for reversed wiring)")

current = encoder_bottom.read_angle()
print(f"\n[INFO] Current position: {current:.2f}°")
print(f"[INFO] Target position: 116.89°")

target = 116.89
diff = (target - current + 360) % 360
if diff > 180:
    diff -= 360

print(f"[INFO] Difference: {diff:.2f}° ({'CW' if diff > 0 else 'CCW'})")
print(f"[INFO] Expected steps: ~{abs(diff) / 0.9:.0f} (at 0.9° per step in half-step mode)")

input("\nPress ENTER to start movement...")

print("\n" + "-"*60)
success = motor_bottom.move_to_angle_with_encoder(116.89, encoder_bottom, debug=True)
print("-"*60)

if success:
    print("\n✓ SUCCESS: Motor reached target position")
else:
    print("\n✗ FAILED: Motor did not reach target")
    print("\nPossible issues:")
    print("  - Motor needs more steps (increase max_attempts)")
    print("  - Steps are too small (mechanical binding?)")
    print("  - Direction is wrong (check motor wiring)")

final = encoder_bottom.read_angle()
actual_movement = (final - current + 360) % 360
if actual_movement > 180:
    actual_movement -= 360

print(f"\n[INFO] Final position: {final:.2f}°")
print(f"[INFO] Actual movement: {actual_movement:+.2f}°")
print(f"[INFO] Expected movement: {diff:+.2f}°")
