cmake_minimum_required(VERSION 3.18)

project(video-stream)

find_package(WIC REQUIRED)

find_package(OpenCV REQUIRED)

add_executable(video-stream main.cpp)

target_compile_features(video-stream PUBLIC cxx_std_17)

target_link_libraries(video-stream PRIVATE
    WIC::WIC
    ${OpenCV_LIBS}
)

target_include_directories(video-stream PRIVATE ${OpenCV_INCLUDE_DIRS})