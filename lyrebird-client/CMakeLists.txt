# lyrebird-client
# 
# Includes a library that defines custom classes for streaming data
# along with pixel layout informat geometry description.
#
# This also produces pyrebird, the a python interface for use by
# lyrebird clients.

add_library(lyrebird-client SHARED
    client.cpp
)

target_link_libraries(lyrebird-client
    ${Boost_LIBRARIES} ${PYTHON_LIBRARIES}
    ${FFTW_LIBRARIES} ${SPT3G_LIBRARIES} ${CMAKE_DL_LIBS}
    pthread)

install (TARGETS lyrebird-client DESTINATION lib)

# This will be relative to the lyrebird-client build path.
set(PYREBIRD_PLACE ../pyrebird)

add_custom_target(pyrebird ALL
    COMMAND mkdir -p ${PYREBIRD_PLACE}
    COMMAND cp "${CMAKE_CURRENT_SOURCE_DIR}/python/*.py" ${PYREBIRD_PLACE}
    COMMAND cp $<TARGET_FILE_NAME:lyrebird-client> ${PYREBIRD_PLACE}
    DEPENDS lyrebird-client)

