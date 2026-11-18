cmake_minimum_required(VERSION 3.18)

project(multi-stream)

find_package(WIC REQUIRED)
find_package(Threads REQUIRED)

add_executable(multi-stream main.cpp)

target_compile_features(multi-stream PUBLIC cxx_std_14)

target_link_libraries(multi-stream PRIVATE 
    WIC::WIC
    Threads::Threads
)
