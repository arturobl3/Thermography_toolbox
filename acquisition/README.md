# Acquisition

Code that runs the physical thermography setup and records the sequences that `pulse_method` analyses.

| Part | What it is |
|---|---|
| Workswell WIC thermal camera (serial `332C2309`) | Records the frames, controlled through the WIC SDK |
| Raspberry Pi Pico + relay | Switches the halogen lamps on for the heating pulse |
| `camera/` | C++ host programs: `thermography` (records a sequence and triggers heating) and `preview` (live view) |
| `pico_firmware/` | MicroPython firmware for the Pico; [its README](pico_firmware/README.md) covers the protocol, wiring and how to upload |
| `../vendor/wic_sdk/` | WIC SDK 3.1: installer zip, API documentation, examples, manuals, license and calibration files |

`camera/hyperspectral.cpp` drove the old filter-wheel setup. It no longer works with the relay-only firmware.

## 1. Install the WIC SDK (once per machine)

```bash
cd vendor/wic_sdk
unzip 18-software-3-1-0.zip -d /tmp/wic_sdk
# eBUS runtime: pick the package matching the OS (22.04 package for Ubuntu 22.04+)
sudo apt install /tmp/wic_sdk/eBUS_Runtime_Ubuntu-22.04-x86_64-6.4.0-6670.deb
sudo apt install /tmp/wic_sdk/wic-sdk_3.1_amd64.deb
```

The camera programs also need OpenCV: `sudo apt install libopencv-dev`.

The API reference is at `vendor/wic_sdk/documentation/index.html`.

## 2. Build the camera programs

```bash
cd acquisition/camera
cmake -S . -B build
cmake --build build
```

## 3. Upload the Pico firmware

See [pico_firmware/README.md](pico_firmware/README.md#uploading-the-firmware).

## 4. Record a session

```bash
./build/preview            # optional: live view to check framing and focus ('high' for the high thermal range)
./build/thermography <frame_count> <session_name> <heating_start_frame> <heating_duration_sec>
# e.g. 3000 frames, lamps on at frame 100 for 5 s:
./build/thermography 3000 d1_cooldown 100 5
```

Frames are written to `~/Desktop/data/<session_name>/`, one file per frame:

| Subfolder | Content | dtype |
|---|---|---|
| `raw/<n>.bin` | Raw sensor counts | `uint16` |
| `calibrated/<n>.bin` | Counts after the camera's calibration | `uint16` |
| `temperature/<n>.bin` | Temperature in °C | `float32` |

Load them with the toolbox:

```python
from pathlib import Path
import numpy as np
from pulse_method.toolbox_pulse import thermograms

session = Path.home() / "Desktop" / "data" / "d1_cooldown"   # loadfrombinfiles does not expand "~"
analyzer = thermograms(height=512, width=640)
data = analyzer.loadfrombinfiles(str(session / "calibrated"))                     # uint16
temp = analyzer.loadfrombinfiles(str(session / "temperature"), dtype=np.float32)
```

**Known issue:** `thermography` stops capturing while the lamps are on. It waits for the Pico's `pong`, which only arrives after heating ends. So each recording is missing the heating phase, and the frames after it are offset in time by `heating_duration_sec`.
