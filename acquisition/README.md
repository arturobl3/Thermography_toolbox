# Acquisition

Code that runs the physical thermography setup and records the sequences that `pulse_method` analyses.

| Part | What it is |
|---|---|
| Workswell WIC thermal camera (serial `332C2309`) | Records the frames, controlled through the WIC SDK |
| Raspberry Pi Pico + relay | Switches the halogen lamps on for the heating pulse |
| `camera/` | C++ host programs: `thermography` (records a sequence and triggers heating) and `preview` (live view) |
| `pico_firmware/` | MicroPython firmware for the Pico; [its README](pico_firmware/README.md) covers the protocol, wiring and how to upload |
| `../vendor/wic_sdk/` | WIC SDK 3.1: installer zip, API documentation, examples, manuals, license and calibration files |

## 1. Install the WIC SDK (once per machine)

```bash
cd vendor/wic_sdk
unzip 18-software-3-1-0.zip -d /tmp/wic_sdk
# eBUS runtime: pick the package matching the OS (22.04 package for Ubuntu 22.04+)
sudo apt install /tmp/wic_sdk/eBUS_Runtime_Ubuntu-22.04-x86_64-6.4.0-6670.deb
sudo apt install /tmp/wic_sdk/wic-sdk_3.1_amd64.deb
```

The eBUS runtime needs its environment set in every shell that runs the camera programs. Without it they exit with `GENICAM_ROOT_V3_3 is not set`. Add this line to `~/.zshrc` or `~/.bashrc`:

```bash
source /opt/pleora/ebus_sdk/Ubuntu-22.04-x86_64/bin/set_puregev_env.sh
```

`preview` also needs OpenCV (`sudo apt install libopencv-dev`). Without it, CMake skips `preview` and builds `thermography` only.

The API reference is at `vendor/wic_sdk/documentation/index.html`.

## 2. Build the camera programs

```bash
cd acquisition/camera
cmake -S . -B build
cmake --build build
```

## 3. Upload the Pico firmware

See [pico_firmware/README.md](pico_firmware/README.md#uploading-the-firmware).

## 4. Frame and focus with `preview`

```bash
./build/preview             # options: --range low|high (default low), --license <file>
```

`preview` sets the camera up the same way as `thermography`: license calibration, range, lens, manual NUC and one flat-field correction at startup (the shutter closes for about 5 s). The image is scaled to the temperature span of the scene, ignoring the hottest and coldest 0.5 % of pixels.

To focus, turn the lens until the edges of the sample light up in green (**focus peaking**) and the **sharpness** number at the top is at its maximum. The number turns green when it is within 2 % of the best value seen so far.

| Control | |
|---|---|
| `peaking %` slider | Threshold: a pixel is painted green when its temperature gradient exceeds this percentage of the displayed span per pixel. Lower it for low-contrast samples |
| `p` | Focus peaking on/off |
| `r` | Reset the best sharpness (do this after moving the camera or sample) |
| `q` / Esc | Quit |
| mouse | Shows the temperature under the cursor |

Sharpness is the RMS temperature gradient of the whole frame in mK/px. Compare it only within one scene: it depends on the sample's contrast, not only on focus.

## 5. Record a session

```bash
./build/thermography <frame_count> <session_name> <heating_start_frame> <heating_duration_sec> [options]
# e.g. 3000 frames, lamps on after frame 100 for 5 s:
./build/thermography 3000 d1_cooldown 100 5
```

| Option | Default | |
|---|---|---|
| `--license <file>` | `vendor/wic_sdk/license 332C2309.wlic` | Needed for calibration; the program refuses to run without it |
| `--data-dir <dir>` | `data/` in the repo root | Where session folders are created. `data/` is gitignored |
| `--range low\|high` | `low` (−25…120 °C) | Set once per session; never switch range mid-session |
| `--nuc manual\|auto` | `manual` | `manual`: one flat-field correction (shutter closed ~5 s) before recording, shutter open throughout. `auto`: the camera may close the shutter mid-recording |

`heating_duration_sec = 0` records without heating. A session name that already exists is refused, so nothing gets overwritten.

The camera keeps recording while the lamps are on: the program sends the heating command and checks for the Pico's reply on every frame instead of waiting for it.

### Output

Everything goes to `data/<session_name>/` in the repo root, or to `<data-dir>/<session_name>/` if you pass `--data-dir`. The default is compiled in, so it's the same no matter which folder you run the program from:

| File | Content | dtype |
|---|---|---|
| `raw/<n>.bin` | Raw sensor counts | `uint16` |
| `calibrated/<n>.bin` | Counts after the license calibration (sensor temperature refreshed every 15 frames) | `uint16` |
| `temperature/<n>.bin` | Temperature in °C | `float32` |
| `frames.csv` | `frame, time_s, sensor_temp_c, lamp_on`: one row per frame. `time_s` is when the frame arrived; `lamp_on` is accurate to about one frame | text |
| `session.txt` | Command, camera settings (range, lens, NUC mode, FFC reference temperature), measured fps and heating result | text |

Even with the license, the camera's calibration is off by several °C at the low end of the range (see `thermal_bandpass/Docs/camera_control.md`). Changes in temperature over time are reliable; absolute values are not.

**Sessions recorded with the old `thermography`**, the ones without `frames.csv` and `session.txt`, were made without the license: their `calibrated/` frames are identical to `raw/`, and `temperature/` was computed from uncalibrated counts. They also miss the heating phase, because capture paused while the lamps were on.

Load a session with the toolbox:

```python
from pathlib import Path
import numpy as np
import pandas as pd
from pulse_method.toolbox_pulse import thermograms

session = Path("data/d1_cooldown").resolve()   # run from the repo root; loadfrombinfiles does not expand "~"
analyzer = thermograms(height=512, width=640)
data = analyzer.loadfrombinfiles(str(session / "calibrated"))                     # uint16
temp = analyzer.loadfrombinfiles(str(session / "temperature"), dtype=np.float32)
frames = pd.read_csv(session / "frames.csv")       # real time axis and heating window
heating = frames[frames.lamp_on == 1].frame         # frames recorded while the lamps were on
```
