# Motor Vibration Debug Guide

## Problem
The bottom stepper motor vibrates instead of moving to position during the initial `move_filter_wheels_to(0,0)` call.

## Root Causes Identified

### 1. **Encoder Read Errors Not Handled**
If `encoder.read_angle()` returns `-1` (indicating I2C communication failure), the control loop continues trying to move to `-1` degrees, causing continuous oscillation.

### 2. **Single-Step Movements Too Small**
Moving 1 step at a time (0.9° per step in half-step mode) causes:
- Very slow convergence
- Potential for oscillation around the target
- No progress if encoder has noise or quantization

### 3. **No Diagnostic Output**
Without debug information, it's impossible to see:
- What the encoder is reading
- Whether I2C communication is working
- How far from target the motor actually is

## Fixes Applied

### 1. **Encoder Error Detection**
```python
if current_angle == -1:
    encoder_error_count += 1
    if encoder_error_count >= max_encoder_errors:
        print(f"[ERROR] Encoder failed after {max_encoder_errors} consecutive errors")
        return False
```

### 2. **Adaptive Step Size**
```python
if abs(diff) > 20:
    steps = 10  # Large steps when far away
elif abs(diff) > 5:
    steps = 3   # Medium steps when getting close
else:
    steps = 1   # Single steps for fine adjustment
```

### 3. **Comprehensive Debug Output**
- Encoder test at startup
- Current position readings
- Movement progress tracking
- Success/failure reporting

## Debugging Steps

### Step 1: Run Encoder Debug Script
```bash
# Upload and run the encoder diagnostic
python debug_encoder_positions.py
```

**Expected output:**
```
TOP encoder (I2C0): ✓ Connected
BOTTOM encoder (I2C1): ✓ Connected
```

**If BOTTOM encoder shows error:**
- Check I2C1 wiring:
  - SDA = GPIO 26
  - SCL = GPIO 27
- Verify encoder power (3.3V)
- Check encoder I2C address (should be 0x36)
- Test with multimeter for continuity

### Step 2: Run Updated main.py
The updated script will now show:
```
[INFO] Initializing I2C buses and encoders...
[INFO] Testing encoder connections...
[INFO] TOP encoder OK - reading 123.45°
[INFO] BOTTOM encoder OK - reading 234.56°
[INFO] Starting initial calibration...
[DEBUG] Moving to target: 344.88°
[DEBUG] Attempt 0: Current=123.45°, Diff=-138.57°
[DEBUG] Target reached! Final angle: 344.88°
[DEBUG] Moving to target: 116.89°
[DEBUG] Attempt 0: Current=234.56°, Diff=-117.67°
[DEBUG] Target reached! Final angle: 116.89°
[INFO] Calibration complete - motors at home position
```

### Step 3: Identify the Issue

**If BOTTOM encoder shows -1:**
```
[ERROR] BOTTOM encoder not responding! Check I2C1 wiring (SDA=GPIO26, SCL=GPIO27)
[ERROR] This will cause motor vibration!
```
→ **I2C wiring problem**

**If encoder reads but motor still vibrates:**
```
[DEBUG] Attempt 0: Current=116.50°, Diff=0.39°
[DEBUG] Attempt 20: Current=116.80°, Diff=0.09°
[DEBUG] Attempt 40: Current=116.50°, Diff=0.39°
```
→ **Oscillation around target** - increase tolerance or reduce step delay

**If encoder reads but doesn't change:**
```
[DEBUG] Attempt 0: Current=234.56°, Diff=-117.67°
[DEBUG] Attempt 20: Current=234.56°, Diff=-117.67°
[DEBUG] Attempt 40: Current=234.56°, Diff=-117.67°
```
→ **Motor not moving** - check motor driver wiring, power, or enable pin

## Hardware Checklist

### Bottom Motor (the vibrating one)
- [ ] Motor driver power supply connected
- [ ] Motor coil wiring correct (A+, A-, B+, B-)
- [ ] STEP pin connection (GPIO 5)
- [ ] DIR pin connection (GPIO 4)
- [ ] MS1/MS2/MS3 connections (GPIO 10, 11, 12)
- [ ] Motor driver enable pin (if present)

### Bottom Encoder
- [ ] I2C SDA connection (GPIO 26)
- [ ] I2C SCL connection (GPIO 27)
- [ ] Encoder 3.3V power
- [ ] Encoder GND connection
- [ ] Magnet properly aligned with encoder

## Quick Test Commands

### Test encoder only:
```python
from machine import Pin, I2C
i2c = I2C(1, scl=Pin(27), sda=Pin(26))
raw = i2c.readfrom_mem(0x36, 0x0E, 2)
angle = ((raw[0] << 8) | raw[1]) & 0x0FFF
print(f"Angle: {angle * 360.0 / 4096:.2f}°")
```

### Test motor only (no encoder):
```python
from machine import Pin
import time
step = Pin(5, Pin.OUT)
dir = Pin(4, Pin.OUT)
dir.value(1)
for _ in range(100):
    step.value(1)
    time.sleep(0.002)
    step.value(0)
    time.sleep(0.002)
```

## Common Issues and Solutions

| Symptom | Likely Cause | Solution |
|---------|-------------|----------|
| Motor vibrates/buzzes | Encoder returning -1 | Check I2C wiring |
| Motor moves then reverses | Oscillation around target | Increase tolerance to 3-5° |
| Motor doesn't move at all | Motor driver issue | Check power, wiring, enable pin |
| Encoder reads but doesn't change | Magnet misalignment | Adjust magnet position |
| Random encoder values | Poor I2C connection | Check wire quality, add pullups |

## Files Modified

1. **main.py** - Added:
   - Encoder error handling
   - Adaptive step sizing
   - Debug output
   - Startup diagnostics
   
2. **debug_encoder_positions.py** (NEW) - Tool to:
   - Test encoder I2C communication
   - Display real-time position readings
   - Identify wiring issues

## Next Steps

1. Upload the updated `main.py` to your Pico
2. Run it and observe the debug output
3. If encoder shows errors, run `debug_encoder_positions.py`
4. Check the specific error messages and follow the troubleshooting steps above
