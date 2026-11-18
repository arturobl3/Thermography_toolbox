"""
Final diagnostic: Test if encoder angle increases with DIR=1 or DIR=0
This will tell us the correct direction logic for the feedback loop
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
        self.dir.value(direction)
        for _ in range(steps):
            self.step.value(1)
            time.sleep(self.step_delay)
            self.step.value(0)
            time.sleep(self.step_delay)

print("="*70)
print("ENCODER-MOTOR CORRELATION TEST")
print("="*70)
print("\nThis test determines the correct direction logic for feedback control")
print("\nPress ENTER to start the test...")
input()

# Initialize BOTTOM motor (the problematic one)
i2c_bottom = I2C(1, scl=Pin(27), sda=Pin(26))
encoder_bottom = AS5600Encoder(i2c_bottom)
motor_bottom = StepperMotor(dir_pin=4, step_pin=5, ms1=10, ms2=11, ms3=12)

start_angle = encoder_bottom.read_angle()
print(f"\nStarting angle: {start_angle:.2f}°")

# Test DIR=1
print("\n--- Test 1: DIR=1 for 50 steps ---")
motor_bottom.move_steps(50, 1)
time.sleep(0.1)
angle_after_dir1 = encoder_bottom.read_angle()

# Calculate change (handle wraparound)
change1 = angle_after_dir1 - start_angle
if change1 > 180:
    change1 -= 360
elif change1 < -180:
    change1 += 360

print(f"Angle after DIR=1: {angle_after_dir1:.2f}°")
print(f"Change: {change1:+.2f}°")

if change1 > 0:
    print("→ DIR=1 makes encoder angle INCREASE (positive diff)")
    print("→ For feedback: When diff > 0 (need to increase angle), use direction=1")
    correct_logic = "direction = 1 if diff > 0 else 0"
else:
    print("→ DIR=1 makes encoder angle DECREASE (negative diff)")
    print("→ For feedback: When diff > 0 (need to increase angle), use direction=0")
    correct_logic = "direction = 0 if diff > 0 else 1"

print("\n" + "="*70)
print("CORRECT DIRECTION LOGIC FOR BOTTOM MOTOR:")
print(f"  {correct_logic}")
print("="*70)

# Now test TOP motor
print("\n\n")
print("="*70)
print("TOP MOTOR TEST")
print("="*70)

i2c_top = I2C(0, scl=Pin(21), sda=Pin(20))
encoder_top = AS5600Encoder(i2c_top)
motor_top = StepperMotor(dir_pin=2, step_pin=3, ms1=6, ms2=7, ms3=8)

start_angle_top = encoder_top.read_angle()
print(f"\nStarting angle: {start_angle_top:.2f}°")

print("\n--- Test 1: DIR=1 for 50 steps ---")
motor_top.move_steps(50, 1)
time.sleep(0.1)
angle_after_dir1_top = encoder_top.read_angle()

change1_top = angle_after_dir1_top - start_angle_top
if change1_top > 180:
    change1_top -= 360
elif change1_top < -180:
    change1_top += 360

print(f"Angle after DIR=1: {angle_after_dir1_top:.2f}°")
print(f"Change: {change1_top:+.2f}°")

if change1_top > 0:
    print("→ DIR=1 makes encoder angle INCREASE (positive diff)")
    print("→ For feedback: When diff > 0 (need to increase angle), use direction=1")
    correct_logic_top = "direction = 1 if diff > 0 else 0"
else:
    print("→ DIR=1 makes encoder angle DECREASE (negative diff)")
    print("→ For feedback: When diff > 0 (need to increase angle), use direction=0")
    correct_logic_top = "direction = 0 if diff > 0 else 1"

print("\n" + "="*70)
print("CORRECT DIRECTION LOGIC FOR TOP MOTOR:")
print(f"  {correct_logic_top}")
print("="*70)

print("\n\n")
print("="*70)
print("FINAL RECOMMENDATION:")
print("="*70)
if correct_logic == correct_logic_top:
    print(f"Both motors use: {correct_logic}")
    print("\nUse this logic in move_to_angle_with_encoder() for both motors")
else:
    print("Motors require DIFFERENT direction logic!")
    print(f"  TOP motor:    {correct_logic_top}")
    print(f"  BOTTOM motor: {correct_logic}")
    print("\nSolution: Create separate move methods or use invert_direction parameter")
print("="*70)
