cmake_minimum_required(VERSION 3.15)
project(uhcr_safety_monitor CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Source files
add_library(safety_monitor SHARED
    safety_monitor.cpp
)

# Platform-specific settings
if(WIN32)
    target_link_libraries(safety_monitor PRIVATE psapi)
    set_target_properties(safety_monitor PROPERTIES
        OUTPUT_NAME "safety_monitor"
        SUFFIX ".dll"
    )
elseif(APPLE)
    set_target_properties(safety_monitor PROPERTIES
        OUTPUT_NAME "safety_monitor"
        SUFFIX ".dylib"
    )
else()
    target_link_libraries(safety_monitor PRIVATE pthread)
    set_target_properties(safety_monitor PROPERTIES
        OUTPUT_NAME "safety_monitor"
        SUFFIX ".so"
    )
endif()

# Installation
install(TARGETS safety_monitor
    LIBRARY DESTINATION ${CMAKE_INSTALL_PREFIX}
    RUNTIME DESTINATION ${CMAKE_INSTALL_PREFIX}
)
