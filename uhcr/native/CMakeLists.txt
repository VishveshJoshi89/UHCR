cmake_minimum_required(VERSION 3.15)
project(UHCR_Safety LANGUAGES CXX)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Compiler flags for safety and optimization
if(MSVC)
    add_compile_options(/W4 /WX /O2 /Oi /Ot /GL /GS)
    add_link_options(/LTCG /OPT:REF /OPT:ICF)
else()
    add_compile_options(-Wall -Wextra -Werror -O3 -march=native -fstack-protector-strong)
    add_compile_options(-fno-strict-overflow -fwrapv)
endif()

# Enable security features
add_definitions(-D_FORTIFY_SOURCE=2)

# Safety checker library
add_library(uhcr_safety SHARED
    safety_checker.cpp
    safety_checker.hpp
)

# Set output directory
set_target_properties(uhcr_safety PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
)

# Install target
install(TARGETS uhcr_safety
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION bin
)

# Optional: Build test executable
option(BUILD_TESTS "Build test executable" OFF)

if(BUILD_TESTS)
    add_executable(safety_test
        safety_test.cpp
        safety_checker.cpp
    )
    
    target_link_libraries(safety_test uhcr_safety)
endif()
