// Pure atlas helpers: no engine state, file access, travel commands, or VGUI.
#pragma once
#include "worldmap_chart.h"
#include <string>
#include <vector>
#include <cstring>

namespace MSRWorldAtlas
{
inline std::string LevelID(const char* level)
{
    if (!level) return {};
    std::string result(level);
    const auto slash = result.find_last_of("/\\");
    if (slash != std::string::npos) result.erase(0, slash + 1);
    for (auto& c : result) if (c >= 'A' && c <= 'Z') c += 'a' - 'A';
    if (result.size() >= 4 && result.compare(result.size() - 4, 4, ".bsp") == 0)
        result.resize(result.size() - 4);
    return result;
}

inline const MSRWorldChart::Pin* FindPin(const char* level)
{
    const auto id = LevelID(level);
    for (const auto& pin : MSRWorldChart::pins)
        if (id == pin.id) return &pin;
    return nullptr; // Never place unknown/sub-map names at a made-up location.
}

inline int Pixel(float normalized, int extent)
{
    return extent > 0 ? static_cast<int>(normalized * extent + .5f) : 0;
}

// Only the packaged format is accepted: 1024-square top-left 24-bit raw BGR.
// Exact byte count and a fixed dimension cap precede all allocations/indexing.
inline bool DecodeTile(const unsigned char* bytes, size_t count, std::vector<unsigned char>& rgba)
{
    rgba.clear();
    const int side = MSRWorldChart::tileSize;
    const size_t expected = 18u + static_cast<size_t>(side) * side * 3u;
    if (!bytes || count != expected || side != 1024) return false;
    if (bytes[0] || bytes[1] || bytes[2] != 2 || bytes[16] != 24 || bytes[17] != 32) return false;
    for (int i = 3; i < 12; ++i) if (bytes[i]) return false;
    const int w = bytes[12] | (bytes[13] << 8), h = bytes[14] | (bytes[15] << 8);
    if (w != side || h != side) return false;
    rgba.resize(static_cast<size_t>(w) * h * 4u);
    for (size_t source = 18, target = 0; source < count; source += 3, target += 4)
    {
        rgba[target] = bytes[source + 2]; rgba[target + 1] = bytes[source + 1];
        rgba[target + 2] = bytes[source]; rgba[target + 3] = 255;
    }
    return true;
}

#ifndef NDEBUG
inline bool SelfTest()
{
    if (LevelID(nullptr) != "" || LevelID("maps/EDANA.BSP") != "edana" ||
        LevelID("C:\\game\\maps\\The_Wall2.bsp") != "the_wall2") return false;
    if (!FindPin("maps/Edana.bsp") || FindPin("maps/edana_unknown.bsp") ||
        FindPin("maps/edanasewers.bsp") || FindPin(nullptr) || FindPin("maps/ms_snow.bsp")) return false;
    for (int i = 0; i < MSRWorldChart::pinCount; ++i)
    {
        const auto& pin = MSRWorldChart::pins[i];
        if (!(pin.u > 0 && pin.u < 1 && pin.v > 0 && pin.v < 1)) return false;
        if (FindPin(pin.id) != &pin) return false;
        for (int j = 0; j < i; ++j) if (!strcmp(pin.id, MSRWorldChart::pins[j].id)) return false;
    }
    const auto* edana = FindPin("edana");
    if (Pixel(edana->u, 1619) != 636 || Pixel(edana->v, 1536) != 808 ||
        Pixel(0, 4096) != 0 || Pixel(1, 4096) != 4096 || Pixel(.5f, 800) != 400) return false;
    std::vector<unsigned char> rgba, bytes(18 + 1024 * 1024 * 3, 0);
    if (DecodeTile(nullptr, bytes.size(), rgba) || DecodeTile(bytes.data(), 18, rgba)) return false;
    bytes[2] = 2; bytes[13] = bytes[15] = 4; bytes[16] = 24; bytes[17] = 32;
    bytes[18] = 7; bytes[19] = 11; bytes[20] = 19;
    if (!DecodeTile(bytes.data(), bytes.size(), rgba) || rgba.size() != 1024 * 1024 * 4 ||
        rgba[0] != 19 || rgba[1] != 11 || rgba[2] != 7 || rgba[3] != 255) return false;
    bytes[2] = 10; if (DecodeTile(bytes.data(), bytes.size(), rgba)) return false;
    bytes[2] = 2; bytes[13] = 8; if (DecodeTile(bytes.data(), bytes.size(), rgba)) return false;
    bytes[13] = 4; bytes[17] = 0; if (DecodeTile(bytes.data(), bytes.size(), rgba)) return false;
    bytes[17] = 32; return !DecodeTile(bytes.data(), bytes.size() - 1, rgba);
}
#endif
}
