# WIC SDK: multi-stream example
This example demonstrates usage of WIC SDK for parallel streaming from several WIC thermal cameras.

Before building example, it is required to fill in serial numbers of cameras to `serialNumbers` vector.

To build example You can use:
```bash
mkdir build && cd build
cmake ..
cmake --build .
```

This should create `build` with `multi-stream` executable in it. To run this example You can use:
```bash
./multi-stream
```