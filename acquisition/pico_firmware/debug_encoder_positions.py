"""
Encoder Position Debug Script

This script reads and displays the current position of both encoders
to help diagnose encoder communication issues.

Run this to verify:
1. Both encoders are responding
2. Encoders are returning valid angles (0-360)
3. Encoder readings are stable
"""

import time
from machine import Pin, I2C

class AS5600Encoder:
    def __init__(self, i2c, name="Encoder"):
        self.i2c = i2c
        self.addr = 0x36
        self.name = name

    def read_angle(self):
        try:
            raw = self.i2c.readfrom_mem(self.addr, 0x0E, 2)
            angle = (raw[0] << 8 | raw[1]) & 0x0FFF
            return angle * 360.0 / 4096
        except Exception as e:
            return -1

    def test_connection(self):
        """Test if encoder is responding"""
        try:
            # Try to read the status register
            self.i2c.readfrom_mem(self.addr, 0x0B, 1)
            return True
        except:
            return False


print("\n" + "="*60)
print("  ENCODER POSITION DEBUG")
print("="*60)

# Initialize I2C for both encoders
print("\nInitializing I2C buses...")
i2c_top = I2C(0, scl=Pin(21), sda=Pin(20))
i2c_bottom = I2C(1, scl=Pin(27), sda=Pin(26))

encoder_top = AS5600Encoder(i2c_top, "TOP")
encoder_bottom = AS5600Encoder(i2c_bottom, "BOTTOM")

# Test connections
print("\nTesting encoder connections...")
top_connected = encoder_top.test_connection()
bottom_connected = encoder_bottom.test_connection()

print(f"  TOP encoder (I2C0): {'✓ Connected' if top_connected else '✗ NOT CONNECTED'}")
print(f"  BOTTOM encoder (I2C1): {'✓ Connected' if bottom_connected else '✗ NOT CONNECTED'}")

if not top_connected and not bottom_connected:
    print("\n[ERROR] No encoders detected! Check wiring.")
    print("  - Verify SDA/SCL connections")
    print("  - Check encoder power (3.3V)")
    print("  - Verify I2C address (should be 0x36)")
elif not bottom_connected:
    print("\n[WARNING] Bottom encoder not responding!")
    print("  - This is likely causing the motor vibration issue")
    print("  - Check I2C1 wiring (SDA=GPIO26, SCL=GPIO27)")

print("\n" + "-"*60)
print("Reading encoder positions (Press Ctrl+C to stop)...")
print("-"*60)
print(f"{'Time':<12}{'TOP Angle':<15}{'BOTTOM Angle':<15}{'Status'}")
print("-"*60)

try:
    count = 0
    while True:
        count += 1
        
        top_angle = encoder_top.read_angle()
        bottom_angle = encoder_bottom.read_angle()
        
        # Status indicators
        status = ""
        if top_angle == -1:
            status += "TOP_ERROR "
        if bottom_angle == -1:
            status += "BOTTOM_ERROR "
        if not status:
            status = "OK"
        
        print(f"{count:<12}{top_angle:>6.2f}°{' '*7}{bottom_angle:>6.2f}°{' '*7}{status}")
        
        time.sleep(0.5)
        
except KeyboardInterrupt:
    print("\n" + "-"*60)
    print("\nDebug session ended.")
    print("\nTroubleshooting:")
    print("  - If angle is -1: Encoder not responding (check I2C wiring)")
    print("  - If angle jumps wildly: Weak magnet or encoder misalignment")
    print("  - If angle is stable: Encoder working correctly")
    print("\n" + "="*60)
