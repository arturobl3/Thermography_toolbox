cmake_minimum_required(VERSION 3.18)

project(thermography_acquisition CXX)

find_package(WIC REQUIRED)
find_package(OpenCV QUIET)  # only needed for the live preview

# === thermography: record a sequence and trigger heating ===
add_executable(thermography thermography.cpp)
target_compile_features(thermography PUBLIC cxx_std_17)
target_link_libraries(thermography PRIVATE WIC::WIC)
# Default license file, so the program finds it from any working directory
get_filename_component(WIC_LICENSE_PATH
    "${CMAKE_CURRENT_SOURCE_DIR}/../../vendor/wic_sdk/license 332C2309.wlic" ABSOLUTE)
# Default output folder for recordings: <repo>/data (gitignored)
get_filename_component(DATA_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../data" ABSOLUTE)
target_compile_definitions(thermography PRIVATE
    WIC_LICENSE_PATH="${WIC_LICENSE_PATH}"
    DATA_DIR="${DATA_DIR}")

# === preview: live view (needs OpenCV, e.g. apt install libopencv-dev) ===
if(OpenCV_FOUND)
    add_executable(preview preview.cpp)
    target_compile_features(preview PUBLIC cxx_std_17)
    target_link_libraries(preview PRIVATE WIC::WIC ${OpenCV_LIBS})
    target_include_directories(preview PRIVATE ${OpenCV_INCLUDE_DIRS})
else()
    message(WARNING "OpenCV not found: skipping 'preview'. Install libopencv-dev to build it.")
endif()
