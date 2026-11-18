import sys
import time
import machine
from machine import Pin, I2C

# Relay pin for thermography (GPIO15)
RELAY_PIN = 15
relay = machine.Pin(RELAY_PIN, machine.Pin.OUT)
relay.off()

# Stepper and encoder setup classes
# Encoder class
class AS5600Encoder:
    def __init__(self, i2c):
        """
        Class h=wwhich handless encoder output.
        """
        self.i2c = i2c
        self.addr = 0x36

    def read_angle(self):
        """
        Method which read raw output of the encoder and convert it to angle.
        """
        try:
            raw = self.i2c.readfrom_mem(self.addr, 0x0E, 2)
            angle = (raw[0] << 8 | raw[1]) & 0x0FFF
            return angle * 360.0 / 4096
        except:
            return -1

# Stepper motor class
class StepperMotor:
    def __init__(self, dir_pin, step_pin, ms1, ms2, ms3, invert_direction=False):
        """
        Class which handles stepper motor motion.

        dir_pin: indicates direction of rotation
        step_pin: forces stepper motor to make a step
        ms1,ms2,ms3: pins which allow to set up the stepper motor resolution
        invert_direction: if True, inverts the DIR pin logic (fixes wiring issues)
        """
        self.dir = Pin(dir_pin, Pin.OUT)
        self.step = Pin(step_pin, Pin.OUT)
        self.invert_direction = invert_direction
        # Setting up resolution of the stepper motors
        Pin(ms1, Pin.OUT).value(1)
        Pin(ms2, Pin.OUT).value(0)
        Pin(ms3, Pin.OUT).value(0)
        self.step_delay = 0.003  # Increased from 0.002 to reduce overshoot

    def move_steps(self, steps, direction):
        """
        Method which given number of steps and direction will rotate motor by this number and this direction.
        """
        # Apply direction inversion if needed
        actual_direction = (1 - direction) if self.invert_direction else direction
        self.dir.value(actual_direction)
        for _ in range(steps):
            self.step.value(1)
            time.sleep(self.step_delay)
            self.step.value(0)
            time.sleep(self.step_delay)

    def move_to_angle_with_encoder(self, target_angle, encoder, debug=False):
        """
        Fedback loop position control of the stepper motor.

        target angle: angle to which we want stepper motor to move.
        encoder: object of class encoder which handles the angle read out.
        debug: if True, print diagnostic information
        """
        max_attempts = 1000
        tolerance = 2  # Degrees - acceptable positioning error
        encoder_error_count = 0
        max_encoder_errors = 5
        stuck_counter = 0  # Track if motor is stuck
        last_position = -999
        
        if debug:
            print(f"[DEBUG] Moving to target: {target_angle:.2f}°")

        for attempt in range(max_attempts):
            current_angle = encoder.read_angle()
            
            # Check for encoder read errors
            if current_angle == -1:
                encoder_error_count += 1
                if debug:
                    print(f"[DEBUG] Encoder read error {encoder_error_count}/{max_encoder_errors}")
                if encoder_error_count >= max_encoder_errors:
                    print(f"[ERROR] Encoder failed after {max_encoder_errors} consecutive errors")
                    return False
                time.sleep(0.01)  # Brief delay before retry
                continue
            
            # Reset error count on successful read
            encoder_error_count = 0
            
            # Check if motor is stuck (position not changing)
            if abs(current_angle - last_position) < 0.5 and attempt > 10:
                stuck_counter += 1
                if stuck_counter > 50:  # Stuck for 50 consecutive attempts
                    print(f"[ERROR] Motor appears stuck at {current_angle:.2f}°, target {target_angle:.2f}°")
                    return False
            else:
                stuck_counter = 0
            last_position = current_angle
            
            # Calculate angular difference (shortest path)
            diff = (target_angle - current_angle + 360) % 360
            if diff > 180:
                diff -= 360

            if debug and attempt % 50 == 0:  # Print every 50th attempt (was 20)
                direction_str = "CW" if diff > 0 else "CCW"
                print(f"[DEBUG] Attempt {attempt}: Current={current_angle:.2f}°, Diff={diff:.2f}° ({direction_str})")

            if abs(diff) < tolerance:
                if debug:
                    print(f"[DEBUG] Target reached! Final angle: {current_angle:.2f}°")
                return True  # Success

            # Determine direction (will be inverted if invert_direction=True)
            direction = 1 if diff > 0 else 0
            
            # Adaptive step size - smaller steps to reduce overshoot
            if abs(diff) > 30:
                steps = 5  # Reduced from 10 to minimize overshoot
            elif abs(diff) > 10:
                steps = 2  # Reduced from 3
            else:
                steps = 1  # Single steps for fine adjustment
            
            # Extra debug output on first attempt to verify movement
            if debug and attempt == 0:
                dir_str = "CLOCKWISE" if direction == 1 else "COUNTER-CLOCKWISE"
                print(f"[DEBUG] First move: {steps} steps {dir_str} (DIR={direction})")
            
            self.move_steps(steps, direction)
            time.sleep(0.01)  # Small delay for encoder to settle
        
        # Failed to reach target
        final_angle = encoder.read_angle()
        print(f"[WARNING] Max attempts reached. Target={target_angle:.2f}°, Final={final_angle:.2f}°")
        return False


# Initialize I2C for encoders
print("[INFO] Initializing I2C buses and encoders...")
i2c_top = I2C(0, scl=Pin(21), sda=Pin(20))
i2c_bottom = I2C(1, scl=Pin(27), sda=Pin(26))

encoder_top = AS5600Encoder(i2c_top)
encoder_bottom = AS5600Encoder(i2c_bottom)

# Test encoder connections
print("[INFO] Testing encoder connections...")
test_top = encoder_top.read_angle()
test_bottom = encoder_bottom.read_angle()

if test_top == -1:
    print("[ERROR] TOP encoder not responding! Check I2C0 wiring (SDA=GPIO20, SCL=GPIO21)")
else:
    print(f"[INFO] TOP encoder OK - reading {test_top:.2f}°")

if test_bottom == -1:
    print("[ERROR] BOTTOM encoder not responding! Check I2C1 wiring (SDA=GPIO26, SCL=GPIO27)")
    print("[ERROR] This will cause motor vibration!")
else:
    print(f"[INFO] BOTTOM encoder OK - reading {test_bottom:.2f}°")



# Definining motor class objects
motor_top = StepperMotor(dir_pin=2, step_pin=3, ms1=6, ms2=7, ms3=8, invert_direction=False)
motor_bottom = StepperMotor(dir_pin=4, step_pin=5, ms1=10, ms2=11, ms3=12, invert_direction=True)

print("[INFO] Motors initialized:")
print("  TOP motor: Standard direction (invert_direction=False)")
print("  BOTTOM motor: Inverted direction (invert_direction=True)")


# Hard coded positions of the filters
top_angles = [344.88, 19.78, 55.68, 91.58, 127.58, 163.92, 198.98, 235.02]
bottom_angles = [116.89, 152.75, 183.87, 225.09, 264.64, 297.51, 334.6, 11.6]

# Function which handles motion of the motors to given positions of both motors
def move_filter_wheels_to(i, j, debug=False):
    target_top = top_angles[i]
    target_bottom = bottom_angles[j]

    if debug:
        print(f"[INFO] Moving to position [{i},{j}]: TOP={target_top:.2f}°, BOTTOM={target_bottom:.2f}°")
    
    # Move top motor first
    success_top = motor_top.move_to_angle_with_encoder(target_top, encoder_top, debug)
    if not success_top:
        print(f"[ERROR] Top motor failed to reach position {i}")
    
    time.sleep(0.5)
    
    # Move bottom motor
    success_bottom = motor_bottom.move_to_angle_with_encoder(target_bottom, encoder_bottom, debug)
    if not success_bottom:
        print(f"[ERROR] Bottom motor failed to reach position {j}")
    
    time.sleep(0.5)
    
    return success_top and success_bottom


# Calibration of the motor positions
print("[INFO] Starting initial calibration...")
print("[INFO] Reading current encoder positions...")
top_current = encoder_top.read_angle()
bottom_current = encoder_bottom.read_angle()
print(f"[INFO] TOP encoder: {top_current:.2f}°")
print(f"[INFO] BOTTOM encoder: {bottom_current:.2f}°")

time.sleep(0.5)
print("[INFO] Moving to home position [0,0]...")
success = move_filter_wheels_to(0, 0, debug=True)  # Enable debug for calibration
if success:
    print("[INFO] Calibration complete - motors at home position")
else:
    print("[WARNING] Calibration had issues - check encoder readings")
time.sleep(0.5)

# Main loop
while True:
    line = sys.stdin.readline()
    if not line:
        time.sleep(0.01)
        continue

    line = line.strip()
    if not line.startswith("ping"):
        continue

    parts = line.split()
    # Thermography mode command: ping <frame> <duration> <duration>
    if len(parts) == 4:
        try:
            frame_index = int(parts[1])
            duration_sec = int(parts[2])
        except:
            print("error")
            continue
        print(f"[INFO] Thermography ping received: frame {frame_index}, duration {duration_sec}s")
        relay.on()
        time.sleep(duration_sec)
        relay.off()
        print("pong")

    # Hyperspectral mode command: ping i_j
    elif len(parts) == 2 and '_' in parts[1]:
        try:
            i_str, j_str = parts[1].split('_')
            i = int(i_str)
            j = int(j_str)
            if i < 0 or i >= len(top_angles) or j < 0 or j >= len(bottom_angles):
                print("error")
                continue
        except:
            print("error")
            continue

        print(f"[INFO] Hyperspectral ping received: i={i}, j={j}")
        move_filter_wheels_to(i, j)
        print("pong")

    else:
        print("error")
