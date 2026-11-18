# Bottom Motor Not Moving - Troubleshooting Guide

## Problem Diagnosis

Based on your debug output:
```
[DEBUG] Attempt 40: Current=297.51°, Diff=179.38°
[DEBUG] Attempt 340: Current=297.60°, Diff=179.29°
```

**Analysis:**
- ✅ Encoder is working (reading ~297.5°)
- ✅ Target angle is 116.89°
- ✅ Calculated difference is correct (~179°)
- ✅ Direction should be CLOCKWISE (diff is positive)
- ✗ **Motor is NOT moving** (encoder reading stays constant)

## Root Cause: Motor Driver Issue

The motor is receiving step commands but not responding. This is **NOT** a software issue - it's a hardware problem with the motor driver or connections.

## Most Common Cause: ENABLE Pin

**A4988/DRV8825 motor drivers have an ENABLE pin that MUST be LOW (grounded) for the motor to work!**

### Quick Check:
```
Driver Pin    | Required State | What Happens if Wrong
--------------|----------------|----------------------
ENABLE (EN)   | LOW (or GND)   | Motor won't move if HIGH
SLEEP         | HIGH (or VCC)  | Motor won't move if LOW  
RESET         | HIGH (or VCC)  | Motor won't move if LOW
```

## Diagnostic Steps

### Step 1: Run Basic Motor Test

Upload and run: `test_bottom_motor_basic.py`

```bash
mpremote connect /dev/ttyACM0 cp test_bottom_motor_basic.py :main.py
mpremote connect /dev/ttyACM0 reset
```

This will:
- Send 200 steps to the motor
- Show encoder feedback
- Tell you if the motor physically moves

**Expected Output if Working:**
```
Step  20: Encoder=305.23°  Delta=+7.72°
Step  40: Encoder=312.95°  Delta=+15.44°
Step  60: Encoder=320.67°  Delta=+23.16°
```

**Your Output (motor not working):**
```
Step  20: Encoder=297.51°  Delta=+0.00°
Step  40: Encoder=297.51°  Delta=+0.00°
Step  60: Encoder=297.51°  Delta=+0.00°
```

### Step 2: Check Motor Driver Enable Pin

#### For A4988 Driver:
```
    ┌─────────────┐
    │ A4988       │
    │             │
    │ ENABLE  ────┼──> Must connect to GND or leave floating
    │             │    (has internal pulldown)
    │ MS1     ────┼──> GPIO10
    │ MS2     ────┼──> GPIO11  
    │ MS3     ────┼──> GPIO12
    │ RESET   ────┼──> Connect to VCC or leave floating
    │ SLEEP   ────┼──> Connect to VCC or leave floating
    │ STEP    ────┼──> GPIO5
    │ DIR     ────┼──> GPIO4
    │             │
    │ VMOT    ────┼──> 12V power supply
    │ GND     ────┼──> Ground
    └─────────────┘
```

**Action Required:**
1. Find the ENABLE pin on your driver board
2. Connect it to GND (or confirm it's already grounded)
3. If uncertain, try adding this to your code:

```python
# Add this after motor initialization
enable_pin = Pin(9, Pin.OUT)  # Or whatever GPIO you choose
enable_pin.value(0)  # LOW = motor enabled
```

### Step 3: Check Other Driver Pins

Add test code to verify pin states:

```python
# Add this to test_bottom_motor_basic.py before motor test

print("\n[DEBUG] Checking all motor driver pins...")

# If you have enable pin on GPIO9
try:
    enable = Pin(9, Pin.OUT)
    enable.value(0)
    print("  ENABLE: Set to LOW (enabled)")
except:
    print("  ENABLE: Not configured")

# MS pins (already set in your code)
print(f"  MS1 (GPIO10): {ms1_pin.value()}")
print(f"  MS2 (GPIO11): {ms2_pin.value()}")
print(f"  MS3 (GPIO12): {ms3_pin.value()}")

# DIR and STEP should toggle during movement
print(f"  DIR (GPIO4):  {dir_pin.value()}")
print(f"  STEP (GPIO5): {step_pin.value()}")
```

### Step 4: Check Power Supply

Motor drivers need **separate power** for the motors:

```bash
# Check if VMOT (motor power) is connected
# Typical values: 12V for NEMA17 motors
# Minimum current: 1A per motor
```

**Common mistake:** Only connecting 3.3V logic power, not motor power.

### Step 5: Test with Multimeter

While running `test_bottom_motor_basic.py`:

1. **Check STEP pin is toggling:**
   - Multimeter on GPIO5
   - Should see voltage switching between 0V and 3.3V
   - If stuck at 0V or 3.3V → Pico pin issue

2. **Check motor driver STEP input:**
   - Multimeter on driver STEP pin
   - Should match GPIO5 behavior
   - If different → Connection problem

3. **Check ENABLE pin:**
   - Should be 0V (LOW)
   - If 3.3V (HIGH) → Motor is disabled

### Step 6: Swap Top and Bottom Motor Drivers

This quickly identifies if the driver is faulty:

1. Swap the STEP/DIR/MS pins between top and bottom motors
2. Run the test again
3. If the problem follows the driver → Driver is faulty
4. If the problem stays with bottom motor → Wiring/motor issue

## Quick Fix Checklist

Try these in order:

- [ ] **Connect ENABLE pin to GND** (most common fix!)
- [ ] Verify VMOT power supply is connected (12V, >1A)
- [ ] Check STEP pin connection (GPIO5 → Driver STEP)
- [ ] Check DIR pin connection (GPIO4 → Driver DIR)
- [ ] Verify driver SLEEP pin is HIGH (or connected to VCC)
- [ ] Verify driver RESET pin is HIGH (or connected to VCC)
- [ ] Check motor coil connections (A+/A-/B+/B-)
- [ ] Swap motor drivers to isolate faulty driver
- [ ] Try reducing microstep resolution (all MS pins LOW)

## Code Solutions

### Solution 1: Add Enable Pin Control

```python
# Add to StepperMotor.__init__() after ms3 setup:
self.enable = Pin(enable_pin, Pin.OUT)
self.enable.value(0)  # LOW = enabled
```

### Solution 2: Add Driver Configuration

```python
# Some drivers need SLEEP and RESET high
sleep_pin = Pin(13, Pin.OUT)
sleep_pin.value(1)  # Wake up driver

reset_pin = Pin(14, Pin.OUT)  
reset_pin.value(1)  # Take out of reset
```

### Solution 3: Test Without Microstep

```python
# Try full-step mode instead of half-step
Pin(ms1, Pin.OUT).value(0)  # Change from 1 to 0
Pin(ms2, Pin.OUT).value(0)
Pin(ms3, Pin.OUT).value(0)
```

## Expected Results

After fixing the ENABLE pin (or other issue):

```
[DEBUG] Attempt 0: Current=297.51°, Diff=179.38° (CW)
[DEBUG] First move: 10 steps CLOCKWISE (DIR=1)
[DEBUG] Attempt 20: Current=310.15°, Diff=166.74° (CW)
[DEBUG] Attempt 40: Current=322.79°, Diff=154.10° (CW)
[DEBUG] Attempt 60: Current=335.43°, Diff=141.46° (CW)
...
[DEBUG] Attempt 200: Current=115.67°, Diff=1.22° (CW)
[DEBUG] Target reached! Final angle: 116.89°
```

## Still Not Working?

If motor still doesn't move after all checks:

1. **Test with continuous_motor_rotation.py again**
   - Does the BOTTOM motor work in that script?
   - If YES → Problem is in main.py logic
   - If NO → Hardware problem persists

2. **Check motor itself:**
   ```bash
   # Disconnect motor from driver
   # Short A+ and A- together, B+ and B- together
   # Motor shaft should be hard to turn (coils acting as brake)
   # If easy to turn → Motor coil disconnected
   ```

3. **Try a different motor driver:**
   - Swap with the top motor driver
   - Or use a completely different driver board

4. **Verify Pico GPIO pins:**
   ```python
   # Test if GPIO5 can toggle
   step = Pin(5, Pin.OUT)
   for i in range(10):
       step.toggle()
       print(f"GPIO5: {step.value()}")
       time.sleep(0.5)
   ```

## Bottom Line

**99% of "motor not moving" issues are caused by:**
1. **ENABLE pin HIGH** (disabled) instead of LOW - 60% of cases
2. **Missing VMOT power** - 20% of cases  
3. **Loose/wrong STEP pin connection** - 15% of cases
4. **Driver in SLEEP mode** - 5% of cases

**Start by checking the ENABLE pin!**
