#
# "lyrebird" is the main viewer binary.
#

add_executable(lyrebird main.cpp)

target_link_libraries(lyrebird lyrebird-vis)

install (TARGETS lyrebird DESTINATION bin)
