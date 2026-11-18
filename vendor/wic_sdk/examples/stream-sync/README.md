# WIC SDK: stream-sync example
This example demonstrates usage of WIC SDK for streaming from WIC thermal camera.

Before building example, it is required to fill in serial number of camera to `serialNumber` string.

To build example You can use:
```bash
mkdir build && cd build
cmake ..
cmake --build .
```

This should create `build` with `stream-sync` executable in it. To run this example You can use:
```bash
./stream-sync
```