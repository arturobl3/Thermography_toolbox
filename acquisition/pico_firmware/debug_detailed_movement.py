"""
Detailed step-by-step movement debug - shows position after every few steps
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
        actual_direction = (1 - direction) if self.invert_direction else direction
        self.dir.value(actual_direction)
        for _ in range(steps):
            self.step.value(1)
            time.sleep(self.step_delay)
            self.step.value(0)
            time.sleep(self.step_delay)

    def move_to_angle_detailed(self, target_angle, encoder):
        """Move with detailed logging every 10 steps"""
        max_attempts = 200  # Reduced for testing
        tolerance = 5
        total_steps = 0
        
        print(f"\nMoving to target: {target_angle:.2f}°")
        print(f"{'Attempt':<8} {'Angle':<8} {'Diff':<8} {'Dir':<4} {'Steps':<6} {'Total Steps':<12}")
        print("-" * 60)
        
        for attempt in range(max_attempts):
            current_angle = encoder.read_angle()
            
            if current_angle == -1:
                print(f"Encoder error at attempt {attempt}")
                time.sleep(0.01)
                continue
            
            diff = (target_angle - current_angle + 360) % 360
            if diff > 180:
                diff -= 360
            
            if abs(diff) < tolerance:
                print(f"\n✓ Target reached! Final position: {current_angle:.2f}°")
                print(f"  Total steps taken: {total_steps}")
                print(f"  Final error: {diff:.2f}°")
                return True
            
            direction = 1 if diff > 0 else 0
            
            # Adaptive step size
            if abs(diff) > 20:
                steps = 10
            elif abs(diff) > 5:
                steps = 3
            else:
                steps = 1
            
            # Print every attempt
            dir_str = "CW" if direction == 1 else "CCW"
            print(f"{attempt:<8} {current_angle:>7.2f}° {diff:>7.2f}° {dir_str:<4} {steps:<6} {total_steps:<12}")
            
            self.move_steps(steps, direction)
            total_steps += steps
            time.sleep(0.01)
        
        final_angle = encoder.read_angle()
        final_diff = (target_angle - final_angle + 360) % 360
        if final_diff > 180:
            final_diff -= 360
        
        print(f"\n✗ Max attempts reached!")
        print(f"  Final position: {final_angle:.2f}°")
        print(f"  Target: {target_angle:.2f}°")
        print(f"  Error: {final_diff:.2f}°")
        print(f"  Total steps taken: {total_steps}")
        return False

# Initialize
print("="*60)
print("DETAILED MOVEMENT DEBUG")
print("="*60)

i2c_bottom = I2C(1, scl=Pin(27), sda=Pin(26))
encoder_bottom = AS5600Encoder(i2c_bottom)
motor_bottom = StepperMotor(dir_pin=4, step_pin=5, ms1=10, ms2=11, ms3=12, invert_direction=True)

start = encoder_bottom.read_angle()
print(f"\nStarting position: {start:.2f}°")

# Test moving to position [0,0] = 116.89°
print("\n" + "="*60)
print("TEST 1: Move to position [0,0] = 116.89°")
print("="*60)
motor_bottom.move_to_angle_detailed(116.89, encoder_bottom)

time.sleep(2)

# Test moving to position [0,1] = 152.75° from wherever we are
print("\n" + "="*60)
print("TEST 2: Move to position [0,1] = 152.75°")
print("="*60)
motor_bottom.move_to_angle_detailed(152.75, encoder_bottom)

print("\n" + "="*60)
print("TESTS COMPLETE")
print("="*60)
