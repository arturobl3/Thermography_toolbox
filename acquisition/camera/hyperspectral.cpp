#include <wic/calibrationdata.h>
#include <wic/camerafinder.h>
#include <wic/framegrabber.h>
#include <wic/wic.h>

#include "picoserial.h"
#include <cstdlib>
#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <filesystem>
#include <chrono>
#include <thread>

namespace fs = std::filesystem;


// Main function
int main(int argc, char* argv[]) {
    if (argc != 3) {
        // Reading input from the user
        std::cerr << "Usage: " << argv[0] << " <frames_per_combination> <session_name>\n";
        return 1;
    }

    int framesPerCombination = std::stoi(argv[1]);
    std::string sessionName = argv[2];

    // Connect camera as before through serial number
    auto wic = wic::findAndConnect("332C2309");
    if (!wic) {
        std::cerr << "[ERROR] Could not connect to WIC.\n";
        return 2;
    }

    // Setting spatial resolution of the camera
    auto resolution = wic->getResolution();
    int width = resolution.result[0];
    int height = resolution.result[1];
    if (width == 0 || height == 0) {
        std::cerr << "[ERROR] Invalid camera resolution.\n";
        return 3;
    }

    // Defoult setting of the camera
    if (wic->doDefaultWICSettings().status != wic::ResponseStatus::Ok) {
        std::cerr << "[ERROR] Failed to apply default WIC settings.\n";
        return 4;
    }

    // Get camera core temperature as well as Temperature resolution. Initially it is high thermal resolution but low range of temperature.
    auto coreTemp = wic->getCameraTemperature(wic::CameraTemperature::SensorTemp);
    auto tempRes = wic->getCurrentTemperatureResolution();

    auto grabber = wic->frameGrabber();
    grabber->setup();

    const char* home = getenv("HOME");
    if (!home) {
        std::cerr << "[ERROR] Cannot get HOME environment variable.\n";
        return 5;
    }

    // Instruction here and how save the data
    fs::path dataRoot = fs::path(home) / "Desktop" / "data";
    fs::create_directories(dataRoot);

    // Create only the main session directory here
    fs::path sessionDir = dataRoot / sessionName;
    fs::create_directories(sessionDir);

    std::vector<uint8_t> buffer(width * height * sizeof(uint16_t));
    std::vector<float> temperatures(width * height);
    
    // Constant value which indicates how many filters are in each of the wheel inside of the camera
    const int maxIndex = 7;
    PicoLink serialPort;
    if (!serialPort.open()) {
        return 6;
    }

    // Main loop which will send indexes to Pico. Inside of the pico those indexes are decoded into the angular positions which camera will move the filters
    for (int i = 0; i <= maxIndex; ++i) {
        for (int j = 0; j <= maxIndex; ++j) {
            std::cout << "[INFO] Moving filter wheels to combination " << i << "_" << j << "\n";

            if (!serialPort.sendCommand("ping " + std::to_string(i) + "_" + std::to_string(j),
                                        std::chrono::seconds(60))) {
                std::cerr << "[ERROR] Failed to position filter wheels. Aborting.\n";
                return 7;
            }

            // Create a subfolder per combination
            fs::path comboDir = sessionDir / (std::to_string(i) + "_" + std::to_string(j));
            fs::create_directories(comboDir);

            // Skip capturing for final reset only if i==0 and j==0 and not first iteration (original logic)
            if (i == 0 && j == 0 && !(i == 0 && j == 0 && (i == 0 && j == 0))) {
                std::cout << "[INFO] Reset position reached, no frame captured.\n";
                continue;
            }

            // Grabbing raw frame
            for (int frame = 0; frame < framesPerCombination; ++frame) {
                wic::FrameGrabberError error;
                grabber->getBuffer(buffer.data(), error, 1000);
                if (error != wic::FrameGrabberError::None) {
                    std::cerr << "[ERROR] Frame grabber error.\n";
                    return 8;
                }

                auto* buffer16 = reinterpret_cast<uint16_t*>(buffer.data());

                // Save raw data to combination folder
                std::string filenameRaw = (comboDir / ("raw_" + std::to_string(frame) + ".bin")).string();
                std::ofstream rawOut(filenameRaw, std::ios::binary);
                rawOut.write(reinterpret_cast<char*>(buffer16), buffer.size());
                rawOut.close();
                
                // Calibration of the raaw frames according to the core temperature
                wic->calibrateRawInplace(buffer16, buffer.size() / 2, (coreTemp.status == wic::ResponseStatus::Ok) ? coreTemp.result : 0);

                // Save calibrated data to combination folder
                std::string filenameCal = (comboDir / ("calibrated_" + std::to_string(frame) + ".bin")).string();
                std::ofstream calOut(filenameCal, std::ios::binary);
                calOut.write(reinterpret_cast<char*>(buffer16), buffer.size());
                calOut.close();

                // Convert raw data to Celsius temperatures
                for (size_t idx = 0; idx < buffer.size() / 2; ++idx) {
                    temperatures[idx] = wic::rawToCelsius(buffer16[idx], tempRes);
                }

                // Save temperature data to combination folder
                std::string filenameTemp = (comboDir / ("temperature_" + std::to_string(frame) + ".bin")).string();
                std::ofstream tempOut(filenameTemp, std::ios::binary);
                tempOut.write(reinterpret_cast<char*>(temperatures.data()), temperatures.size() * sizeof(float));
                tempOut.close();

                std::cout << "[INFO] Captured frame " << frame << " for combination " << i << "_" << j << "\n";
            }
        }
    }

    // Reset filter wheels to 0_0 position without capturing frames
    std::cout << "[INFO] Resetting filter wheels to 0_0 position.\n";
    if (!serialPort.sendCommand("ping 0_0", std::chrono::seconds(60))) {
        std::cerr << "[ERROR] Failed to reset filter wheels.\n";
        return 9;
    }

    std::cout << "[INFO] Hyperspectral imaging complete.\n";
    return 0;
}
