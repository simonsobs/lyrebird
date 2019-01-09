#
# Top-level CMakeLists.txt for Lyrebird.
#

cmake_minimum_required (VERSION 2.8)
project (Lyrebird)

# If you want to only build the client library, adjust LYREBIRD_BUILD_VIS
# to "no", or something else that is not "yes".  E.g.
#    cmake -D
set(LYREBIRD_BUILD_VIS "yes"
    CACHE STRING "Set to 'yes' to build the visualization server.")

# Useful cmake helper functions should be defined in ./cmake/
set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} "${CMAKE_SOURCE_DIR}/cmake")

# Common C++ flags
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++11")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -Wno-unused -Werror")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-sign-compare")  # Needed for spt3g.

# Both the client library and the visualizer require spt3g and its
# dependencies (especially boost).
find_package(Spt3g REQUIRED)

# On systems with python2 and python3, help the user find the right
# libraries.  If it's choosing the wrong one, set the variable
# USE_PYTHON_MAJOR=2 or USE_PYTHON_MAJOR=3 when invoking cmake (or by
# adjusting CMakeCache.txt).

message("Python version configuration:")
find_package(PythonInterp)
find_package(PythonLibs)
message("-- System defaults to python${PYTHON_VERSION_MAJOR}")

set(USE_PYTHON_MAJOR ${PYTHON_VERSION_MAJOR}
    CACHE STRING "Set to 2 or 3 to pick your favorite Python.")
message("-- But we will configure boost for python${USE_PYTHON_MAJOR}")

find_package(Boost COMPONENTS
    python${USE_PYTHON_MAJOR} numpy${USE_PYTHON_MAJOR}
    serialization iostreams filesystem REQUIRED)

include_directories(${Boost_INCLUDE_DIR} ${PYTHON_INCLUDE_DIRS} ${PYTHON_INCLUDE_PATH}
  ${SPT3G_INCLUDES})


# Always build the clientlib; it's needed by server too.  This is also
# where pyrebird lives.

add_subdirectory(lyrebird-client)


if(${LYREBIRD_BUILD_VIS} STREQUAL "yes")

    # Only the visualizer needs all the OpenGL and Xwindows stuff.

    find_package(GLFW REQUIRED)
    find_package(OpenGL REQUIRED)
    find_package(GLEW REQUIRED)
    find_package(X11 REQUIRED)
    find_package(FFTW REQUIRED)
    
    include_directories("./")      # this is only needed for glm/glm.hpp
    include_directories("./AntTweakBar/include/")
    include_directories("./lyrebird-vis/")
    include_directories(${GLFW_INCLUDE_DIR} ${FFTW_INCLUDE_DIRS} 
      ${OPENGL_INCLUDE_DIR} ${GLEW_INCLUDE_DIRS} ${X11_INCLUDE_DIRS} )

    add_subdirectory(AntTweakBar)
    add_subdirectory(lyrebird-vis)
    add_subdirectory(lyrebird-bin)

endif()

