# WIC SDK: video-stream example
This example demonstrates usage of WIC SDK for streaming from WIC thermal camera.

Before building example, it is required to fill in serial number of camera to `serialNumber` string.

This example uses [OpenCV](https://opencv.org/) for visualization. It is required to have OpenCV installed before building this example.

To build example You can use:
```bash
mkdir build && cd build
cmake ..
cmake --build .
```

This should create `build` with `video-stream` executable in it. To run this example You can use:
```bash
./video-stream
```