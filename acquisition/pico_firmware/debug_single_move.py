"""
Debug a single movement to see exactly what's happening
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
        print(f"  Moving {steps} steps, DIR pin = {actual_direction} (requested direction={direction}, invert={self.invert_direction})")
        for _ in range(steps):
            self.step.value(1)
            time.sleep(self.step_delay)
            self.step.value(0)
            time.sleep(self.step_delay)

# Initialize
print("Initializing bottom motor and encoder...")
i2c_bottom = I2C(1, scl=Pin(27), sda=Pin(26))
encoder_bottom = AS5600Encoder(i2c_bottom)
motor_bottom = StepperMotor(dir_pin=4, step_pin=5, ms1=10, ms2=11, ms3=12, invert_direction=True)

# Read starting position
start_angle = encoder_bottom.read_angle()
print(f"\nStarting position: {start_angle:.2f}°")

# Target position [0,0] = 116.89°
target = 116.89
print(f"Target position: {target:.2f}°")

# Calculate difference
diff = (target - start_angle + 360) % 360
if diff > 180:
    diff -= 360

print(f"Calculated diff: {diff:.2f}°")
print(f"Should move: {'CLOCKWISE (CW)' if diff > 0 else 'COUNTER-CLOCKWISE (CCW)'}")
direction = 1 if diff > 0 else 0
print(f"Direction value: {direction} (1=CW, 0=CCW)")

# Take 20 steps and see what happens
print(f"\nTaking 20 steps in direction {direction}...")
motor_bottom.move_steps(20, direction)

# Read new position
time.sleep(0.1)
new_angle = encoder_bottom.read_angle()
angle_change = new_angle - start_angle
if angle_change > 180:
    angle_change -= 360
elif angle_change < -180:
    angle_change += 360

print(f"\nAfter 20 steps:")
print(f"  New position: {new_angle:.2f}°")
print(f"  Change: {angle_change:.2f}° ({'CW' if angle_change > 0 else 'CCW'})")
print(f"  Expected: Move toward {target:.2f}° (diff should decrease)")

# Calculate new diff
new_diff = (target - new_angle + 360) % 360
if new_diff > 180:
    new_diff -= 360

print(f"  New diff to target: {new_diff:.2f}°")
print(f"  Original diff: {diff:.2f}°")

if abs(new_diff) < abs(diff):
    print("\n✓ Motor moving in CORRECT direction (getting closer to target)")
else:
    print("\n✗ Motor moving in WRONG direction (getting farther from target)")
    print("   Direction inversion is incorrect!")
