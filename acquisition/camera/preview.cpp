// Live view of the WIC camera, calibrated with the license, with focus peaking.
//
// Use it to frame and focus the sample before recording with `thermography`.
// The camera is set up the same way as for a recording (license calibration,
// range, lens, manual NUC with one flat-field correction at startup), so what
// you see here is what gets recorded.
//
// Focus aids:
//   - Focus peaking: pixels whose temperature gradient is above the threshold
//     are painted green. Turn the focus ring until the edges of the sample light
//     up as thin, dense lines. The "peaking %" slider sets the threshold as a
//     percentage of the displayed temperature span per pixel.
//   - Sharpness: RMS temperature gradient of the whole frame in mK/px. It is
//     highest at best focus; "best" holds the maximum seen so far.
//
// Keys: p = peaking on/off, r = reset best sharpness, q / Esc = quit.

#include <wic/calibrationdata.h>
#include <wic/camerafinder.h>
#include <wic/framegrabber.h>
#include <wic/wic.h>

#include "wicsetup.h"

#include <opencv2/highgui.hpp>
#include <opencv2/imgproc.hpp>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

#ifndef WIC_LICENSE_PATH
#define WIC_LICENSE_PATH ""  // set by CMakeLists.txt
#endif

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

namespace {

constexpr const char* kWindow = "preview";
constexpr const char* kPeakingTrackbar = "peaking %";
constexpr int kDefaultPeakingPercent = 15;
constexpr int kSensorTempRefreshFrames = 15;  // re-read sensor temperature this often
constexpr double kDisplayClipFraction = 0.005;  // ignore the coldest/hottest 0.5% when scaling
constexpr double kMinDisplaySpanC = 0.5;        // never stretch less than this over the palette
constexpr double kSharpnessSmoothing = 0.2;     // weight of the newest frame in the average
constexpr double kNearBestFraction = 0.98;      // sharpness shown green when this close to best

struct Options {
    std::string licensePath = WIC_LICENSE_PATH;
    std::string rangeName = "low";
};

void printUsage(const char* prog) {
    std::cerr << "Usage: " << prog << " [low|high] [options]\n"
              << "\n"
              << "Options:\n"
              << "  --range low|high   Temperature range, low = -25..120 C (default: low)\n"
              << "  --license <file>   WIC license (.wlic). Default:\n"
              << "                     " << WIC_LICENSE_PATH << "\n"
              << "\n"
              << "Keys: p = focus peaking on/off, r = reset best sharpness, q / Esc = quit.\n";
}

bool parseArgs(int argc, char* argv[], Options& opt) {
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--help" || arg == "-h") return false;
        if (arg == "low" || arg == "high") {
            opt.rangeName = arg;
        } else if (arg == "--range" || arg == "--license") {
            if (i + 1 >= argc) {
                std::cerr << "[ERROR] " << arg << " needs a value\n";
                return false;
            }
            const std::string value = argv[++i];
            if (arg == "--range") opt.rangeName = value;
            if (arg == "--license") opt.licensePath = value;
        } else {
            std::cerr << "[ERROR] Unknown argument " << arg << "\n";
            return false;
        }
    }
    if (opt.rangeName != "low" && opt.rangeName != "high") {
        std::cerr << "[ERROR] --range must be low or high\n";
        return false;
    }
    if (opt.licensePath.empty()) {
        std::cerr << "[ERROR] No license file: pass --license <file>\n";
        return false;
    }
    return true;
}

// Last mouse position over the window, for the temperature readout.
int mouseX = -1;
int mouseY = -1;

void onMouse(int event, int x, int y, int, void*) {
    if (event == cv::EVENT_MOUSEMOVE) {
        mouseX = x;
        mouseY = y;
    }
}

// The palette as an OpenCV lookup table (OpenCV images are BGR).
cv::Mat paletteLut() {
    cv::Mat lut(256, 1, CV_8UC3);
    for (int i = 0; i < 256; ++i) {
        const color& c = BWIron1Plt[i];
        lut.at<cv::Vec3b>(i) = cv::Vec3b(c.b, c.g, c.r);
    }
    return lut;
}

// Temperature span to map onto the palette, ignoring a few outlier pixels so a
// hot spot elsewhere in the view doesn't flatten the contrast of the sample.
std::pair<double, double> displayRange(const std::vector<float>& temps,
                                       std::vector<float>& scratch) {
    scratch = temps;
    const size_t lo = static_cast<size_t>(scratch.size() * kDisplayClipFraction);
    const size_t hi = scratch.size() - 1 - lo;
    std::nth_element(scratch.begin(), scratch.begin() + lo, scratch.end());
    const double low = scratch[lo];
    std::nth_element(scratch.begin() + lo, scratch.begin() + hi, scratch.end());
    const double high = scratch[hi];
    if (high - low >= kMinDisplaySpanC) return {low, high};
    const double mid = (low + high) / 2.0;
    return {mid - kMinDisplaySpanC / 2.0, mid + kMinDisplaySpanC / 2.0};
}

std::string fixed(double value, int decimals) {
    std::ostringstream out;
    out << std::fixed << std::setprecision(decimals) << value;
    return out.str();
}

// Text with a dark outline, readable on any part of the palette.
void drawText(cv::Mat& img, const std::string& text, int line,
              const cv::Scalar& colorBgr = cv::Scalar(255, 255, 255)) {
    const cv::Point org(8, 20 + 20 * line);
    cv::putText(img, text, org, cv::FONT_HERSHEY_SIMPLEX, 0.5, cv::Scalar(0, 0, 0), 3,
                cv::LINE_AA);
    cv::putText(img, text, org, cv::FONT_HERSHEY_SIMPLEX, 0.5, colorBgr, 1, cv::LINE_AA);
}

}  // namespace

int main(int argc, char* argv[]) {
    Options opt;
    if (!parseArgs(argc, argv, opt)) {
        printUsage(argv[0]);
        return 1;
    }

    // --- Connect with the license, so calibrateRawInplace actually calibrates ---
    wic::LicenseFile license(opt.licensePath.c_str());
    if (!license.isOk()) {
        std::cerr << "[ERROR] Could not load license file " << opt.licensePath << "\n";
        return 2;
    }
    wic::WIC* cam = wic::findAndConnect(license);
    if (!cam || !cam->connected()) {
        std::cerr << "[ERROR] Could not connect to WIC " << license.serialNumber() << ".\n";
        return 2;
    }
    std::cout << "[INFO] Connected to WIC " << license.serialNumber() << "\n";

    if (cam->doDefaultWICSettings().status != wic::ResponseStatus::Ok) {
        std::cerr << "[ERROR] Failed to apply default settings.\n";
        return 4;
    }

    const wic::Range range = (opt.rangeName == "high") ? wic::Range::High : wic::Range::Low;
    auto rangeRes = cam->setRangeAndLens(range, kLens);
    if (!rangeRes.isOk()) {
        std::cerr << "[ERROR] Failed to set range " << opt.rangeName << " / lens " << kLens << ": "
                  << wic::responseStatusToStr(rangeRes.status) << "\n";
        return 4;
    }
    if (rangeRes.result > 0) {
        std::cerr << "[WARN] " << rangeRes.result
                  << " errors in the camera's correction data; check frames for artifacts\n";
    }
    const auto tempRes = cam->getCurrentTemperatureResolution();  // must follow setRangeAndLens
    std::cout << "[INFO] Range " << opt.rangeName << ", lens " << kLens << "\n";

    auto resolution = cam->getResolution();
    const int width = resolution.result[0];
    const int height = resolution.result[1];
    if (!resolution.isOk() || width <= 0 || height <= 0) {
        std::cerr << "[ERROR] Invalid resolution.\n";
        return 3;
    }

    // --- NUC: manual mode, one flat-field correction, shutter open afterwards ---
    if (!cam->setNUCUpdateMode(wic::NUCUpdateModes::Manual).isOk()) {
        std::cerr << "[ERROR] Failed to set manual NUC mode.\n";
        return 4;
    }
    if (cam->setIntegratedNUCUpdateFrames(wic::IntegratedNUCUpdateFrames::Frames16) !=
        wic::ResponseStatus::Ok) {
        std::cerr << "[ERROR] Failed to set integrated NUC frames.\n";
        return 4;
    }
    std::cout << "[INFO] Flat-field correction: the shutter closes for about 5 s\n";
    double ffcAnchorC = NAN;
    if (!runFlatField(cam, ffcAnchorC)) {
        return 4;
    }

    auto sensorRead = cam->getCameraTemperature(wic::CameraTemperature::SensorTemp);
    double sensorTempC = sensorRead.isOk() ? sensorRead.result : 0.0;
    if (!sensorRead.isOk()) {
        std::cerr << "[WARN] Could not read sensor temperature; calibrating with 0 C until it "
                     "can be read\n";
    }

    // --- Window ---
    cv::namedWindow(kWindow, cv::WINDOW_AUTOSIZE);
    cv::setMouseCallback(kWindow, onMouse);
    cv::createTrackbar(kPeakingTrackbar, kWindow, nullptr, 100);
    cv::setTrackbarMin(kPeakingTrackbar, kWindow, 1);
    cv::setTrackbarPos(kPeakingTrackbar, kWindow, kDefaultPeakingPercent);

    // --- Capture loop ---
    auto grabber = cam->frameGrabber();
    grabber->setup();
    std::vector<uint16_t> buffer(static_cast<size_t>(width) * height);
    std::vector<float> temps(buffer.size());
    std::vector<float> scratch;
    const cv::Mat tempMat(height, width, CV_32F, temps.data());  // view of temps, no copy
    const cv::Mat lut = paletteLut();
    cv::Mat gray8, image, blurred, gx, gy, gradient;

    bool peaking = true;
    double sharpness = -1.0;  // mK/px, smoothed over frames; < 0 until the first frame
    double bestSharpness = 0.0;
    int exitCode = 0;

    for (int frame = 0;; ++frame) {
        wic::FrameGrabberError error;
        grabber->getBuffer(reinterpret_cast<uint8_t*>(buffer.data()), error, 5000);
        if (error != wic::FrameGrabberError::None) {
            std::cerr << "[ERROR] Frame grabber error at frame " << frame << ".\n";
            exitCode = 6;
            break;
        }

        if (frame % kSensorTempRefreshFrames == 0) {
            auto s = cam->getCameraTemperature(wic::CameraTemperature::SensorTemp);
            if (s.isOk()) sensorTempC = s.result;
        }
        cam->calibrateRawInplace(buffer.data(), buffer.size(), sensorTempC);
        for (size_t i = 0; i < buffer.size(); ++i) {
            temps[i] = static_cast<float>(wic::rawToCelsius(buffer[i], tempRes));
        }

        // Color image
        const auto [lowC, highC] = displayRange(temps, scratch);
        const double spanC = highC - lowC;
        tempMat.convertTo(gray8, CV_8U, 255.0 / spanC, -lowC * 255.0 / spanC);
        cv::applyColorMap(gray8, image, lut);

        // Temperature gradient in C per pixel. The light blur keeps sensor noise
        // from showing up as peaking; the 1/8 turns the Sobel response into C/px.
        cv::GaussianBlur(tempMat, blurred, cv::Size(3, 3), 0);
        cv::Sobel(blurred, gx, CV_32F, 1, 0, 3, 1.0 / 8.0);
        cv::Sobel(blurred, gy, CV_32F, 0, 1, 3, 1.0 / 8.0);
        cv::magnitude(gx, gy, gradient);

        const double rmsGradientMk = std::sqrt(cv::mean(gradient.mul(gradient))[0]) * 1000.0;
        sharpness = (sharpness < 0) ? rmsGradientMk
                                    : (1.0 - kSharpnessSmoothing) * sharpness +
                                          kSharpnessSmoothing * rmsGradientMk;
        bestSharpness = std::max(bestSharpness, sharpness);

        const int peakingPercent = cv::getTrackbarPos(kPeakingTrackbar, kWindow);
        if (peaking) {
            const cv::Mat edges = gradient > (peakingPercent / 100.0) * spanC;
            image.setTo(cv::Scalar(0, 255, 0), edges);
        }

        // Overlay
        const bool nearBest = sharpness >= kNearBestFraction * bestSharpness;
        drawText(image,
                 "sharpness " + fixed(sharpness, 0) + " mK/px   best " + fixed(bestSharpness, 0),
                 0, nearBest ? cv::Scalar(0, 255, 0) : cv::Scalar(255, 255, 255));
        drawText(image,
                 "display " + fixed(lowC, 1) + " .. " + fixed(highC, 1) + " C   sensor " +
                     fixed(sensorTempC, 1) + " C",
                 1);
        if (mouseX >= 0 && mouseX < width && mouseY >= 0 && mouseY < height) {
            drawText(image,
                     "(" + std::to_string(mouseX) + ", " + std::to_string(mouseY) + ")  " +
                         fixed(temps[static_cast<size_t>(mouseY) * width + mouseX], 2) + " C",
                     2);
        }
        drawText(image,
                 std::string("peaking ") + (peaking ? std::to_string(peakingPercent) + "%" : "off") +
                     "   p: peaking  r: reset best  q: quit",
                 (height - 28) / 20);

        cv::imshow(kWindow, image);
        const int key = cv::waitKey(1) & 0xFF;
        if (key == 'q' || key == 27) break;
        if (key == 'p') peaking = !peaking;
        if (key == 'r') bestSharpness = sharpness;
        if (cv::getWindowProperty(kWindow, cv::WND_PROP_VISIBLE) < 1) break;  // window closed
    }
    cv::destroyAllWindows();
    return exitCode;
}
