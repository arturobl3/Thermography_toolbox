"""Pico firmware for the thermography setup: switches the halogen-lamp relay.

Listens on USB serial (stdin) for one command per line, sent by
acquisition/camera/thermography.cpp:

    ping <frame_index> <duration_sec> <duration_sec>

It turns the relay on for duration_sec, turns it off, then replies "pong".
Malformed commands get "error". frame_index is only logged. The duration
appears twice for compatibility with the host program; only the first one
is used.
"""

import sys
import time

from machine import Pin

RELAY_PIN = 15  # GPIO15 drives the lamp relay

# Upper bound on a single heating pulse, so a typo on the host cannot leave
# the lamps on indefinitely. Raise it if an experiment needs longer pulses.
MAX_HEATING_SEC = 300

relay = Pin(RELAY_PIN, Pin.OUT)
relay.off()


def heat(duration_sec):
    """Keep the relay on for duration_sec, and always switch it off afterwards."""
    relay.on()
    try:
        time.sleep(duration_sec)
    finally:
        relay.off()


def handle(line):
    parts = line.split()
    if not parts or parts[0] != "ping":
        return  # ignore anything that is not a command (e.g. REPL noise)

    if len(parts) != 4:
        print("error")
        return
    try:
        frame_index = int(parts[1])
        duration_sec = int(parts[2])
    except ValueError:
        print("error")
        return
    if not 0 < duration_sec <= MAX_HEATING_SEC:
        print("error")
        return

    print(f"[INFO] Heating at frame {frame_index} for {duration_sec}s")
    heat(duration_sec)
    print("pong")


print("[INFO] Relay controller ready")
while True:
    line = sys.stdin.readline()
    if line:
        handle(line.strip())
    else:
        time.sleep(0.01)
