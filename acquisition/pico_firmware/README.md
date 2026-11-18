# Raspberry Pi Pico Controller for WIC Thermal Camera System

This directory contains the MicroPython firmware for the Raspberry Pi Pico that controls the dual filter wheel system and thermography relay for the WIC thermal camera.

## Overview

The Pico acts as a hardware controller that receives commands via serial communication (UART/USB) and performs two main functions:

1. **Hyperspectral Imaging**: Controls two stepper motors with absolute position encoders (AS5600) to position dual filter wheels for spectral filtering
2. **Thermography Mode**: Controls a relay to trigger external heating elements for thermal imaging sequences

## Project Structure

```
pico_code/
├── main.py                      # Main MicroPython firmware
├── README.md                    # This file
├── pyproject.toml              # Python project configuration
├── uv.lock                     # UV package manager lock file
└── pico_code.code-workspace    # VS Code workspace configuration
```

## Hardware Components

### Filter Wheel System (Hyperspectral Mode)
- **2x Stepper Motors**: Control rotation of top and bottom filter wheels
  - Top motor: DIR=GPIO2, STEP=GPIO3, MS pins=GPIO6/7/8
  - Bottom motor: DIR=GPIO4, STEP=GPIO5, MS pins=GPIO10/11/12
  - Microstep resolution: 1/2 step (MS1=1, MS2=0, MS3=0)
- **2x AS5600 Magnetic Encoders**: Absolute position feedback
  - Top encoder: I2C0 (SCL=GPIO21, SDA=GPIO20)
  - Bottom encoder: I2C1 (SCL=GPIO27, SDA=GPIO26)
- **8 filter positions per wheel**: Each wheel has 8 slots at specific angles

### Relay Control (Thermography Mode)
- **Relay**: GPIO15 - Controls external heating elements

## Filter Wheel Positions

The filter positions are hard-coded in `main.py` as angular positions in degrees (0-360°):

```python
top_angles = [344.88, 19.78, 55.68, 91.58, 127.58, 163.92, 198.98, 235.02]
bottom_angles = [107.18, 143.48, 178.48, 215.24, 254.79, 292.15, 327.25, 2.3]
```

**Note**: There is a +10° offset applied to bottom angles for alignment:
```python
target_bottom = bottom_angles[j] + 10  # small offset to align filters properly
```

### Adjusting Filter Positions

If an encoder malfunctions or positions drift, you can correct them by:

1. **Individual position correction**: Edit specific values in the `top_angles` or `bottom_angles` arrays
2. **Global offset**: Add/subtract a constant offset to all positions in one array
3. **Alignment offset**: Modify the `+10` offset applied to `target_bottom` in the `move_filter_wheels_to()` function

## Communication Protocol

The Pico listens for commands on stdin (USB serial) and responds with acknowledgments.

### Hyperspectral Mode Command
```
ping i_j\n
```
- `i`: Top wheel filter index (0-7)
- `j`: Bottom wheel filter index (0-7)
- **Response**: `pong` when both wheels reach their target positions
- **Error Response**: `error` if indices are out of range or parsing fails

**Example**:
```
ping 3_5
[INFO] Hyperspectral ping received: i=3, j=5
pong
```

### Thermography Mode Command
```
ping <frame_index> <duration_sec> <duration_sec>\n
```
- `frame_index`: Frame number (for logging)
- `duration_sec`: How long to activate the relay (in seconds)
- **Response**: `pong` after relay turns off
- **Error Response**: `error` if parsing fails

**Example**:
```
ping 42 5 5
[INFO] Thermography ping received: frame 42, duration 5s
pong
```

## Motor Control Algorithm

The stepper motors use closed-loop position control with encoder feedback:

1. Read current angle from AS5600 encoder
2. Calculate shortest angular distance to target (accounting for 0°/360° wraparound)
3. Move one microstep in the appropriate direction
4. Repeat until position is within 0.5° tolerance
5. Maximum 2000 attempts as safety stop

**Parameters**:
- Step delay: 2ms between steps
- Position tolerance: 0.5°
- Maximum attempts: 2000 steps
- Settling time: 0.5s after each motor movement

## How to Upload Changes to the Pico

After modifying `main.py`, you need to upload the updated firmware to the Pico. Here are four methods:

Address the board by its by-id symlink (`/dev/ttyACM*` numbering follows enumeration order, and the ODrive motor controller takes `ttyACM0`, pushing the Pico to `ttyACM1`). The same path is the default in `main_operation/picoserial.h`, overridable with `PICO_SERIAL_PORT`.

### Method 1: Using `mpremote` (Recommended)

Best for command-line workflows and automation.

```bash
# Install mpremote (first time only)
pip install mpremote

# Upload the updated main.py
PICO_PORT=/dev/serial/by-id/usb-MicroPython_Board_in_FS_mode_e6614104034a962a-if00
mpremote connect "$PICO_PORT" fs cp main.py :main.py

# Reset the Pico to run the new code
mpremote connect "$PICO_PORT" reset
```

### Method 2: Using `ampy`

Alternative command-line tool from Adafruit.

```bash
# Install ampy (first time only)
pip install adafruit-ampy

# Upload the file
ampy --port "$PICO_PORT" put main.py

# Manually reset the Pico (unplug/replug or press reset button)
```

### Method 3: Using Thonny IDE (GUI)

Good for beginners or interactive development.

1. Install Thonny: `sudo apt install thonny`
2. Open Thonny
3. Go to **Tools → Options → Interpreter**
4. Select "MicroPython (Raspberry Pi Pico)"
5. Select the port `/dev/serial/by-id/usb-MicroPython_Board_in_FS_mode_e6614104034a962a-if00`
6. Open your `main.py` in Thonny
7. Click **File → Save as...** and choose "Raspberry Pi Pico"
8. Save as `main.py`

### Method 4: Manual Copy via USB Mass Storage

No additional software needed, but requires physical access.

1. **Unplug the Pico from USB**
2. **Hold the BOOTSEL button** on the Pico while plugging it back into USB
3. The Pico will appear as a USB mass storage device named "RPI-RP2"
4. **Drag and drop** your `main.py` file onto the drive
5. The Pico will automatically reboot and run the new code

**Note**: This method requires the Pico to already have MicroPython installed. If starting fresh, you need to copy the MicroPython UF2 firmware first.

## Troubleshooting

### Encoder Not Responding
- Check I2C connections (SCL/SDA wiring)
- Verify encoder power supply (3.3V)
- Check encoder I2C address (should be 0x36)
- Method returns -1 if read fails

### Motor Not Moving
- Verify stepper driver power supply
- Check DIR and STEP pin connections
- Ensure MS1/MS2/MS3 pins are correctly set
- Verify motor wiring (coil A and coil B)

### Position Drift
- Encoders may need recalibration
- Edit `top_angles` or `bottom_angles` arrays in `main.py`
- Adjust the +10° offset for bottom wheel alignment if needed

### Serial Communication Issues
- Check USB connection (`ls /dev/ttyACM*`)
- Ensure no other program is using the serial port
- Verify baud rate matches (default is 115200 for Pico USB)
- Check for proper line endings (`\n`)

### Filter Wheels Not Reaching Position
- Increase `max_attempts` in `move_to_angle_with_encoder()` if motors are moving slowly
- Adjust `tolerance` if precision requirements are different
- Check for mechanical obstructions in filter wheel rotation
- Verify encoder magnet alignment and distance from sensor

## Calibration Procedure

On startup, the Pico automatically moves both filter wheels to position (0,0):

```python
time.sleep(0.5)
move_filter_wheels_to(0,0)  # Calibration to home position
time.sleep(0.5)
```

This ensures a known starting position before accepting commands.

## Integration with Main System

The C++ programs in the `main_operation` folder communicate with this Pico firmware:

- **hyperspectral.cpp**: Sends `ping i_j` commands to position filter wheels for each spectral band combination
- **thermography.cpp**: Sends thermography relay commands for thermal imaging sequences

The Pico waits for `pong` responses before proceeding to the next frame capture.

## Dependencies

The code uses MicroPython's built-in libraries:
- `machine`: Hardware control (Pin, I2C)
- `time`: Delays and timing
- `sys`: stdin for serial communication

No external MicroPython libraries are required.

## License

Part of the WIC Thermal Camera system.