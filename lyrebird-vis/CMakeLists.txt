# Keep source files sorted alphabetically.
add_library(lyrebird-vis SHARED
    cameracontrol.cpp
    configparsing.cpp
    datastreamer.cpp
    datavals.cpp
    dfmuxstreamer.cpp
    equation.cpp
    equationmap.cpp
    genericutils.cpp
    geometryutils.cpp
    # hdfstreamer.cpp
    highlighter.cpp
    jsoncpp.cpp
    logging.cpp
    nanosvg.cpp
    numberlineart.cpp
    plotbundler.cpp
    plotter.cpp
    polygon.cpp
    sdstreamer.cpp
    shader.cpp
    simplerender.cpp
    sockethelper.cpp
    # sockettest.cpp
    teststreamer.cpp
    visualelement.cpp
)

target_link_libraries(lyrebird-vis
  AntTweakBar lyrebird-client
  ${GLFW_LIBRARIES} ${OPENGL_gl_LIBRARY} ${OPENGL_glu_LIBRARY} ${GLEW_LIBRARY}
  ${X11_LIBRARIES} ${X11_Xxf86vm_LIB}
  ${X11_Xrandr_LIB} ${X11_Xinerama_LIB} ${X11_Xi_LIB} ${X11_Xcursor_LIB}
  ${FFTW_LIBRARIES} ${SPT3G_LIBRARIES} ${CMAKE_DL_LIBS} pthread)

install (TARGETS lyrebird-vis DESTINATION lib)
