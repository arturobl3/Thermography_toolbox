cmake_minimum_required(VERSION 3.18)

project(stream-sync)

find_package(WIC REQUIRED)

add_executable(stream-sync main.cpp)

target_compile_features(stream-sync PUBLIC cxx_std_14)

target_link_libraries(stream-sync PRIVATE WIC::WIC)
