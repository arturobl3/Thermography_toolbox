cmake_minimum_required(VERSION 3.18)

project(main_operation)

find_package(WIC REQUIRED)
find_package(OpenCV REQUIRED)

# === preview ===
add_executable(preview preview.cpp)
target_compile_features(preview PUBLIC cxx_std_17)
target_link_libraries(preview PRIVATE WIC::WIC ${OpenCV_LIBS})
target_include_directories(preview PRIVATE ${OpenCV_INCLUDE_DIRS})

# === thermography ===
add_executable(thermography thermography.cpp)
target_compile_features(thermography PUBLIC cxx_std_17)
target_link_libraries(thermography PRIVATE WIC::WIC ${OpenCV_LIBS})
target_include_directories(thermography PRIVATE ${OpenCV_INCLUDE_DIRS})

# === hyperspectral ===
add_executable(hyperspectral hyperspectral.cpp)
target_compile_features(hyperspectral PUBLIC cxx_std_17)
target_link_libraries(hyperspectral PRIVATE WIC::WIC ${OpenCV_LIBS})
target_include_directories(hyperspectral PRIVATE ${OpenCV_INCLUDE_DIRS})
