# Pico relay firmware

MicroPython firmware for the Raspberry Pi Pico that switches the halogen-lamp relay during a thermography recording. The host program `acquisition/camera/thermography.cpp` sends it one command over USB serial when heating should start.

The Pico used to drive a dual filter-wheel system as well. That hardware is gone, and the firmware is now relay-only. The old code is in git history: commit `2df92c9`.

## Wiring

| Pico pin | Connected to |
|---|---|
| GPIO15 | Relay input (lamps on when high) |

## Serial protocol

The Pico reads one line per command from USB serial (115200 baud) and replies on the same port.

```
ping <frame_index> <duration_sec> <duration_sec>
```

- Turns the relay on for `duration_sec` seconds, turns it off, then replies `pong`.
- `frame_index` is only logged.
- `duration_sec` appears twice because `thermography.cpp` sends it twice; only the first value is used.
- Durations must be between 1 and `MAX_HEATING_SEC` (300 s by default, set in `main.py`).
- A malformed or out-of-range command gets the reply `error`, and the relay is left off.
- Lines that don't start with `ping` are ignored.

Example session:

```
> ping 100 5 5
[INFO] Heating at frame 100 for 5s
pong          (after 5 s)
```

The reply only comes **after** heating has finished, so the host must wait at least `duration_sec` seconds before giving up.

## Serial port

Address the board by its stable by-id path. The `/dev/ttyACM*` number depends on enumeration order: when the ODrive controller is connected it takes `ttyACM0`, and the Pico ends up on `ttyACM1`.

```bash
PICO_PORT=/dev/serial/by-id/usb-MicroPython_Board_in_FS_mode_e6614104034a962a-if00
```

The same path is the default in `acquisition/camera/picoserial.h`. Set the `PICO_SERIAL_PORT` environment variable to override it.

Opening the port normally raises DTR, and MicroPython reacts to that with a soft reset. `picoserial.h` avoids this by keeping DTR and RTS low. Keep that in mind if you write another host program.

## Uploading the firmware

`mpremote` is the only dependency in this folder's `pyproject.toml`:

```bash
cd acquisition/pico_firmware
uv sync
uv run mpremote connect "$PICO_PORT" fs cp main.py :main.py
uv run mpremote connect "$PICO_PORT" reset
```

To try the firmware by hand, open a REPL with `uv run mpremote connect "$PICO_PORT"` and type a command such as `ping 0 2 2`. The relay should click on for 2 s, then you should see `pong`. Exit with `Ctrl-]`.

Other ways to upload work too:
- **Thonny:** select the "MicroPython (Raspberry Pi Pico)" interpreter, then *Save as → Raspberry Pi Pico → `main.py`*.
- **USB mass storage:** hold BOOTSEL while plugging in the board. Note that this route needs the MicroPython UF2 to be installed first.

The VS Code MicroPico extension is configured through `.micropico` and `.vscode/`.

## Troubleshooting

- **No `pong`, or a timeout on the host:**
  - Check that nothing else holds the port open: a stray `mpremote`, a Thonny session, or a second host program.
  - Check that `main.py` was actually uploaded and the board was reset after the upload.
- **`error` reply:** the duration is out of range, or the command doesn't have exactly four fields.
- **Relay doesn't click:** check the relay's supply and the GPIO15 wiring. Test it from the REPL with `from machine import Pin; Pin(15, Pin.OUT).on()`.
