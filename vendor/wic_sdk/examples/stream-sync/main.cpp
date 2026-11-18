#include <wic/calibrationdata.h>
#include <wic/camerafinder.h>
#include <wic/framegrabber.h>
#include <wic/wic.h>

#include <algorithm>
#include <iostream>
#include <vector>

int
main()
{
	auto serialNumber = "332C2309";
	// const std::string serialNumber = "332C2309";
	auto wic = wic::findAndConnect(serialNumber);
	
	if (!wic) {
		std::cerr << "Could not connect WIC" << std::endl;
		return 2;
    }

    auto resolution = wic->getResolution();
    if (resolution.result[0] == 0 || resolution.result[1] == 0) {
		std::cerr << "Invalid resolution, core detection error." << std::endl;
		return 3;
    }

    auto defaultRes = wic->doDefaultWICSettings();
    if (defaultRes.status != wic::ResponseStatus::Ok) {
        std::cerr << "DoDefaultWICSettings: "
                  << wic::responseStatusToStr(defaultRes.status) << std::endl;
        return 4;
    }

    // sensor temp should be polled often
    auto coreTemp =
        wic->getCameraTemperature(wic::CameraTemperature::SensorTemp);
    std::cout << "Sensor temperature: " << coreTemp.result << std::endl;

    std::cout << "Lens: " << wic->getLens() << std::endl;

	// if no lens were detected, set desired lens from license file
	// this may take a few minutes, especially with validateMemory flag on

	auto grabber = wic->frameGrabber();
	grabber->setup();

	// default wic settings = OutputType::RAD14
	// every 2 bytes represent radiometric flux of one pixel
	// buffer is in row major format
	std::vector<uint8_t> buffer;
    buffer.resize(resolution.result[0] * resolution.result[1]* sizeof(uint16_t));

	std::vector<float> temperatures;
    temperatures.resize(resolution.result[0] * resolution.result[1]);

	size_t frame{ 0 };

    auto error = wic::FrameGrabberError::None;

    while (true) {
        grabber->getBuffer(buffer.data(), error, 1000);
        if (error != wic::FrameGrabberError::None) {
            std::cerr << "Buffer error occured." << std::endl;
            return 6;
        }
		auto buffer16 = reinterpret_cast<uint16_t*>(buffer.data());
		// calibrate raw values, does anything only if license was set
        wic->calibrateRawInplace(
            buffer16, buffer.size() / 2, (coreTemp.status == wic::ResponseStatus::Ok) ? coreTemp.result : 0);

		auto tempRes = wic->getCurrentTemperatureResolution();

		for (auto i = 0; i < buffer.size() / 2; i++) {
			temperatures[i] = wic::rawToCelsius(buffer16[i], tempRes);
		}

		auto minmax =
		  std::minmax_element(temperatures.begin(), temperatures.end());

		std::cout << "frame: " << frame++ << " min: " << *minmax.first
				  << " max: " << *minmax.second << std::endl;
	}
}
