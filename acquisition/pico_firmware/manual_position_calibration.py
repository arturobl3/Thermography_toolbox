"""
Manual Position Calibration Tool for Filter Wheel Encoders

This script continuously reads and displays the angle from the AS5600 magnetic
position encoders. Use this to:
1. Diagnose encoder malfunctions
2. Manually rotate filter wheels and record positions
3. Calibrate filter slot angles

Instructions:
1. Upload this file to the Pico as main.py (use mpremote)
2. Open a serial terminal to see the output
3. Manually rotate the filter wheel
4. Record the angles for each of the 8 filter positions
5. Update the angles in the main.py file

Press Ctrl+C to exit.
"""

import time
from machine import Pin, I2C

# Encoder class
class AS5600Encoder:
    def __init__(self, i2c, name="Encoder"):
        """
        Class which handles encoder output.
        
        Args:
            i2c: I2C bus object
            name: Display name for this encoder
        """
        self.i2c = i2c
        self.addr = 0x36
        self.name = name

    def read_angle(self):
        """
        Method which reads raw output of the encoder and converts it to angle.
        
        Returns:
            float: Angle in degrees (0-360), or -1 if read fails
        """
        try:
            raw = self.i2c.readfrom_mem(self.addr, 0x0E, 2)
            angle = (raw[0] << 8 | raw[1]) & 0x0FFF
            return angle * 360.0 / 4096
        except Exception as e:
            return -1
    
    def read_raw(self):
        """
        Read the raw 12-bit value from the encoder.
        
        Returns:
            int: Raw value (0-4095), or -1 if read fails
        """
        try:
            raw = self.i2c.readfrom_mem(self.addr, 0x0E, 2)
            return (raw[0] << 8 | raw[1]) & 0x0FFF
        except Exception as e:
            return -1


def print_header():
    """Print the header for the calibration display."""
    print("\n" + "="*70)
    print("  FILTER WHEEL POSITION CALIBRATION TOOL")
    print("="*70)
    print("\nManually rotate the filter wheels to each position.")
    print("Record the angle values displayed below.\n")
    print("Press Ctrl+C to exit.\n")
    print("-"*70)


def main():
    # Initialize I2C buses for both encoders
    print("Initializing encoders...")
    
    try:
        i2c_top = I2C(0, scl=Pin(21), sda=Pin(20))
        encoder_top = AS5600Encoder(i2c_top, name="TOP")
        print("✓ Top encoder initialized (I2C0: SCL=GPIO21, SDA=GPIO20)")
    except Exception as e:
        print(f"✗ Failed to initialize top encoder: {e}")
        encoder_top = None
    
    try:
        i2c_bottom = I2C(1, scl=Pin(27), sda=Pin(26))
        encoder_bottom = AS5600Encoder(i2c_bottom, name="BOTTOM")
        print("✓ Bottom encoder initialized (I2C1: SCL=GPIO27, SDA=GPIO26)")
    except Exception as e:
        print(f"✗ Failed to initialize bottom encoder: {e}")
        encoder_bottom = None
    
    if not encoder_top and not encoder_bottom:
        print("\nERROR: No encoders could be initialized!")
        return
    
    time.sleep(1)
    print_header()
    
    # Reading mode selection
    print("Select reading mode:")
    print("  1 - Read BOTH encoders (default)")
    print("  2 - Read TOP encoder only")
    print("  3 - Read BOTTOM encoder only")
    print("\nWaiting 3 seconds, then defaulting to BOTH...")
    time.sleep(3)
    
    # Default to reading both
    read_top = encoder_top is not None
    read_bottom = encoder_bottom is not None
    
    print(f"\nReading: {'TOP ' if read_top else ''}{'BOTTOM' if read_bottom else ''}")
    print("-"*70)
    print(f"{'Time (s)':<12}{'Top Angle (°)':<20}{'Bottom Angle (°)':<20}{'Status'}")
    print("-"*70)
    
    start_time = time.time()
    sample_count = 0
    
    try:
        while True:
            sample_count += 1
            elapsed = time.time() - start_time
            
            # Read angles
            if read_top:
                top_angle = encoder_top.read_angle()
                top_raw = encoder_top.read_raw()
            else:
                top_angle = -1
                top_raw = -1
            
            if read_bottom:
                bottom_angle = encoder_bottom.read_angle()
                bottom_raw = encoder_bottom.read_raw()
            else:
                bottom_angle = -1
                bottom_raw = -1
            
            # Format output
            top_str = f"{top_angle:6.2f}°" if top_angle >= 0 else "ERROR"
            bottom_str = f"{bottom_angle:6.2f}°" if bottom_angle >= 0 else "ERROR"
            
            # Status indicators
            status = []
            if read_top and top_angle < 0:
                status.append("⚠ TOP FAIL")
            if read_bottom and bottom_angle < 0:
                status.append("⚠ BOTTOM FAIL")
            
            status_str = " | ".join(status) if status else "✓ OK"
            
            # Print reading
            print(f"{elapsed:6.1f}      {top_str:<20}{bottom_str:<20}{status_str}")
            
            # Every 10 samples, print detailed info
            if sample_count % 10 == 0:
                print(f"\n[Sample #{sample_count}]")
                if read_top and top_angle >= 0:
                    print(f"  TOP:    {top_angle:6.2f}° (raw: {top_raw})")
                if read_bottom and bottom_angle >= 0:
                    print(f"  BOTTOM: {bottom_angle:6.2f}° (raw: {bottom_raw})")
                print()
            
            time.sleep(0.5)  # Update twice per second
            
    except KeyboardInterrupt:
        print("\n" + "-"*70)
        print("\nCalibration session ended.")
        print(f"Total samples: {sample_count}")
        print(f"Duration: {time.time() - start_time:.1f} seconds")
        print("\n" + "="*70)
        print("INSTRUCTIONS FOR UPDATING MAIN.PY:")
        print("="*70)
        print("\n1. Record the angles for all 8 positions on each wheel")
        print("2. Update the arrays in main.py:")
        print("\n   top_angles = [pos0, pos1, pos2, pos3, pos4, pos5, pos6, pos7]")
        print("   bottom_angles = [pos0, pos1, pos2, pos3, pos4, pos5, pos6, pos7]")
        print("\n3. Upload the updated main.py to the Pico")
        print("\n" + "="*70)


# Run the calibration tool
if __name__ == "__main__":
    main()
