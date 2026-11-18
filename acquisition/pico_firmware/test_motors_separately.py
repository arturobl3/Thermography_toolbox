"""
Test TOP and BOTTOM motors separately to determine correct direction logic for each
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
    def __init__(self, dir_pin, step_pin, ms1, ms2, ms3):
        self.dir = Pin(dir_pin, Pin.OUT)
        self.step = Pin(step_pin, Pin.OUT)
        Pin(ms1, Pin.OUT).value(1)
        Pin(ms2, Pin.OUT).value(0)
        Pin(ms3, Pin.OUT).value(0)
        self.step_delay = 0.002

    def move_steps(self, steps, direction):
        """direction: 0 or 1 for DIR pin"""
        self.dir.value(direction)
        for _ in range(steps):
            self.step.value(1)
            time.sleep(self.step_delay)
            self.step.value(0)
            time.sleep(self.step_delay)

# Initialize
print("="*60)
print("MOTOR DIRECTION TEST")
print("="*60)

i2c_top = I2C(0, scl=Pin(21), sda=Pin(20))
i2c_bottom = I2C(1, scl=Pin(27), sda=Pin(26))

encoder_top = AS5600Encoder(i2c_top)
encoder_bottom = AS5600Encoder(i2c_bottom)

motor_top = StepperMotor(dir_pin=2, step_pin=3, ms1=6, ms2=7, ms3=8)
motor_bottom = StepperMotor(dir_pin=4, step_pin=5, ms1=10, ms2=11, ms3=12)

# Test TOP motor
print("\n" + "="*60)
print("TOP MOTOR TEST")
print("="*60)

start_top = encoder_top.read_angle()
print(f"Starting position: {start_top:.2f}°")

print("\nTest 1: DIR=1, 30 steps")
motor_top.move_steps(30, 1)
time.sleep(0.1)
pos1 = encoder_top.read_angle()
change1 = pos1 - start_top
if change1 > 180: change1 -= 360
elif change1 < -180: change1 += 360
print(f"  Position: {pos1:.2f}° (change: {change1:+.2f}°)")
print(f"  Result: DIR=1 causes {'CW' if change1 > 0 else 'CCW'} rotation")

print("\nTest 2: DIR=0, 30 steps")
motor_top.move_steps(30, 0)
time.sleep(0.1)
pos2 = encoder_top.read_angle()
change2 = pos2 - pos1
if change2 > 180: change2 -= 360
elif change2 < -180: change2 += 360
print(f"  Position: {pos2:.2f}° (change: {change2:+.2f}°)")
print(f"  Result: DIR=0 causes {'CW' if change2 > 0 else 'CCW'} rotation")

# Conclusion for TOP
print("\nTOP MOTOR WIRING:")
if change1 > 0 and change2 < 0:
    print("  DIR=1 → CW, DIR=0 → CCW (STANDARD)")
    print("  For algorithm: use direction = 1 if diff > 0 else 0")
elif change1 < 0 and change2 > 0:
    print("  DIR=1 → CCW, DIR=0 → CW (INVERTED)")
    print("  For algorithm: use direction = 0 if diff > 0 else 1")
else:
    print("  UNCLEAR - motors may not be moving correctly")

time.sleep(2)

# Test BOTTOM motor
print("\n" + "="*60)
print("BOTTOM MOTOR TEST")
print("="*60)

start_bottom = encoder_bottom.read_angle()
print(f"Starting position: {start_bottom:.2f}°")

print("\nTest 1: DIR=1, 30 steps")
motor_bottom.move_steps(30, 1)
time.sleep(0.1)
pos1 = encoder_bottom.read_angle()
change1 = pos1 - start_bottom
if change1 > 180: change1 -= 360
elif change1 < -180: change1 += 360
print(f"  Position: {pos1:.2f}° (change: {change1:+.2f}°)")
print(f"  Result: DIR=1 causes {'CW' if change1 > 0 else 'CCW'} rotation")

print("\nTest 2: DIR=0, 30 steps")
motor_bottom.move_steps(30, 0)
time.sleep(0.1)
pos2 = encoder_bottom.read_angle()
change2 = pos2 - pos1
if change2 > 180: change2 -= 360
elif change2 < -180: change2 += 360
print(f"  Position: {pos2:.2f}° (change: {change2:+.2f}°)")
print(f"  Result: DIR=0 causes {'CW' if change2 > 0 else 'CCW'} rotation")

# Conclusion for BOTTOM
print("\nBOTTOM MOTOR WIRING:")
if change1 > 0 and change2 < 0:
    print("  DIR=1 → CW, DIR=0 → CCW (STANDARD)")
    print("  For algorithm: use direction = 1 if diff > 0 else 0")
elif change1 < 0 and change2 > 0:
    print("  DIR=1 → CCW, DIR=0 → CW (INVERTED)")
    print("  For algorithm: use direction = 0 if diff > 0 else 1")
else:
    print("  UNCLEAR - motors may not be moving correctly")

print("\n" + "="*60)
print("RECOMMENDATION:")
print("="*60)
print("Update move_to_angle_with_encoder() to use motor-specific")
print("direction logic, or set invert_direction parameter correctly")
print("for each motor based on the results above.")
print("="*60)
