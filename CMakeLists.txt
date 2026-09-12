cmake_minimum_required(VERSION 3.20)
project(aladdin_sega LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(PORTFORGE_ROOT "" CACHE PATH "Pinned PortForge checkout; see third_party/README.md")
if(NOT EXISTS "${PORTFORGE_ROOT}/src/platform/genesis/machine.hpp")
  message(FATAL_ERROR "Set PORTFORGE_ROOT to the inspected PortForge checkout")
endif()
find_package(Python REQUIRED COMPONENTS Interpreter)
include(CTest)
set(source_check_options)
if(BUILD_TESTING)
  list(APPEND source_check_options --tests)
endif()
execute_process(COMMAND "${Python_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/check_sources.py" "${PORTFORGE_ROOT}" ${source_check_options}
  RESULT_VARIABLE provenance_result)
if(NOT provenance_result EQUAL 0)
  message(FATAL_ERROR "PortForge source identity mismatch")
endif()
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/build-options.txt"
  "C_COMPILER=${CMAKE_C_COMPILER}\nCXX_COMPILER=${CMAKE_CXX_COMPILER}\nC_COMPILER_VERSION=${CMAKE_C_COMPILER_VERSION}\nCXX_COMPILER_VERSION=${CMAKE_CXX_COMPILER_VERSION}\nBUILD_TYPE=${CMAKE_BUILD_TYPE}\nC_FLAGS=${CMAKE_C_FLAGS}\nCXX_FLAGS=${CMAKE_CXX_FLAGS}\nC_FLAGS_RELEASE=${CMAKE_C_FLAGS_RELEASE}\nCXX_FLAGS_RELEASE=${CMAKE_CXX_FLAGS_RELEASE}\nGENERATOR=${CMAKE_GENERATOR}\nCXX_STANDARD=${CMAKE_CXX_STANDARD}\nMINGW_STATIC_RUNTIME=${MINGW}\n")
add_custom_target(check_native_sources ALL
  COMMAND "${Python_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/check_sources.py" "${PORTFORGE_ROOT}" ${source_check_options}
    --identity-header "${CMAKE_CURRENT_BINARY_DIR}/generated/build_identity.hpp"
    --build-options "${CMAKE_CURRENT_BINARY_DIR}/build-options.txt"
    --receipt "${CMAKE_CURRENT_BINARY_DIR}/native-build-receipt.json"
  BYPRODUCTS "${CMAKE_CURRENT_BINARY_DIR}/generated/build_identity.hpp"
  VERBATIM)
add_library(aladdin_native SHARED native/machine.cpp
  "${CMAKE_CURRENT_SOURCE_DIR}/third_party/nuked_opn2/ym3438.c"
  "${CMAKE_CURRENT_SOURCE_DIR}/third_party/nuked_psg/ympsg.c")
add_dependencies(aladdin_native check_native_sources)
target_include_directories(aladdin_native PRIVATE "${PORTFORGE_ROOT}" "${CMAKE_CURRENT_BINARY_DIR}/generated")
if(MINGW)
  target_link_options(aladdin_native PRIVATE -static -static-libgcc -static-libstdc++)
endif()
install(TARGETS aladdin_native LIBRARY DESTINATION aladdin_sega RUNTIME DESTINATION aladdin_sega)
if(BUILD_TESTING)
  foreach(test_name m68k_units z80_units genesis_device_units genesis_render_units genesis_nuked_machine_units genesis_snapshot_codec_units genesis_scheduler_continuation_units)
    add_executable(${test_name} "${PORTFORGE_ROOT}/tests/${test_name}.cpp"
      "${CMAKE_CURRENT_SOURCE_DIR}/third_party/nuked_opn2/ym3438.c"
      "${CMAKE_CURRENT_SOURCE_DIR}/third_party/nuked_psg/ympsg.c")
    add_dependencies(${test_name} check_native_sources)
    if(MINGW)
      target_link_options(${test_name} PRIVATE -static -static-libgcc -static-libstdc++)
    endif()
    add_test(NAME ${test_name} COMMAND ${test_name})
    if(MSVC)
      target_compile_options(${test_name} PRIVATE /UNDEBUG)
    else()
      target_compile_options(${test_name} PRIVATE -UNDEBUG)
    endif()
  endforeach()
  target_compile_definitions(m68k_units PRIVATE PF_M68K_UNITS_STANDALONE)
endif()
