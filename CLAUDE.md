# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

The goal is a single repo for the lab's pulse-thermography work. It is a fork (`origin` = `arturobl3/Thermography_toolbox`) of Konrad Jaworski's analysis toolbox (`konrad-jaworski/Thermography_toolbox`). It has two parts:

- **`pulse_method/`**: Konrad's analysis code. A single `thermograms` class in `toolbox_pulse.py` loads a sequence of shape `(N_frames, H, W)` and runs PPT, PCT, TSR, HOS and DMD. Each has a NumPy version and a `*_torch` version; the torch versions accept NumPy input and return tensors. It also has filtering helpers (`SavGol`, `MeanFil`, `svd_denoise`, `binarize_mask`). It is installed with `pip install .` (`setup.py`, package name `thermography_toolbox`). **Leave this folder as Konrad wrote it**, so his updates merge cleanly once his repo is added as `upstream` (not done yet).
- **`acquisition/`**: our hardware code, which records the sequences `pulse_method` analyses. See `acquisition/README.md` for the full setup and recording guide.
  - `camera/thermography.cpp`: records N frames from the Workswell WIC camera and switches on the halogen lamps at a given frame through the Pico.
  - `camera/preview.cpp`: live view (needs OpenCV).
  - `camera/picoserial.h`: the USB serial link to the Pico (`send()` + `poll()`, which never block).
  - `pico_firmware/main.py`: MicroPython relay firmware. Protocol: `ping <frame> <dur> <dur>` → relay on for `dur` s → `pong`; bad commands get `error`; `MAX_HEATING_SEC = 300`.
- **`vendor/wic_sdk/`**: Workswell WIC SDK 3.1 (installer zip with `.deb`s, Doxygen API docs at `documentation/index.html`, examples, manuals) and the camera license file. Committed on purpose. Don't edit.

**Where the two parts meet:** a session folder `data/<session>/{raw,calibrated,temperature}/<n>.bin`, plus `frames.csv` and `session.txt`. `data/` is in the repo root and is gitignored. The default is compiled in from `CMakeLists.txt` (`DATA_DIR`), and `--data-dir` overrides it. The `.bin` files are read by `thermograms.loadfrombinfiles(dir, dtype)`: use `uint16` for raw and calibrated, `float32` for temperature. Pass an absolute path, because the loader doesn't expand `~`.

## Build and run (acquisition)

```bash
# once per machine: SDK + eBUS runtime from vendor/wic_sdk (see acquisition/README.md)
source /opt/pleora/ebus_sdk/Ubuntu-22.04-x86_64/bin/set_puregev_env.sh   # every shell; else "GENICAM_ROOT_V3_3 is not set"

cd acquisition/camera && cmake -S . -B build && cmake --build build
./build/thermography <frames> <session> <heating_start_frame> <heating_sec> [--range low|high] [--nuc manual|auto] [--license f] [--data-dir d]
./build/thermography --help

cd acquisition/pico_firmware && uv sync
uv run mpremote connect "$PICO_PORT" fs cp main.py :main.py && uv run mpremote connect "$PICO_PORT" reset
```

- `PICO_PORT` / `PICO_SERIAL_PORT` default to `/dev/serial/by-id/usb-MicroPython_Board_in_FS_mode_e6614104034a962a-if00`. Use the by-id path: when an ODrive is connected it takes `ttyACM0`.
- OpenCV is optional. Without it CMake skips `preview` and still builds `thermography`.
- The default license path and data folder are compiled in from `CMakeLists.txt` (`WIC_LICENSE_PATH`, `DATA_DIR`), so rebuild after moving the repo.
- There are no automated tests. To check the serial logic without hardware, run a fake Pico on a pseudo-terminal: execute `handle()` from `main.py` with a stub `machine` module, and point `PICO_SERIAL_PORT` at the pty.

## Camera facts that matter

The detailed reference is `Docs/camera_control.md` in `arturobl3/thermal_bandpass`, measured on this same camera (serial `332C2309`, 640×512, 30 fps, lens `019mm`).

- **Without the license, `calibrateRawInplace` does nothing.** Sessions recorded with the old `thermography` (no `frames.csv`) have `calibrated/` byte-identical to `raw/`, and their `temperature/` values come from uncalibrated counts. Those sessions also **lack the heating phase**, because capture blocked until the Pico replied.
- The order of calls matters: `findAndConnect(LicenseFile)` → `doDefaultWICSettings` → `setRangeAndLens(Low, "019mm")` → `getCurrentTemperatureResolution()`. The last call must come after the range is set.
- **Never switch range mid-session.** Low (−25…120 °C) is correct; samples stay below about 60 °C.
- **NUC:** use Manual mode plus one flat-field correction at startup: set the shutter reference temperature to the mean of sensor and housing temperature, close the shutter and verify, `doNUCUpdate(Long)`, reopen and verify, with a 2 s settle after each move. In Auto mode the shutter closes on its own mid-recording, and every NUC shifts the absolute level by about 1–2 °C.
- Even with the license, absolute temperatures are biased by up to about −8 °C at the low end of the range. Changes over time are reliable.
- Don't call `doCameraReset()`; it's equivalent to cutting power and leaves the camera in an unpredictable state. The `WIC` object must only be used from one thread.

## Status and open work (as of 2026-11-18)

1. **The new `thermography.cpp` has not been run on the camera yet.** It compiles cleanly, and the heating logic passed against a simulated Pico. Checklist on the acquisition PC:
   - Upload the relay-only `main.py` to the Pico.
   - Build.
   - Run `./build/thermography 60 test_noheat 0 0`. In `session.txt`, `measured_fps` should be about 30, and `cmp raw/30.bin calibrated/30.bin` must report a difference.
   - Run `./build/thermography 300 test_heat 60 3`. In `frames.csv`, `time_s` should have no gap and `lamp_on` should be 1 for about 90 rows.
   - Writing three files per frame is about 80 MB/s at 30 fps. If `measured_fps` drops below 30, the disk can't keep up.
2. Add Konrad's repo as `upstream` and fetch from it. Not done yet.
3. Merge the U-Net repo (`arturobl3/thermography`: synthetic-data U-Net denoiser/segmenter for defect maps, `helper_functions.py`, real defect maps in `data/real/`) into this one. When that happens, move this repo from `setup.py` to `pyproject.toml` + uv. The `.gitignore` rules `/data/` and `*.npy` would hide the U-Net repo's tracked `data/real/*.npy`, so add an exception or give them another location. Note that this repo has its own CLAUDE.md, and that it currently installs `pulse_method` from Konrad's GitHub, pinned to commit `f2c8900`, not from this fork.
4. `preview.cpp:265` ignores the return value of `doNUCUpdate()`, and `preview` doesn't use the license either.

The full filter-wheel and hyperspectral code (dual stepper motors, encoders, `hyperspectral.cpp`, debug scripts) was removed because the hardware no longer exists. It's in commit `2df92c9` if it's ever needed.

## Working with the user

The user is improving their git skills. For git operations beyond staging, such as commits, branches, merges, pushes and remotes, give the commands with a one-line explanation of each and let them run them. Ask before deleting files that git can't restore.
