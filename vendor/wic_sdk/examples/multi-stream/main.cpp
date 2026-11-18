#include <wic/calibrationdata.h>
#include <wic/camerafinder.h>
#include <wic/framegrabber.h>
#include <wic/wic.h>

#include <algorithm>
#include <iostream>
#include <vector>
#include <thread>
#include <csignal>
#include <atomic>
#include <chrono> 

std::atomic<bool> runFlag;

void connectAndStream(const char* serialNumber)
{
	auto wic = wic::findAndConnect(serialNumber);
	if (!wic)
	{
		std::cerr << "Could not connect WIC " << serialNumber << std::endl;
		return;
    }

    auto resolution = wic->getResolution();
    if (resolution.result[0] == 0 || resolution.result[1] == 0)
	{
		std::cerr << serialNumber << ": Invalid resolution, core detection error." << std::endl;
		return;
    }

    auto defaultRes = wic->doDefaultWICSettings();
    if (defaultRes.status != wic::ResponseStatus::Ok)
	{
        std::cerr << serialNumber << ": DoDefaultWICSettings: " << wic::responseStatusToStr(defaultRes.status) << std::endl;
        return;
    }

    // sensor temp should be polled often
    auto coreTemp = wic->getCameraTemperature(wic::CameraTemperature::SensorTemp);
    std::cout << serialNumber << ": Sensor temperature: " << coreTemp.result << std::endl;
    std::cout << serialNumber << ": Lens: " << wic->getLens() << std::endl;
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

    auto error = wic::FrameGrabberError::None;
	auto lastFrameTime = std::chrono::high_resolution_clock::now();
	int errorCount = 0;
    while (runFlag) 
	{
        grabber->getBuffer(buffer.data(), error, 1000);
        if (error != wic::FrameGrabberError::None) 
		{
            std::cerr << serialNumber << ": Buffer error occured: " << std::to_string(static_cast<int>(error)) << std::endl;
			++errorCount;
			if (errorCount > 10)
			{
				std::cerr << serialNumber << ": Too many buffer errors. Terminating" << std::endl;
				return; 
			}
            continue;
        }
		errorCount = 0;

		auto buffer16 = reinterpret_cast<uint16_t*>(buffer.data());
        wic->calibrateRawInplace(buffer16, buffer.size() / sizeof(uint16_t), (coreTemp.status == wic::ResponseStatus::Ok) ? coreTemp.result : 0);

		auto tempRes = wic->getCurrentTemperatureResolution();

		for (auto i = 0; i < buffer.size() / sizeof(uint16_t); i++) 
		{
			temperatures[i] = wic::rawToCelsius(buffer16[i], tempRes);
		}

		auto minmax = std::minmax_element(temperatures.begin(), temperatures.end());

		auto minPosition = std::distance(temperatures.begin(), minmax.first);
		auto minPositionX = minPosition % resolution.result[1];
		auto minPositionY = minPosition / resolution.result[1];

		auto maxPosition = std::distance(temperatures.begin(), minmax.second);
		auto maxPositionX = maxPosition % resolution.result[1];
		auto maxPositionY = maxPosition / resolution.result[1];

		auto now = std::chrono::high_resolution_clock::now();
		int duration = std::chrono::duration_cast<std::chrono::milliseconds>(now - lastFrameTime).count();
		double fps = 1000.0 / duration;
		lastFrameTime = now;

		std::cout << serialNumber << ": minimum: " << *minmax.first << " [" << minPositionX << ", " << minPositionY << "]" 
								  <<  " maximum: " << *minmax.second << " [" << maxPositionX << ", " << maxPositionY << "]" 
								  << " (t = " << duration << " ms, FPS = " << fps<< ")"
								  << std::endl;
	}
	
}

int main(int argc, char** argv)
{
	runFlag = true;
	const auto terminationFunction = [](int signal)
	{
		runFlag = false;
	};	
	std::signal(SIGTERM, terminationFunction);
	std::signal(SIGINT, terminationFunction);
	std::signal(SIGABRT, terminationFunction);

	const std::vector<const char*> serialNumbers = {""};
	std::vector<std::thread> threads;
	for (const auto& serialNumber : serialNumbers)
	{
		threads.push_back(std::thread(&connectAndStream, serialNumber));
	}
	for (auto& thread : threads)
	{
		thread.join();
	}
}
