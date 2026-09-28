cmake_minimum_required(VERSION 3.16)

project(towel LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_C_STANDARD 11)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# Executable goes into the build directory
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})

# ONNX Runtime
set(ONNXRUNTIME_ROOT "/home/srivatsa/onnxruntime-linux-x64-gpu-1.19.2")

# OpenCV
find_package(OpenCV REQUIRED)

set(SOURCES
    main.cpp
    src/ctpat.cpp

    utils/main_config_utils.c

    bytetrack/src/BYTETracker.cpp
    bytetrack/src/STrack.cpp
    bytetrack/src/kalmanFilter.cpp
    bytetrack/src/utils.cpp
    bytetrack/src/lapjv.cpp

    db/src/db.c
    routes/routes.c
)

add_executable(towel ${SOURCES})
target_compile_definitions(towel PRIVATE PROJECT_ROOT="${CMAKE_SOURCE_DIR}")

target_include_directories(towel PRIVATE
    ${CMAKE_SOURCE_DIR}/src
    ${CMAKE_SOURCE_DIR}/bytetrack/include
    ${CMAKE_SOURCE_DIR}/db/src
    ${CMAKE_SOURCE_DIR}/routes
    ${CMAKE_SOURCE_DIR}/utils
    /usr/include/eigen3
    ${ONNXRUNTIME_ROOT}/include
    ${OpenCV_INCLUDE_DIRS}
)

target_link_directories(towel PRIVATE ${ONNXRUNTIME_ROOT}/lib)

target_link_libraries(towel PRIVATE
    ${OpenCV_LIBS}
    onnxruntime
    sqlite3
    microhttpd
    cjson
    pthread
    m
)

set_target_properties(towel PROPERTIES
    BUILD_RPATH   "${ONNXRUNTIME_ROOT}/lib"
    INSTALL_RPATH "${ONNXRUNTIME_ROOT}/lib"
)