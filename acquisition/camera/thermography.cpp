// Records a pulse-thermography sequence with the WIC camera and triggers the
// halogen lamps through the Pico relay (acquisition/pico_firmware).
//
// Output: <repo>/data/<session_name>/ (or --data-dir <dir>/<session_name>/)
//   raw/<n>.bin          uint16  raw sensor counts
//   calibrated/<n>.bin   uint16  counts after the license calibration
//   temperature/<n>.bin  float32 degrees C
//   frames.csv           frame, time_s, sensor_temp_c, lamp_on (one row per frame)
//   session.txt          camera settings and run summary

#include <wic/calibrationdata.h>
#include <wic/camerafinder.h>
#include <wic/framegrabber.h>
#include <wic/wic.h>

#include "picoserial.h"

#include <chrono>
#include <cmath>
#include <cstdlib>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

#ifndef WIC_LICENSE_PATH
#define WIC_LICENSE_PATH ""  // set by CMakeLists.txt
#endif
#ifndef DATA_DIR
#define DATA_DIR ""  // set by CMakeLists.txt: <repo>/data
#endif

namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;

namespace {

constexpr const char* kLens = "019mm";
constexpr int kSensorTempRefreshFrames = 15;  // re-read sensor temperature this often
constexpr int kMaxHeatingSec = 300;           // MAX_HEATING_SEC in pico_firmware/main.py
constexpr int kPongGraceSec = 5;              // extra wait for "pong" after heating should end

struct Options {
    int frameCount = 0;
    std::string sessionName;
    int heatingStartFrame = 0;
    int heatingDurationSec = 0;
    std::string licensePath = WIC_LICENSE_PATH;
    std::string dataDir = DATA_DIR;
    std::string rangeName = "low";
    std::string nucMode = "manual";
};

void printUsage(const char* prog) {
    std::cerr
        << "Usage: " << prog
        << " <frame_count> <session_name> <heating_start_frame> <heating_duration_sec> [options]\n"
        << "\n"
        << "Options:\n"
        << "  --license <file>    WIC license (.wlic). Default:\n"
        << "                      " << WIC_LICENSE_PATH << "\n"
        << "  --data-dir <dir>    Where session folders are created. Default:\n"
        << "                      " << DATA_DIR << "\n"
        << "  --range low|high   Temperature range, low = -25..120 C (default: low)\n"
        << "  --nuc manual|auto   manual: one flat-field correction before recording and the\n"
        << "                      shutter stays open (default). auto: the camera may close\n"
        << "                      the shutter on its own during the recording.\n"
        << "\n"
        << "heating_duration_sec = 0 records without heating.\n";
}

bool parseInt(const std::string& text, int& out) {
    try {
        size_t used = 0;
        out = std::stoi(text, &used);
        return used == text.size();
    } catch (...) {
        return false;
    }
}

bool parseArgs(int argc, char* argv[], Options& opt) {
    std::vector<std::string> positional;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--help" || arg == "-h") return false;
        if (arg == "--license" || arg == "--data-dir" || arg == "--range" || arg == "--nuc") {
            if (i + 1 >= argc) {
                std::cerr << "[ERROR] " << arg << " needs a value\n";
                return false;
            }
            const std::string value = argv[++i];
            if (arg == "--license") opt.licensePath = value;
            if (arg == "--data-dir") opt.dataDir = value;
            if (arg == "--range") opt.rangeName = value;
            if (arg == "--nuc") opt.nucMode = value;
        } else if (arg.rfind("--", 0) == 0) {
            std::cerr << "[ERROR] Unknown option " << arg << "\n";
            return false;
        } else {
            positional.push_back(arg);
        }
    }

    if (positional.size() != 4) return false;
    opt.sessionName = positional[1];
    if (!parseInt(positional[0], opt.frameCount) || opt.frameCount <= 0 ||
        !parseInt(positional[2], opt.heatingStartFrame) || opt.heatingStartFrame < 0 ||
        !parseInt(positional[3], opt.heatingDurationSec) || opt.heatingDurationSec < 0) {
        std::cerr << "[ERROR] frame_count must be > 0; heating_start_frame and "
                     "heating_duration_sec must be >= 0 integers\n";
        return false;
    }
    if (opt.heatingDurationSec > kMaxHeatingSec) {
        std::cerr << "[ERROR] heating_duration_sec > " << kMaxHeatingSec
                  << " s: the Pico firmware would reject it (MAX_HEATING_SEC)\n";
        return false;
    }
    if (opt.rangeName != "low" && opt.rangeName != "high") {
        std::cerr << "[ERROR] --range must be low or high\n";
        return false;
    }
    if (opt.nucMode != "manual" && opt.nucMode != "auto") {
        std::cerr << "[ERROR] --nuc must be manual or auto\n";
        return false;
    }
    if (opt.licensePath.empty()) {
        std::cerr << "[ERROR] No license file: pass --license <file>\n";
        return false;
    }
    if (opt.dataDir.empty()) {
        std::cerr << "[ERROR] No data directory: pass --data-dir <dir>\n";
        return false;
    }
    if (opt.sessionName.find('/') != std::string::npos || opt.sessionName == "." ||
        opt.sessionName == "..") {
        std::cerr << "[ERROR] session_name must be a plain folder name\n";
        return false;
    }
    return true;
}

// Flat-field correction (NUC) with the shutter physically closed. Same sequence as
// thermal_bandpass/scripts/capture_burst.cpp: the camera's own shutter temperature
// reading is a stub, so the FFC reference is the mean of sensor and housing
// temperature. Returns false (with the shutter reopened if possible) on any failure.
bool runFlatField(wic::WIC* cam, double& anchorC) {
    constexpr auto kShutterSettle = std::chrono::milliseconds(2000);

    auto sensor = cam->getCameraTemperature(wic::CameraTemperature::SensorTemp);
    auto housing = cam->getCameraTemperature(wic::CameraTemperature::HousingTemp);
    anchorC = NAN;
    if (sensor.isOk() && housing.isOk()) {
        anchorC = (sensor.result + housing.result) / 2.0;
    } else if (sensor.isOk()) {
        anchorC = sensor.result;
    }
    if (!std::isnan(anchorC)) {
        if (cam->setShutterTemperature(anchorC) != wic::ResponseStatus::Ok) {
            std::cerr << "[WARN] setShutterTemperature failed; using camera default\n";
        }
        std::cout << "[INFO] FFC reference temperature " << std::fixed << std::setprecision(1)
                  << anchorC << " C\n";
    } else {
        std::cerr << "[WARN] Could not read sensor/housing temperature; FFC reference left at "
                     "camera default\n";
    }

    auto closeRes = cam->setShutterPosition(wic::ShutterPosition::Close);
    auto closeChk = cam->getShutterPosition();
    if (!closeRes.isOk() || !closeChk.isOk() || closeChk.result != wic::ShutterPosition::Close) {
        std::cerr << "[ERROR] Could not close the shutter for the flat-field correction\n";
        return false;
    }
    std::this_thread::sleep_for(kShutterSettle);

    auto nuc = cam->doNUCUpdate(wic::NUCUpdateType::Long);
    if (nuc != wic::ResponseStatus::Ok) {
        std::cerr << "[ERROR] NUC update failed: " << wic::responseStatusToStr(nuc) << "\n";
        (void)cam->setShutterPosition(wic::ShutterPosition::Open);
        return false;
    }

    auto openRes = cam->setShutterPosition(wic::ShutterPosition::Open);
    auto openChk = cam->getShutterPosition();
    if (!openRes.isOk() || !openChk.isOk() || openChk.result != wic::ShutterPosition::Open) {
        std::cerr << "[ERROR] Could not reopen the shutter after the flat-field correction\n";
        return false;
    }
    std::this_thread::sleep_for(kShutterSettle);
    return true;
}

std::string localTimestamp() {
    const std::time_t now = std::time(nullptr);
    std::ostringstream out;
    out << std::put_time(std::localtime(&now), "%Y-%m-%d %H:%M:%S");
    return out.str();
}

bool writeBinary(const fs::path& path, const void* data, size_t bytes) {
    std::ofstream out(path, std::ios::binary);
    out.write(static_cast<const char*>(data), static_cast<std::streamsize>(bytes));
    return static_cast<bool>(out);
}

enum class Heating { NotRequested, Waiting, On, Done, Failed };

}  // namespace

int main(int argc, char* argv[]) {
    Options opt;
    if (!parseArgs(argc, argv, opt)) {
        printUsage(argv[0]);
        return 1;
    }
    const bool heatingRequested =
        opt.heatingDurationSec > 0 && opt.heatingStartFrame < opt.frameCount;

    // --- Output folder (never overwrite a previous session) ---
    const fs::path rootDir = fs::path(opt.dataDir) / opt.sessionName;
    if (fs::exists(rootDir) && !fs::is_empty(rootDir)) {
        std::cerr << "[ERROR] " << rootDir << " already exists; choose another session name.\n";
        return 5;
    }

    // --- Connect with the license, so calibrateRawInplace actually calibrates ---
    wic::LicenseFile license(opt.licensePath.c_str());
    if (!license.isOk()) {
        std::cerr << "[ERROR] Could not load license file " << opt.licensePath << "\n";
        return 2;
    }
    wic::WIC* wic = wic::findAndConnect(license);
    if (!wic || !wic->connected()) {
        std::cerr << "[ERROR] Could not connect to WIC " << license.serialNumber() << ".\n";
        return 2;
    }
    std::cout << "[INFO] Connected to WIC " << license.serialNumber() << "\n";

    if (wic->doDefaultWICSettings().status != wic::ResponseStatus::Ok) {
        std::cerr << "[ERROR] Failed to apply default settings.\n";
        return 4;
    }

    // Range and lens decide which calibration is applied. Set the range once, here,
    // and never switch it mid-session.
    const wic::Range range = (opt.rangeName == "high") ? wic::Range::High : wic::Range::Low;
    auto rangeRes = wic->setRangeAndLens(range, kLens);
    if (!rangeRes.isOk()) {
        std::cerr << "[ERROR] Failed to set range " << opt.rangeName << " / lens " << kLens << ": "
                  << wic::responseStatusToStr(rangeRes.status) << "\n";
        return 4;
    }
    if (rangeRes.result > 0) {
        std::cerr << "[WARN] " << rangeRes.result
                  << " errors in the camera's correction data; check frames for artifacts\n";
    }
    const auto tempRes = wic->getCurrentTemperatureResolution();  // must follow setRangeAndLens

    auto resolution = wic->getResolution();
    const int width = resolution.result[0];
    const int height = resolution.result[1];
    if (!resolution.isOk() || width <= 0 || height <= 0) {
        std::cerr << "[ERROR] Invalid resolution.\n";
        return 3;
    }

    // --- NUC: manual mode keeps the shutter open for the whole recording ---
    const auto nucMode =
        (opt.nucMode == "auto") ? wic::NUCUpdateModes::Auto : wic::NUCUpdateModes::Manual;
    if (!wic->setNUCUpdateMode(nucMode).isOk()) {
        std::cerr << "[ERROR] Failed to set NUC mode " << opt.nucMode << ".\n";
        return 4;
    }
    if (wic->setIntegratedNUCUpdateFrames(wic::IntegratedNUCUpdateFrames::Frames16) !=
        wic::ResponseStatus::Ok) {
        std::cerr << "[ERROR] Failed to set integrated NUC frames.\n";
        return 4;
    }
    double ffcAnchorC = NAN;
    if (!runFlatField(wic, ffcAnchorC)) {
        return 4;
    }

    auto sensorRead = wic->getCameraTemperature(wic::CameraTemperature::SensorTemp);
    double sensorTempC = sensorRead.isOk() ? sensorRead.result : 0.0;
    if (!sensorRead.isOk()) {
        std::cerr << "[WARN] Could not read sensor temperature; calibrating with 0 C until it "
                     "can be read\n";
    }

    // --- Create the session folder and its metadata ---
    fs::create_directories(rootDir / "raw");
    fs::create_directories(rootDir / "calibrated");
    fs::create_directories(rootDir / "temperature");

    std::ofstream sessionTxt(rootDir / "session.txt");
    sessionTxt << "started: " << localTimestamp() << "\n"
               << "command:";
    for (int i = 0; i < argc; ++i) sessionTxt << " " << argv[i];
    sessionTxt << "\n"
               << "camera_serial: " << license.serialNumber() << "\n"
               << "license: " << opt.licensePath << "\n"
               << "lens: " << kLens << "\n"
               << "range: " << opt.rangeName << "\n"
               << "nuc_mode: " << opt.nucMode << "\n"
               << "ffc_reference_temp_c: " << ffcAnchorC << "\n"
               << "resolution: " << width << "x" << height << "\n"
               << "camera_fps: " << wic->getSpeed() << "\n"
               << "frame_count: " << opt.frameCount << "\n"
               << "heating_start_frame: " << opt.heatingStartFrame << "\n"
               << "heating_duration_sec: " << opt.heatingDurationSec << "\n";
    sessionTxt.flush();

    std::ofstream framesCsv(rootDir / "frames.csv");
    framesCsv << "frame,time_s,sensor_temp_c,lamp_on\n";

    // --- Pico link, opened before capture so its open never lands mid-recording ---
    PicoLink pico;
    Heating heating = Heating::NotRequested;
    if (heatingRequested) {
        if (pico.open()) {
            heating = Heating::Waiting;
        } else {
            std::cerr << "[ERROR] No Pico on " << picoSerialPort() << "; heating will not run.\n";
            heating = Heating::Failed;
        }
    }
    Clock::time_point heatingSentAt{};
    int lampOnFrame = -1, lampOffFrame = -1;

    // --- Capture ---
    auto grabber = wic->frameGrabber();
    grabber->setup();
    std::vector<uint16_t> buffer(static_cast<size_t>(width) * height);
    std::vector<float> temperatures(buffer.size());
    const size_t frameBytes = buffer.size() * sizeof(uint16_t);

    Clock::time_point t0{};
    double lastTimeS = 0.0;
    int captured = 0;
    int exitCode = 0;

    for (int frame = 0; frame < opt.frameCount; ++frame) {
        wic::FrameGrabberError error;
        grabber->getBuffer(reinterpret_cast<uint8_t*>(buffer.data()), error, 1000);
        const auto now = Clock::now();
        if (error != wic::FrameGrabberError::None) {
            std::cerr << "[ERROR] Frame grabber error at frame " << frame << ".\n";
            exitCode = 6;
            break;
        }
        if (frame == 0) t0 = now;
        lastTimeS = std::chrono::duration<double>(now - t0).count();

        // Heating status as of this frame (accurate to about one frame period).
        if (heating == Heating::On) {
            switch (pico.poll()) {
                case PicoLink::Reply::Pong:
                    heating = Heating::Done;
                    lampOffFrame = frame;
                    std::cout << "[INFO] Heating finished at frame " << frame << ".\n";
                    break;
                case PicoLink::Reply::Error:
                    heating = Heating::Failed;
                    std::cerr << "[ERROR] Pico rejected the heating command: " << pico.received()
                              << "\n";
                    break;
                case PicoLink::Reply::Pending:
                    if (now - heatingSentAt >
                        std::chrono::seconds(opt.heatingDurationSec + kPongGraceSec)) {
                        heating = Heating::Failed;
                        std::cerr << "[ERROR] No pong from the Pico " << opt.heatingDurationSec +
                                         kPongGraceSec
                                  << " s after the heating command. Got: " << pico.received()
                                  << "\n";
                    }
                    break;
            }
        }

        if (frame % kSensorTempRefreshFrames == 0) {
            auto s = wic->getCameraTemperature(wic::CameraTemperature::SensorTemp);
            if (s.isOk()) sensorTempC = s.result;
        }

        framesCsv << frame << ',' << std::fixed << std::setprecision(4) << lastTimeS << ','
                  << std::setprecision(2) << sensorTempC << ',' << (heating == Heating::On ? 1 : 0)
                  << '\n';

        const std::string name = std::to_string(frame) + ".bin";
        bool ok = writeBinary(rootDir / "raw" / name, buffer.data(), frameBytes);
        wic->calibrateRawInplace(buffer.data(), buffer.size(), sensorTempC);
        ok = writeBinary(rootDir / "calibrated" / name, buffer.data(), frameBytes) && ok;
        for (size_t i = 0; i < buffer.size(); ++i) {
            temperatures[i] = static_cast<float>(wic::rawToCelsius(buffer[i], tempRes));
        }
        ok = writeBinary(rootDir / "temperature" / name, temperatures.data(),
                         temperatures.size() * sizeof(float)) &&
             ok;
        if (!ok) {
            std::cerr << "[ERROR] Could not write frame " << frame << " (disk full?).\n";
            exitCode = 8;
            break;
        }
        captured = frame + 1;

        // Start heating after this frame is stored; frames keep coming while the
        // lamps are on, and the "pong" is picked up by poll() above.
        if (frame == opt.heatingStartFrame && heating == Heating::Waiting) {
            const std::string command = "ping " + std::to_string(opt.heatingStartFrame) + " " +
                                        std::to_string(opt.heatingDurationSec) + " " +
                                        std::to_string(opt.heatingDurationSec);
            if (pico.send(command)) {
                heating = Heating::On;
                heatingSentAt = Clock::now();
                lampOnFrame = frame + 1;
                std::cout << "[INFO] Heating on after frame " << frame << " for "
                          << opt.heatingDurationSec << " s.\n";
            } else {
                heating = Heating::Failed;
            }
        }

        if (frame % kSensorTempRefreshFrames == 0) framesCsv.flush();
        std::cout << "[INFO] Frame " << frame << " captured.\n";
    }
    framesCsv.close();

    // --- Summary ---
    const double fps = (captured > 1 && lastTimeS > 0) ? (captured - 1) / lastTimeS : 0.0;
    std::string heatingResult = "not requested";
    if (heating == Heating::Done) {
        heatingResult = "ok, lamp_on frames " + std::to_string(lampOnFrame) + ".." +
                        std::to_string(lampOffFrame - 1);
    } else if (heating == Heating::On) {
        heatingResult = "still on when recording ended (the Pico switches it off by itself)";
        std::cerr << "[WARN] Recording ended before heating finished.\n";
    } else if (heating == Heating::Waiting) {
        heatingResult = "not started (recording stopped before heating_start_frame)";
    } else if (heating == Heating::Failed) {
        heatingResult = "FAILED";
        if (exitCode == 0) exitCode = 7;
    }

    sessionTxt << "frames_captured: " << captured << "\n"
               << "duration_s: " << std::fixed << std::setprecision(3) << lastTimeS << "\n"
               << "measured_fps: " << std::setprecision(2) << fps << "\n"
               << "heating: " << heatingResult << "\n"
               << "finished: " << localTimestamp() << "\n";

    std::cout << "[INFO] Done recording " << captured << " frames in " << std::setprecision(1)
              << lastTimeS << " s (" << std::setprecision(2) << fps << " fps). Heating: "
              << heatingResult << ".\n";
    return exitCode;
}
