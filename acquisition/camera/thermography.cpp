#include <wic/calibrationdata.h>
#include <wic/camerafinder.h>
#include <wic/framegrabber.h>
#include <wic/wic.h>

#include "picoserial.h"

#include <algorithm>
#include <cstdlib>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

namespace fs = std::filesystem;

// Main program
int main(int argc, char* argv[]) {
    if (argc != 5) {
        // Inputs to the program where we specify number of frames to be recorded, name of the file, when to start heating and for how long
        std::cerr << "Usage: " << argv[0] << " <frame_count> <session_name> <heating_start_frame> <heating_duration_sec>\n";
        return 1;
    }

    int frameCount = std::stoi(argv[1]);
    std::string sessionName = argv[2];
    int heatingStartFrame = std::stoi(argv[3]);
    int heatingDurationSec = std::stoi(argv[4]);

    // Connection with the WIC camera
    auto wic = wic::findAndConnect("332C2309");
    if (!wic) {
        std::cerr << "Could not connect WIC.\n";
        return 2;
    }

    // Settings of the camera spatial resolution
    auto resolution = wic->getResolution();
    int width = resolution.result[0];
    int height = resolution.result[1];
    if (width == 0 || height == 0) {
        std::cerr << "Invalid resolution.\n";
        return 3;
    }

    // Defoult settings of the thermal camera
    if (wic->doDefaultWICSettings().status != wic::ResponseStatus::Ok) {
        std::cerr << "Failed to apply default settings.\n";
        return 4;
    }

    // Core temperature of the camera
    auto coreTemp = wic->getCameraTemperature(wic::CameraTemperature::SensorTemp);

    // Initialization of variables fo capturing frames
    auto grabber = wic->frameGrabber();
    grabber->setup();

    std::vector<uint8_t> buffer(width * height * sizeof(uint16_t));
    std::vector<float> temperatures(width * height);

    const char* home = getenv("HOME");
    if (!home) {
        std::cerr << "Could not determine HOME directory.\n";
        return 5;
    }

    // Instruction how and here save the data
    fs::path dataRoot = fs::path(home) / "Desktop" / "data";
    fs::create_directories(dataRoot);

    fs::path rootDir = dataRoot / sessionName;
    fs::create_directories(rootDir / "raw");
    fs::create_directories(rootDir / "calibrated");
    fs::create_directories(rootDir / "temperature");

    // Get current temperature resolution of the camera, initially it in hight thermal resolution with low thermal range
    auto tempRes = wic->getCurrentTemperatureResolution();


    // Link to the Pico driving the halogen-lamp relay. Opened once, before capture,
    // so the DTR-safe open never lands in the middle of a frame.
    PicoLink pico;
    bool picoReady = false;
    if (heatingStartFrame < frameCount) {
        picoReady = pico.open();
        if (!picoReady) {
            std::cerr << "[ERROR] No Pico on " << picoSerialPort() << "; heating will not run.\n";
        }
    }
    // Loop hich determine how many frames to capture which were specified by the user.
    for (int frame = 0; frame < frameCount; ++frame) {
        wic::FrameGrabberError error;
        grabber->getBuffer(buffer.data(), error, 1000);
        if (error != wic::FrameGrabberError::None) {
            std::cerr << "Frame grabber error.\n";
            return 6;
        }

        auto* buffer16 = reinterpret_cast<uint16_t*>(buffer.data());

        // Save raw
        std::ofstream rawOut(rootDir / "raw" / (std::to_string(frame) + ".bin"), std::ios::binary);
        rawOut.write(reinterpret_cast<char*>(buffer16), buffer.size());
        rawOut.close();

        // Calibrate
        wic->calibrateRawInplace(
            buffer16,
            buffer.size() / 2,
            (coreTemp.status == wic::ResponseStatus::Ok) ? coreTemp.result : 0);

        std::ofstream calOut(rootDir / "calibrated" / (std::to_string(frame) + ".bin"), std::ios::binary);
        calOut.write(reinterpret_cast<char*>(buffer16), buffer.size());
        calOut.close();
        
        // Convert calibrated data to temperature
        for (size_t i = 0; i < buffer.size() / 2; ++i) {
            temperatures[i] = wic::rawToCelsius(buffer16[i], tempRes);
        }

        // Save temeperature
        std::ofstream tempOut(rootDir / "temperature" / (std::to_string(frame) + ".bin"), std::ios::binary);
        tempOut.write(reinterpret_cast<char*>(temperatures.data()), temperatures.size() * sizeof(float));
        tempOut.close();

        // Trigger heating
        if (frame == heatingStartFrame) {
            std::cout << "[INFO] Triggering heating at frame " << frame << " for " << heatingDurationSec << " seconds.\n";
            if (!picoReady) {
                std::cerr << "[ERROR] Heating command failed.\n";
            } else {
                const std::string command = "ping " + std::to_string(heatingStartFrame) + " " +
                                            std::to_string(heatingDurationSec) + " " +
                                            std::to_string(heatingDurationSec);
                // The firmware answers with pong only after the relay has been on for
                // heatingDurationSec, so the timeout has to cover the heating itself.
                if (!pico.sendCommand(command, std::chrono::seconds(heatingDurationSec + 5))) {
                    std::cerr << "[ERROR] Heating command failed.\n";
                }
            }
        }

        std::cout << "[INFO] Frame " << frame << " captured.\n";
    }

    std::cout << "[INFO] Done recording " << frameCount << " frames.\n";
    return 0;
}
