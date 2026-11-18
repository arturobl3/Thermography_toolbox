"""
Continuous Motor Rotation Test Script

This script continuously rotates both stepper motors (top and bottom) at a slow,
steady pace to help diagnose electrical connection issues.

Use this to:
1. Verify motor driver connections
2. Check stepper motor wiring
3. Diagnose power supply issues
4. Test DIR and STEP signal integrity
5. Confirm microstep settings are correct

Instructions:
1. Upload this file to the Pico as main.py (or run it in Thonny)
2. Observe which motor(s) are rotating
3. Listen for clicking/buzzing sounds that indicate connection issues
4. Check LED indicators on motor drivers
5. Verify motor vibrations/movement

Press Ctrl+C to exit.
"""

import time
from machine import Pin

# Motor class
class StepperMotor:
    def __init__(self, dir_pin, step_pin, ms1_pin, ms2_pin, ms3_pin, name="Motor"):
        """
        Class which handles stepper motor control.
        
        Args:
            dir_pin: GPIO pin for direction control
            step_pin: GPIO pin for step pulses
            ms1_pin, ms2_pin, ms3_pin: Microstep resolution pins
            name: Display name for this motor
        """
        self.dir = Pin(dir_pin, Pin.OUT)
        self.step = Pin(step_pin, Pin.OUT)
        self.ms1 = Pin(ms1_pin, Pin.OUT)
        self.ms2 = Pin(ms2_pin, Pin.OUT)
        self.ms3 = Pin(ms3_pin, Pin.OUT)
        self.name = name
        
        # Set microstep resolution (1/2 step)
        self.ms1.value(1)
        self.ms2.value(0)
        self.ms3.value(0)
        
        # Initialize step pin low
        self.step.value(0)
        
        print(f"✓ {name} initialized:")
        print(f"    DIR=GPIO{dir_pin}, STEP=GPIO{step_pin}")
        print(f"    MS pins: GPIO{ms1_pin}/GPIO{ms2_pin}/GPIO{ms3_pin}")
        print(f"    Microstep: 1/2 (MS1=1, MS2=0, MS3=0)")

    def step_once(self, direction=1, delay_ms=5):
        """
        Execute a single step pulse.
        
        Args:
            direction: 1 for clockwise, 0 for counter-clockwise
            delay_ms: Delay between steps in milliseconds
        """
        self.dir.value(direction)
        time.sleep_ms(1)  # Direction setup time
        
        self.step.value(1)
        time.sleep_ms(delay_ms)
        self.step.value(0)
        time.sleep_ms(delay_ms)

    def rotate_continuous(self, steps, direction=1, delay_ms=5):
        """
        Rotate motor for specified number of steps.
        
        Args:
            steps: Number of steps to execute
            direction: 1 for clockwise, 0 for counter-clockwise
            delay_ms: Delay between steps in milliseconds
        """
        for _ in range(steps):
            self.step_once(direction, delay_ms)


def print_header():
    """Print the header for the motor test display."""
    print("\n" + "="*70)
    print("  CONTINUOUS MOTOR ROTATION TEST")
    print("="*70)
    print("\nThis script will continuously rotate both motors.")
    print("Watch for:")
    print("  • Motor shaft rotation")
    print("  • Unusual sounds (buzzing, clicking)")
    print("  • LED indicators on motor drivers")
    print("  • Vibrations or jerky movements")
    print("\nPress Ctrl+C to stop.\n")
    print("-"*70)


def main():
    print("Initializing motors...")
    print()
    
    # Initialize both motors
    try:
        motor_top = StepperMotor(
            dir_pin=2, 
            step_pin=3, 
            ms1_pin=6, 
            ms2_pin=7, 
            ms3_pin=8,
            name="TOP MOTOR"
        )
        print()
    except Exception as e:
        print(f"✗ Failed to initialize top motor: {e}")
        motor_top = None
    
    try:
        motor_bottom = StepperMotor(
            dir_pin=4, 
            step_pin=5, 
            ms1_pin=10, 
            ms2_pin=11, 
            ms3_pin=12,
            name="BOTTOM MOTOR"
        )
        print()
    except Exception as e:
        print(f"✗ Failed to initialize bottom motor: {e}")
        motor_bottom = None
    
    if not motor_top and not motor_bottom:
        print("\nERROR: No motors could be initialized!")
        return
    
    time.sleep(1)
    print_header()
    
    # Test parameters
    steps_per_cycle = 1600  # Steps before changing direction 
    delay_ms = 2  # Milliseconds between steps (slower = easier to observe)
    
    print(f"Configuration:")
    print(f"  Steps per cycle: {steps_per_cycle}")
    print(f"  Step delay: {delay_ms}ms")
    print(f"  Speed: ~{1000/(delay_ms*2)} steps/sec")
    print()
    print("-"*70)
    print(f"{'Cycle':<10}{'Direction':<15}{'Top Motor':<20}{'Bottom Motor'}")
    print("-"*70)
    
    cycle = 0
    direction = 1  # Start clockwise
    
    try:
        while True:
            cycle += 1
            dir_str = "Clockwise →" if direction == 1 else "Counter-CW ←"
            
            # Status strings
            top_status = "Rotating..." if motor_top else "NOT INIT"
            bottom_status = "Rotating..." if motor_bottom else "NOT INIT"
            
            print(f"{cycle:<10}{dir_str:<15}{top_status:<20}{bottom_status}")
            
            # Rotate both motors simultaneously
            for step in range(steps_per_cycle):
                if motor_top:
                    motor_top.step_once(direction, delay_ms)
                if motor_bottom:
                    motor_bottom.step_once(direction, delay_ms)
            
            # Reverse direction every cycle
            direction = 1 - direction
            
            # Small pause between direction changes
            time.sleep(0.5)
            
            # Every 10 cycles, print diagnostic info
            if cycle % 10 == 0:
                print()
                print(f"[Cycle #{cycle} completed]")
                print(f"  Total steps executed: {cycle * steps_per_cycle}")
                if motor_top:
                    print(f"  ✓ TOP MOTOR: Operating")
                else:
                    print(f"  ✗ TOP MOTOR: Not initialized")
                if motor_bottom:
                    print(f"  ✓ BOTTOM MOTOR: Operating")
                else:
                    print(f"  ✗ BOTTOM MOTOR: Not initialized")
                print()
            
    except KeyboardInterrupt:
        print("\n" + "-"*70)
        print("\nMotor test stopped.")
        print(f"Total cycles completed: {cycle}")
        print(f"Total steps per motor: ~{cycle * steps_per_cycle}")
        print("\n" + "="*70)
        print("TROUBLESHOOTING CHECKLIST:")
        print("="*70)
        print("\nIf a motor is NOT rotating:")
        print("  1. Check power supply to motor driver")
        print("  2. Verify motor wiring (Coil A: A+/A-, Coil B: B+/B-)")
        print("  3. Check DIR and STEP pin connections")
        print("  4. Verify MS1/MS2/MS3 pin connections")
        print("  5. Check motor driver enable pin (if present)")
        print("  6. Test motor driver LED indicators")
        print("  7. Swap motor cables to verify motor vs driver issue")
        print("  8. Check ground connections between Pico and driver")
        print("\nIf motor is buzzing but not rotating:")
        print("  • One coil may be disconnected")
        print("  • Check A+/A- and B+/B- wiring")
        print("  • Verify coil pairs are correct")
        print("\nIf motor is jerky or skipping steps:")
        print("  • Increase delay_ms (slower speed)")
        print("  • Check power supply current capacity")
        print("  • Verify microstep settings")
        print("\n" + "="*70)
        
        # Stop motors safely
        if motor_top:
            motor_top.step.value(0)
        if motor_bottom:
            motor_bottom.step.value(0)


# Run the motor test
if __name__ == "__main__":
    main()
