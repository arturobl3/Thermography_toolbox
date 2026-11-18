"""
Test moving BOTTOM motor to position [0,0] = 116.89° with full debug output
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
        print(f"    move_steps: direction={direction}, invert={self.invert_direction}, actual_dir={actual_direction}")
        self.dir.value(actual_direction)
        for _ in range(steps):
            self.step.value(1)
            time.sleep(self.step_delay)
            self.step.value(0)
            time.sleep(self.step_delay)

    def move_to_angle(self, target_angle, encoder):
        tolerance = 5
        max_attempts = 100  # Limited for testing
        
        print(f"\nMoving to {target_angle:.2f}°")
        print(f"{'Attempt':<8} {'Current':<10} {'Target':<10} {'Diff':<10} {'Dir':<5} {'Steps':<6}")
        print("-" * 60)
        
        for attempt in range(max_attempts):
            current_angle = encoder.read_angle()
            
            if current_angle == -1:
                print(f"Encoder error at attempt {attempt}")
                continue
            
            diff = (target_angle - current_angle + 360) % 360
            if diff > 180:
                diff -= 360
            
            if abs(diff) < tolerance:
                print(f"\n✓ Reached target! Final: {current_angle:.2f}°, Error: {diff:.2f}°")
                return True
            
            direction = 1 if diff > 0 else 0
            
            if abs(diff) > 20:
                steps = 10
            elif abs(diff) > 5:
                steps = 3
            else:
                steps = 1
            
            dir_str = "CW" if direction == 1 else "CCW"
            print(f"{attempt:<8} {current_angle:<10.2f} {target_angle:<10.2f} {diff:<10.2f} {dir_str:<5} {steps:<6}")
            
            self.move_steps(steps, direction)
            time.sleep(0.01)
        
        final = encoder.read_angle()
        print(f"\n✗ Failed! Final: {final:.2f}°, Target: {target_angle:.2f}°")
        return False

# Initialize
print("="*60)
print("SINGLE POSITION TEST: BOTTOM motor to 116.89°")
print("="*60)

i2c_bottom = I2C(1, scl=Pin(27), sda=Pin(26))
encoder_bottom = AS5600Encoder(i2c_bottom)
motor_bottom = StepperMotor(dir_pin=4, step_pin=5, ms1=10, ms2=11, ms3=12, invert_direction=True)

start = encoder_bottom.read_angle()
print(f"\nStarting position: {start:.2f}°")
print(f"Target position: 116.89°")
print(f"Motor config: invert_direction=True")

input("\nPress ENTER to start movement...")

success = motor_bottom.move_to_angle(116.89, encoder_bottom)

if success:
    print("\n✓ SUCCESS")
else:
    print("\n✗ FAILED")

print("\n" + "="*60)
