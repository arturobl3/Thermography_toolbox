#include <wic/calibrationdata.h>
#include <wic/camerafinder.h>
#include <wic/framegrabber.h>
#include <wic/wic.h>

#include <opencv2/highgui.hpp>
#include <opencv2/opencv.hpp>

#include <algorithm>
#include <iostream>
#include <string>
#include <vector>


#include <fcntl.h>
#include <termios.h>
#include <unistd.h>
#include <cstring>


// Color mapping structure for the video stream
struct color {
    uint8_t r, g, b;
};

static constexpr std::array<color, 256> BWIron1Plt = {
	{ { 255, 255, 255 }, { 253, 253, 253 }, { 251, 251, 251 },
	  { 249, 249, 249 }, { 247, 247, 247 }, { 245, 245, 245 },
	  { 244, 243, 243 }, { 241, 241, 241 }, { 239, 239, 240 },
	  { 237, 237, 237 }, { 235, 235, 235 }, { 233, 233, 233 },
	  { 231, 231, 232 }, { 230, 229, 229 }, { 227, 228, 227 },
	  { 225, 225, 225 }, { 223, 223, 224 }, { 221, 221, 221 },
	  { 219, 220, 219 }, { 217, 218, 218 }, { 216, 216, 215 },
	  { 213, 214, 214 }, { 212, 211, 211 }, { 209, 209, 209 },
	  { 208, 207, 207 }, { 205, 205, 205 }, { 204, 204, 203 },
	  { 202, 201, 201 }, { 199, 199, 199 }, { 197, 197, 197 },
	  { 195, 195, 196 }, { 193, 193, 193 }, { 191, 192, 191 },
	  { 189, 190, 189 }, { 188, 187, 188 }, { 186, 185, 185 },
	  { 183, 183, 184 }, { 182, 182, 181 }, { 180, 180, 180 },
	  { 178, 178, 177 }, { 175, 176, 176 }, { 174, 174, 174 },
	  { 172, 172, 172 }, { 169, 170, 169 }, { 168, 168, 167 },
	  { 165, 165, 165 }, { 164, 163, 164 }, { 162, 161, 161 },
	  { 159, 160, 159 }, { 158, 157, 158 }, { 155, 155, 155 },
	  { 153, 153, 154 }, { 152, 152, 151 }, { 150, 149, 150 },
	  { 148, 148, 148 }, { 145, 146, 146 }, { 144, 144, 143 },
	  { 141, 141, 141 }, { 140, 140, 139 }, { 137, 138, 138 },
	  { 136, 135, 136 }, { 134, 133, 134 }, { 132, 132, 132 },
	  { 130, 130, 130 }, { 128, 128, 128 }, { 126, 126, 126 },
	  { 124, 124, 124 }, { 122, 122, 122 }, { 120, 120, 120 },
	  { 118, 118, 118 }, { 116, 116, 116 }, { 114, 114, 114 },
	  { 112, 112, 112 }, { 110, 110, 110 }, { 108, 108, 108 },
	  { 106, 106, 106 }, { 104, 104, 104 }, { 102, 102, 102 },
	  { 100, 100, 100 }, { 98, 98, 98 },	{ 96, 96, 96 },
	  { 94, 95, 94 },	 { 92, 93, 92 },	{ 90, 90, 90 },
	  { 88, 88, 88 },	 { 86, 86, 86 },	{ 85, 84, 85 },
	  { 83, 82, 82 },	 { 80, 80, 80 },	{ 78, 78, 79 },
	  { 76, 76, 76 },	 { 74, 74, 75 },	{ 72, 73, 72 },
	  { 70, 70, 70 },	 { 68, 68, 68 },	{ 66, 66, 66 },
	  { 64, 64, 64 },	 { 63, 62, 62 },	{ 60, 60, 60 },
	  { 56, 56, 56 },	 { 52, 52, 52 },	{ 49, 50, 50 },
	  { 46, 47, 46 },	 { 44, 44, 44 },	{ 41, 41, 41 },
	  { 38, 39, 39 },	 { 38, 38, 38 },	{ 37, 37, 37 },
	  { 36, 36, 36 },	 { 34, 35, 35 },	{ 34, 35, 34 },
	  { 34, 34, 34 },	 { 33, 33, 33 },	{ 31, 31, 32 },
	  { 31, 31, 31 },	 { 31, 30, 31 },	{ 30, 30, 30 },
	  { 28, 28, 29 },	 { 27, 27, 27 },	{ 27, 26, 27 },
	  { 26, 26, 26 },	 { 24, 24, 25 },	{ 23, 23, 24 },
	  { 23, 23, 24 },	 { 22, 22, 23 },	{ 21, 20, 22 },
	  { 20, 20, 22 },	 { 18, 18, 20 },	{ 17, 16, 20 },
	  { 15, 14, 20 },	 { 14, 14, 21 },	{ 12, 12, 22 },
	  { 11, 10, 23 },	 { 9, 8, 25 },		{ 8, 8, 28 },
	  { 7, 6, 32 },		 { 6, 5, 35 },		{ 6, 4, 40 },
	  { 5, 4, 45 },		 { 6, 3, 51 },		{ 6, 2, 55 },
	  { 6, 2, 61 },		 { 6, 2, 68 },		{ 7, 1, 74 },
	  { 7, 0, 77 },		 { 8, 0, 84 },		{ 8, 0, 90 },
	  { 11, 0, 95 },	 { 13, 0, 99 },		{ 15, 0, 105 },
	  { 17, 0, 110 },	 { 22, 0, 115 },	{ 28, 0, 120 },
	  { 35, 0, 127 },	 { 40, 0, 130 },	{ 46, 0, 135 },
	  { 59, 0, 141 },	 { 70, 0, 146 },	{ 80, 0, 148 },
	  { 90, 0, 151 },	 { 104, 0, 155 },	{ 115, 0, 157 },
	  { 122, 0, 157 },	 { 125, 0, 157 },	{ 132, 0, 157 },
	  { 139, 0, 157 },	 { 146, 0, 156 },	{ 146, 0, 156 },
	  { 152, 0, 155 },	 { 157, 0, 155 },	{ 162, 0, 155 },
	  { 166, 0, 155 },	 { 170, 0, 153 },	{ 174, 1, 153 },
	  { 180, 2, 150 },	 { 182, 2, 149 },	{ 183, 4, 149 },
	  { 186, 4, 149 },	 { 190, 6, 147 },	{ 192, 6, 145 },
	  { 194, 9, 144 },	 { 196, 12, 141 },	{ 201, 17, 135 },
	  { 201, 18, 135 },	 { 203, 20, 132 },	{ 205, 22, 129 },
	  { 208, 26, 122 },	 { 209, 28, 118 },	{ 212, 33, 112 },
	  { 213, 36, 106 },	 { 216, 41, 98 },	{ 220, 48, 84 },
	  { 222, 51, 74 },	 { 224, 54, 61 },	{ 224, 56, 54 },
	  { 225, 58, 50 },	 { 228, 65, 29 },	{ 230, 68, 26 },
	  { 231, 73, 20 },	 { 232, 76, 17 },	{ 232, 76, 16 },
	  { 234, 78, 13 },	 { 235, 82, 11 },	{ 236, 86, 8 },
	  { 237, 88, 8 },	 { 238, 92, 6 },	{ 239, 97, 4 },
	  { 240, 100, 3 },	 { 240, 101, 3 },	{ 241, 104, 3 },
	  { 242, 109, 1 },	 { 242, 109, 1 },	{ 244, 114, 1 },
	  { 244, 116, 0 },	 { 245, 123, 0 },	{ 245, 125, 0 },
	  { 246, 128, 0 },	 { 247, 133, 0 },	{ 248, 135, 0 },
	  { 248, 137, 0 },	 { 249, 141, 0 },	{ 249, 143, 0 },
	  { 251, 150, 0 },	 { 251, 154, 0 },	{ 252, 155, 0 },
	  { 253, 165, 0 },	 { 253, 168, 0 },	{ 253, 168, 0 },
	  { 253, 172, 0 },	 { 254, 178, 0 },	{ 254, 184, 0 },
	  { 254, 184, 0 },	 { 254, 187, 0 },	{ 254, 190, 0 },
	  { 254, 194, 0 },	 { 254, 197, 0 },	{ 254, 201, 1 },
	  { 254, 203, 2 },	 { 254, 205, 2 },	{ 254, 209, 6 },
	  { 254, 213, 10 },	 { 254, 216, 12 },	{ 255, 219, 16 },
	  { 255, 221, 22 },	 { 255, 224, 32 },	{ 255, 227, 38 },
	  { 255, 229, 48 },	 { 255, 232, 60 },	{ 255, 232, 63 },
	  { 255, 234, 71 },	 { 255, 237, 90 },	{ 255, 239, 102 },
	  { 255, 240, 107 }, { 255, 242, 119 }, { 255, 243, 144 },
	  { 255, 245, 166 } }
};


// Pointer to the camera object
wic::WIC* cam{ nullptr };
std::pair<int, int> resolution;

cv::Mat mx_color;

// Vectors for storing raw and temperatures values
std::vector<uint16_t> bufferRAW;
std::vector<float> bufferTemp;


// Function to print on mouse hover over camera video stream
void mouseCallback(int event, int x, int y, int flags, void* userData) {
    // Function for mouse hover interaction with the video stream
    if (event != cv::EVENT_MOUSEMOVE)
        return;
    if ((y * resolution.first + x) >= bufferRAW.size())
        return;
    std::cout << "mouse(" << x << "," << y << ") - Raw values: "
              << bufferRAW.at(y * resolution.first + x) << " Temperature: "
              << bufferTemp.at(y * resolution.first + x) << std::endl;
}

// Function to formulate matrix from frame
template <typename T>
void matFromFrame(const std::vector<T>& data, cv::Mat& mx) {
    auto k = 0;
    for (int i = 0; i < mx.rows; i++) {
        for (int j = 0; j < mx.cols; j++) {
            mx.at<T>(i, j) = data[k];
            k++;
        }
    }
}

// Function to overlay color mapping over video stream
void colorMat(const std::vector<float>& data, cv::Mat& mx) {
    auto minmax = std::minmax_element(std::cbegin(data), std::cend(data));
    auto min = *minmax.first;
    auto max = *minmax.second;
    auto step = (max - min) / 256.f;

    auto k = 0;
    for (int i = 0; i < mx.rows; i++) {
        for (int j = 0; j < mx.cols; j++) {
            int index = (data[k] - min) / step;
            index = std::clamp(index, 0, 255);
            auto color = BWIron1Plt[index];

            mx.at<cv::Vec3b>(i, j)[0] = color.r;
            mx.at<cv::Vec3b>(i, j)[1] = color.g;
            mx.at<cv::Vec3b>(i, j)[2] = color.b;

            k++;
        }
    }
}



// Handler of camera raw input which transform and print raw and temperature values while streaming camera feed
void bufferHandler(std::vector<uint16_t>& data, float temp, int delay) {
    bufferRAW.resize(data.size());
    bufferRAW = data;

    cam->calibrateRawInplace(bufferRAW.data(), bufferRAW.size(), temp);
    auto resolution = cam->getCurrentTemperatureResolution();

    bufferTemp.clear();

    std::transform(std::cbegin(bufferRAW), std::cend(bufferRAW), std::back_inserter(bufferTemp),
                   [tlin = resolution](uint16_t r) { return wic::rawToCelsius(r, tlin); });

    colorMat(bufferTemp, mx_color);

    cv::imshow("camera", mx_color);
    cv::waitKey(delay);
}

// Setting camera range, low range indicate higier resolution, while high range indicate lower resolution
int setCameraRange(const std::string& range) {
    if (!cam) {
        std::cerr << "Camera not initialized properly!" << std::endl;
        return -1;
    }

    wic::Range camRange;
    if (range == "high") {
        camRange = wic::Range::High;
    } else if (range == "low") {
        camRange = wic::Range::Low;
    } else {
        std::cerr << "Invalid range specified. Please use 'high' or 'low'." << std::endl;
        return -1;
    }

    auto res = cam->setRange(camRange);
    if (res != wic::ResponseStatus::Ok) {
        std::cerr << "Failed to set range." << std::endl;
        return -1;
    }
    std::cout << "Thermal range set to: " << range << std::endl;
    return 0;
}

int main(int argc, char* argv[]) {
    // Default to low thermal range unless user explicitly requests high
    std::string rangeInput = "low";
    
    // Check command line arguments for thermal range
    if (argc > 1) {
        std::string arg = argv[1];
        if (arg == "high" || arg == "--high" || arg == "-h") {
            rangeInput = "high";
        } else if (arg == "low" || arg == "--low" || arg == "-l") {
            rangeInput = "low";
        } else if (arg == "--help") {
            std::cout << "Usage: " << argv[0] << " [thermal_range]" << std::endl;
            std::cout << "  thermal_range: 'high' or 'low' (default: low)" << std::endl;
            std::cout << "  Options:" << std::endl;
            std::cout << "    high, --high, -h  : Use high thermal range (lower resolution)" << std::endl;
            std::cout << "    low, --low, -l    : Use low thermal range (higher resolution, default)" << std::endl;
            return 0;
        } else {
            std::cerr << "Invalid argument: " << arg << std::endl;
            std::cout << "Use --help for usage information" << std::endl;
            return 1;
        }
    }

    // Connecting to the camera through its serial number, do not require license file
    auto serialNumber = "332C2309";
    cam = wic::findAndConnect(serialNumber);

     if (!cam) {
        std::cerr << "Camera connection failed!" << std::endl;
        return 1;
    }
    if (!cam->connected()) {
        std::cerr << "Camera not connected!" << std::endl;
        return 2;
    }

    // Camera defoult settings initialization
    auto wicDefaultRes = cam->doDefaultWICSettings();
    std::cout << "doDefaultWIC settings: "
              << wic::responseStatusToStr(wicDefaultRes.status) <<std::endl;

    // NUC update of the camera
    cam->doNUCUpdate();
    std::cout << "Frame rate of the camera: ";
    std::cout << cam->getSpeed() << std::endl;  // Depicts speed of the camera

    // Set camera thermal range (defaulting to low unless specified)
    std::cout << "Using thermal range: " << rangeInput << std::endl;

    // Ensure the range setting is valid
    if (setCameraRange(rangeInput) != 0) {
        return 1;
    }
    
    std::cout << "Range: " << static_cast<int>(cam->getRange()) << std::endl;  // Display camera range

    // Set camera resolution and display window
    resolution = std::make_pair(cam->getResolution().result[0], cam->getResolution().result[1]);
    mx_color = cv::Mat(resolution.second, resolution.first, CV_8UC3);

    cv::namedWindow("camera");
    cv::setMouseCallback("camera", mouseCallback, nullptr);

    // Frame grabber setup
    auto grabber = cam->frameGrabber();
    grabber->setup();

    // Variable holding raw values of the camera
    std::vector<uint16_t> buffer;
    buffer.resize(grabber->getRequiredBufferSize() / 2);

    // Camera core temperature for calibration of raw data
    auto coreTemp = cam->getCameraTemperature(wic::CameraTemperature::SensorTemp);

    wic::FrameGrabberError error;

    // Main loop which grabs raw data from the camera and show them in video stream 
    while (true) {
        grabber->getBuffer(reinterpret_cast<uint8_t*>(buffer.data()), error, 5000);
        if (error != wic::FrameGrabberError::None) {
            std::cerr << "getBuffer ended with error" << std::endl;
            break;
        }
        bufferHandler(buffer, coreTemp.result, 1000 / 60);
    }
}
