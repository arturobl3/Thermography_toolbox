// Camera setup shared by thermography.cpp and preview.cpp.
#pragma once

#include <wic/wic.h>

#include <chrono>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <thread>

inline constexpr const char* kLens = "019mm";

// Flat-field correction (NUC) with the shutter physically closed. Same sequence as
// thermal_bandpass/scripts/capture_burst.cpp: the camera's own shutter temperature
// reading is a stub, so the FFC reference is the mean of sensor and housing
// temperature. Returns false (with the shutter reopened if possible) on any failure.
inline bool runFlatField(wic::WIC* cam, double& anchorC) {
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
