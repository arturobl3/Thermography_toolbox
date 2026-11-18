cmake_minimum_required(VERSION 3.18)

project(thermography_acquisition CXX)

find_package(WIC REQUIRED)
find_package(OpenCV QUIET)  # only needed for the live preview

# === thermography: record a sequence and trigger heating ===
add_executable(thermography thermography.cpp)
target_compile_features(thermography PUBLIC cxx_std_17)
target_link_libraries(thermography PRIVATE WIC::WIC)

# === preview: live view (needs OpenCV, e.g. apt install libopencv-dev) ===
if(OpenCV_FOUND)
    add_executable(preview preview.cpp)
    target_compile_features(preview PUBLIC cxx_std_17)
    target_link_libraries(preview PRIVATE WIC::WIC ${OpenCV_LIBS})
    target_include_directories(preview PRIVATE ${OpenCV_INCLUDE_DIRS})
else()
    message(WARNING "OpenCV not found: skipping 'preview'. Install libopencv-dev to build it.")
endif()
