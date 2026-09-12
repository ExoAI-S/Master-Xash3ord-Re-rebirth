cmake_minimum_required(VERSION 3.19)

# Experimental MSR-on-PrimeXT targets.
#
# MSR is intentionally compiled as two separate DLLs, just like the original
# GoldSrc layout. Its source tree is kept intact under ../msr_source so that
# relative includes used by the MScript runtime continue to resolve while the
# PrimeXT SDK is supplied through the parent project.

set(MSR_ROOT "${CMAKE_SOURCE_DIR}/msr_source")
set(MSR_GAME_ROOT "${MSR_ROOT}/src/game")
set(MSR_COMMON_ROOT "${MSR_ROOT}/src/common")
set(MSR_PUBLIC_ROOT "${MSR_ROOT}/src/public")
set(MSR_THIRDPARTY_ROOT "${MSR_ROOT}/thirdparty")

include("${CMAKE_CURRENT_SOURCE_DIR}/source_lists.cmake")

# Keep the exact authored source membership from MSR's own client/server
# projects. A recursive glob also picks up standalone experiments and legacy
# HUD units that are deliberately not part of the shipped DLLs.
set(MSR_CLIENT_SOURCES ${MSR_AUTHORED_CLIENT_SOURCES})
set(MSR_SERVER_SOURCES ${MSR_AUTHORED_SERVER_SOURCES})
list(APPEND MSR_CLIENT_SOURCES "${MSR_GAME_ROOT}/client/standalone_profile.cpp")
list(APPEND MSR_SERVER_SOURCES "${MSR_GAME_ROOT}/server/encounter_director.cpp")
# These commented-out entries were incorrectly imported by source discovery.
list(FILTER MSR_SERVER_SOURCES EXCLUDE REGEX "/(SteamServerHelper|entities)\\.cpp$")

set(MSR_INCLUDE_DIRS
    "${MSR_GAME_ROOT}/client"
    "${MSR_GAME_ROOT}/client/ms"
    "${MSR_GAME_ROOT}/client/hl"
    "${MSR_GAME_ROOT}/client/fmod"
    "${MSR_GAME_ROOT}/client/render"
    "${MSR_GAME_ROOT}/client/ui"
    "${MSR_GAME_ROOT}/client/ui/ms"
    "${MSR_GAME_ROOT}/server"
    "${MSR_GAME_ROOT}/server/hl"
    "${MSR_GAME_ROOT}/server/player"
    "${MSR_GAME_ROOT}/server/effects"
    "${MSR_GAME_ROOT}/server/gamerules"
    "${MSR_GAME_ROOT}/server/monsters"
    "${MSR_GAME_ROOT}/server/fn"
    "${MSR_GAME_ROOT}/shared"
    "${MSR_GAME_ROOT}/shared/movement"
    "${MSR_GAME_ROOT}/shared/ms"
    "${MSR_GAME_ROOT}/shared/stats"
    "${MSR_GAME_ROOT}/shared/syntax"
    "${MSR_GAME_ROOT}/shared/weapons"
    "${MSR_COMMON_ROOT}"
    "${MSR_PUBLIC_ROOT}"
    "${MSR_PUBLIC_ROOT}/engine"
    "${MSR_ROOT}/lib/include"
    "${MSR_ROOT}/lib/include/vgui"
    "${MSR_PUBLIC_ROOT}/steam"
    "${MSR_THIRDPARTY_ROOT}"
    "${MSR_THIRDPARTY_ROOT}/angelscript/include"
    "${MSR_THIRDPARTY_ROOT}/spdlog/include"
)

add_library(msr_client SHARED ${MSR_CLIENT_SOURCES})
add_library(msr_server SHARED ${MSR_SERVER_SOURCES})
target_include_directories(msr_client PRIVATE "${CMAKE_SOURCE_DIR}/external/tracy/import/src")

foreach(target IN ITEMS msr_client msr_server)
    add_dependencies(${target} build_info)
    target_include_directories(${target} PRIVATE ${MSR_INCLUDE_DIRS})
    target_compile_definitions(${target} PRIVATE
        MSR_STANDALONE=1
        _CRT_SECURE_NO_WARNINGS
        VERSION_SAFE_STEAM_API_INTERFACES
    )
    if(NOT MSVC)
        target_compile_definitions(${target} PRIVATE
            _LINUX=1 LINUX=1
            stricmp=strcasecmp
            strnicmp=strncasecmp
            _snprintf=snprintf
            _vsnprintf=vsnprintf
        )
        target_compile_options(${target} PRIVATE -fno-strict-aliasing -Wno-write-strings)
    endif()
    set_target_properties(${target} PROPERTIES
        PREFIX ""
        CXX_STANDARD 20
        CXX_STANDARD_REQUIRED YES
        POSITION_INDEPENDENT_CODE 1
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/${CMAKE_BUILD_TYPE}/msr/bin"
        LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/${CMAKE_BUILD_TYPE}/msr/bin"
        ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/${CMAKE_BUILD_TYPE}/msr/bin"
    )
endforeach()

target_compile_definitions(msr_client PRIVATE ISCLIENT CLIENT_WEAPONS DISCORD_DYNAMIC_LIB USE_BREAKPAD_HANDLER)
target_compile_definitions(msr_server PRIVATE VALVE_DLL=1 CURL_STATICLIB HTTP_ONLY)

if(MSVC)
    foreach(target IN ITEMS msr_client msr_server)
        set_property(TARGET ${target} PROPERTY MSVC_RUNTIME_LIBRARY MultiThreaded)
        target_compile_options(${target} PRIVATE /utf-8)
        # Keep release function symbols and a map alongside the build so local
        # crash dumps can be diagnosed without changing runtime optimization.
        target_link_options(${target} PRIVATE /DEBUG:FULL /OPT:REF /OPT:ICF /INCREMENTAL:NO /MAP)
    endforeach()
    target_link_options(msr_client PRIVATE /SAFESEH:NO)
    target_sources(msr_server PRIVATE "${MSR_GAME_ROOT}/server/ms.def")
    target_link_libraries(msr_client PRIVATE
        "${MSR_ROOT}/lib/vgui/vgui.lib"
        "${MSR_ROOT}/lib/SDL2/SDL2.lib"
        "${MSR_ROOT}/lib/fmod/fmod_vc.lib"
        "${MSR_ROOT}/lib/discord/discord-rpc.lib"
        wsock32 gdi32 opengl32 bcrypt)
    target_link_libraries(msr_server PRIVATE
        "${MSR_ROOT}/lib/curl/libcurl.lib"
        "${MSR_ROOT}/lib/zlib/zlib.lib"
        Ws2_32 Wldap32 Crypt32 Normaliz)
endif()

set_target_properties(msr_client PROPERTIES OUTPUT_NAME "client")
set_target_properties(msr_server PROPERTIES OUTPUT_NAME "ms")

find_package(fmt CONFIG REQUIRED)
target_link_libraries(msr_client PRIVATE fmt::fmt)
target_link_libraries(msr_server PRIVATE fmt::fmt)

if(ENABLE_PHYSX)
    find_package(PhysX REQUIRED)
    target_link_libraries(msr_server PRIVATE PhysX::PhysX)
endif()

message(STATUS "MSR port targets enabled; MScript source and AngelScript sources are included")

find_package(Python3 COMPONENTS Interpreter QUIET)
if(Python3_Interpreter_FOUND)
    add_custom_target(msr_verify_scripts
        COMMAND ${Python3_EXECUTABLE}
            "${CMAKE_CURRENT_SOURCE_DIR}/verify_scripts_pak.py"
            "${CMAKE_SOURCE_DIR}/game_dir/msr/scripts.pak"
        WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
        COMMENT "Validating the staged MSR MScript pack"
        VERBATIM
    )
endif()
