"""
Basic Bottom Motor Movement Test

This script tests if the bottom motor responds to step commands at all.
It will slowly rotate the motor while showing encoder feedback.

This helps diagnose:
1. Motor driver enable pin issues
2. STEP/DIR pin connection problems
3. Power supply issues
4. Motor wiring problems
"""

import time
from machine import Pin, I2C

print("\n" + "="*60)
print("  BOTTOM MOTOR BASIC TEST")
print("="*60)

# Initialize encoder to verify it's working
print("\n[1] Testing encoder...")
i2c_bottom = I2C(1, scl=Pin(27), sda=Pin(26))
try:
    raw = i2c_bottom.readfrom_mem(0x36, 0x0E, 2)
    angle = ((raw[0] << 8) | raw[1]) & 0x0FFF
    start_angle = angle * 360.0 / 4096
    print(f"    ✓ Encoder OK - Current angle: {start_angle:.2f}°")
except:
    print("    ✗ Encoder ERROR - Check I2C wiring!")
    print("    Cannot verify motor movement without encoder")
    start_angle = None

# Initialize motor pins
print("\n[2] Initializing motor pins...")
dir_pin = Pin(4, Pin.OUT)
step_pin = Pin(5, Pin.OUT)
ms1_pin = Pin(10, Pin.OUT)
ms2_pin = Pin(11, Pin.OUT)
ms3_pin = Pin(12, Pin.OUT)

# Set microstep mode (1/2 step)
ms1_pin.value(1)
ms2_pin.value(0)
ms3_pin.value(0)

step_pin.value(0)
print("    ✓ Motor pins initialized")
print("    - DIR: GPIO4")
print("    - STEP: GPIO5")
print("    - Microstep: 1/2 (MS1=1, MS2=0, MS3=0)")

# Check if there's an enable pin that might be disabled
print("\n[3] Motor driver enable pin check:")
print("    If your driver has an ENABLE pin, it must be:")
print("    - Connected and pulled LOW (enabled)")
print("    - Or left floating if it has internal pulldown")
print("    Common enable pins: GPIO9, GPIO13, or connected to GND")

input("\nPress ENTER to start motor test...")

# Test parameters
steps_total = 200  # Should be ~180 degrees in half-step mode
step_delay = 0.003  # 3ms between steps (slower for observation)

print("\n" + "-"*60)
print("Testing CLOCKWISE rotation (direction=1)...")
print("-"*60)

dir_pin.value(1)  # Clockwise
time.sleep(0.01)

for i in range(steps_total):
    step_pin.value(1)
    time.sleep(step_delay)
    step_pin.value(0)
    time.sleep(step_delay)
    
    # Print progress every 20 steps
    if (i + 1) % 20 == 0:
        if start_angle is not None:
            try:
                raw = i2c_bottom.readfrom_mem(0x36, 0x0E, 2)
                angle = ((raw[0] << 8) | raw[1]) & 0x0FFF
                current_angle = angle * 360.0 / 4096
                delta = (current_angle - start_angle + 360) % 360
                if delta > 180:
                    delta -= 360
                print(f"  Step {i+1:3d}: Encoder={current_angle:6.2f}°  Delta={delta:+6.2f}°")
            except:
                print(f"  Step {i+1:3d}: Encoder read error")
        else:
            print(f"  Step {i+1:3d}: (no encoder feedback)")

print("\n✓ Clockwise test complete")
time.sleep(1)

print("\n" + "-"*60)
print("Testing COUNTER-CLOCKWISE rotation (direction=0)...")
print("-"*60)

dir_pin.value(0)  # Counter-clockwise
time.sleep(0.01)

for i in range(steps_total):
    step_pin.value(1)
    time.sleep(step_delay)
    step_pin.value(0)
    time.sleep(step_delay)
    
    if (i + 1) % 20 == 0:
        if start_angle is not None:
            try:
                raw = i2c_bottom.readfrom_mem(0x36, 0x0E, 2)
                angle = ((raw[0] << 8) | raw[1]) & 0x0FFF
                current_angle = angle * 360.0 / 4096
                delta = (current_angle - start_angle + 360) % 360
                if delta > 180:
                    delta -= 360
                print(f"  Step {i+1:3d}: Encoder={current_angle:6.2f}°  Delta={delta:+6.2f}°")
            except:
                print(f"  Step {i+1:3d}: Encoder read error")
        else:
            print(f"  Step {i+1:3d}: (no encoder feedback)")

print("\n✓ Counter-clockwise test complete")

if start_angle is not None:
    try:
        raw = i2c_bottom.readfrom_mem(0x36, 0x0E, 2)
        angle = ((raw[0] << 8) | raw[1]) & 0x0FFF
        final_angle = angle * 360.0 / 4096
        total_delta = (final_angle - start_angle + 360) % 360
        if total_delta > 180:
            total_delta -= 360
        
        print("\n" + "="*60)
        print("RESULTS:")
        print("="*60)
        print(f"  Start angle:  {start_angle:.2f}°")
        print(f"  Final angle:  {final_angle:.2f}°")
        print(f"  Net movement: {total_delta:+.2f}°")
        print(f"  Total steps:  {steps_total * 2}")
        
        if abs(total_delta) < 5:
            print("\n✗ MOTOR NOT MOVING!")
            print("\nPossible causes:")
            print("  1. Motor driver ENABLE pin is HIGH (disabled)")
            print("     → Check if there's an EN/ENABLE pin and pull it LOW")
            print("  2. Motor driver not powered")
            print("     → Verify VMOT power supply (typically 12V)")
            print("  3. STEP pin not connected properly")
            print("     → Check GPIO5 connection to motor driver STEP input")
            print("  4. Motor driver in sleep/reset mode")
            print("     → Check SLEEP/RESET pins (should be HIGH)")
            print("  5. Motor coils disconnected")
            print("     → Verify A+, A-, B+, B- connections")
        elif abs(total_delta) < 90:
            print("\n⚠ Motor moving but less than expected")
            print("  Expected: ~±0° (should return to start)")
            print("  This could indicate:")
            print("  - Microstep settings incorrect")
            print("  - Motor skipping steps (insufficient current)")
            print("  - Mechanical binding")
        else:
            print("\n✓ Motor appears to be working!")
            print("  The motor is responding to step commands.")
            print("  If main.py still has issues, the problem is likely")
            print("  in the control logic or timing, not the hardware.")
    except:
        print("\nCouldn't read final encoder position")
else:
    print("\n" + "="*60)
    print("Test complete (no encoder feedback available)")
    print("="*60)
    print("\nDid you observe the motor shaft rotating?")
    print("  YES → Motor hardware OK, check control logic")
    print("  NO  → Motor hardware problem, check wiring/power")

print("\n" + "="*60)
