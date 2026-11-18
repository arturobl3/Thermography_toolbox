"""
Diagnose Bottom Motor Stuck Issues

This script will test specific problematic positions with detailed output
to understand why the motor is getting stuck.
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
        self.total_steps_executed = 0

    def move_steps(self, steps, direction):
        actual_direction = (1 - direction) if self.invert_direction else direction
        self.dir.value(actual_direction)
        for _ in range(steps):
            self.step.value(1)
            time.sleep(self.step_delay)
            self.step.value(0)
            time.sleep(self.step_delay)
            self.total_steps_executed += 1

    def move_with_detailed_log(self, target_angle, encoder):
        """Move with detailed logging every 10 steps"""
        print(f"\n{'='*60}")
        print(f"Moving to target: {target_angle:.2f}°")
        print(f"{'='*60}")
        
        start_angle = encoder.read_angle()
        print(f"Start position: {start_angle:.2f}°")
        
        diff = (target_angle - start_angle + 360) % 360
        if diff > 180:
            diff -= 360
        
        expected_steps = abs(diff) / 0.9  # 0.9° per step in half-step mode
        print(f"Angular difference: {diff:+.2f}°")
        print(f"Expected steps: ~{expected_steps:.0f}")
        print(f"Direction: {'CW (1)' if diff > 0 else 'CCW (0)'}")
        
        direction = 1 if diff > 0 else 0
        self.total_steps_executed = 0
        
        print(f"\n{'Step':<8}{'Angle':<12}{'Diff':<12}{'Moved':<12}{'Status'}")
        print("-" * 60)
        
        max_steps = 250  # Test with 250 steps max
        for i in range(max_steps):
            # Take 10 steps
            self.move_steps(10, direction)
            time.sleep(0.02)  # Longer settle time
            
            current_angle = encoder.read_angle()
            if current_angle == -1:
                print(f"{self.total_steps_executed:<8}{'ERROR':<12}{'N/A':<12}{'N/A':<12}Encoder fail")
                return False
            
            remaining_diff = (target_angle - current_angle + 360) % 360
            if remaining_diff > 180:
                remaining_diff -= 360
            
            total_moved = (current_angle - start_angle + 360) % 360
            if total_moved > 180:
                total_moved -= 360
            
            status = ""
            if abs(remaining_diff) < 2:
                status = "TARGET!"
            elif abs(remaining_diff - diff) < 1:
                status = "NOT MOVING"
            elif (remaining_diff > 0) != (diff > 0):
                status = "OVERSHOOT"
            
            print(f"{self.total_steps_executed:<8}{current_angle:>6.2f}°{' '*4}{remaining_diff:>+6.2f}°{' '*4}{total_moved:>+6.2f}°{' '*4}{status}")
            
            if abs(remaining_diff) < 2:
                print(f"\n✓ Target reached after {self.total_steps_executed} steps")
                return True
            
            # Check if stuck (not moving)
            if i > 5 and abs(total_moved) < 5:
                print(f"\n✗ Motor appears STUCK - only moved {total_moved:.2f}° after {self.total_steps_executed} steps")
                print(f"  Expected to move: {diff:.2f}°")
                print(f"  Actual movement: {total_moved:.2f}°")
                print(f"  Motor efficacy: {(abs(total_moved) / self.total_steps_executed * 100):.2f}% of expected")
                return False
        
        final_angle = encoder.read_angle()
        final_diff = (target_angle - final_angle + 360) % 360
        if final_diff > 180:
            final_diff -= 360
        
        print(f"\n✗ Max steps reached")
        print(f"  Final position: {final_angle:.2f}°")
        print(f"  Still need to move: {final_diff:+.2f}°")
        return False


print("\n" + "="*70)
print("  BOTTOM MOTOR DETAILED DIAGNOSTIC")
print("="*70)

i2c_bottom = I2C(1, scl=Pin(27), sda=Pin(26))
encoder_bottom = AS5600Encoder(i2c_bottom)
motor_bottom = StepperMotor(dir_pin=4, step_pin=5, ms1=10, ms2=11, ms3=12, invert_direction=False)  # Changed to False

print("\n[INFO] Bottom motor initialized with NORMAL direction (not inverted)")

# Test the problematic positions from your output
test_positions = [
    (116.89, "[0,0] - Failed with 39° error"),
    (152.75, "[0,1] - Failed with 24° error"),
    (225.09, "[0,3] - Failed with 39° error"),
    (264.64, "[0,4] - Failed with 85° error"),
]

for target, description in test_positions:
    current = encoder_bottom.read_angle()
    print(f"\n\n{'='*70}")
    print(f"TEST: {description}")
    print(f"Current: {current:.2f}° → Target: {target:.2f}°")
    print(f"{'='*70}")
    
    input("Press ENTER to start movement (or Ctrl+C to skip)...")
    
    success = motor_bottom.move_with_detailed_log(target, encoder_bottom)
    
    if not success:
        print("\n[ANALYSIS]")
        print("  The motor is either:")
        print("  1. Mechanically binding at certain positions")
        print("  2. Losing steps due to insufficient current")
        print("  3. Encoder magnet misaligned at certain angles")
        print("  4. Motor driver overheating/thermal shutdown")
        
        cont = input("\nContinue to next test? (y/n): ").strip().lower()
        if cont != 'y':
            break
    
    time.sleep(2)

print("\n" + "="*70)
print("Diagnostic complete")
print("="*70)
