// Pure client scenery rules: no engine state, allocation, or gameplay changes.
#pragma once

#include <cmath>
#include <cstring>

namespace MSRSceneryPolicy
{
enum Kind { None, Grass, Bush, Rock, Tree, Detail };

struct FadeBand
{
    float start;
    float end;
};

// Only these generated decorative models may be distance culled. In particular,
// neither arbitrary models/plains paths nor apple fruit/gameplay props qualify.
inline Kind Classify(const char *model)
{
    if (!model)
        return None;
    if (std::strcmp(model, "models/plains/plains_grass.mdl") == 0 ||
        std::strcmp(model, "models/plains/meadow_grass_patch.mdl") == 0)
        return Grass;
    if (std::strcmp(model, "models/plains/plains_bush.mdl") == 0)
        return Bush;
    if (std::strcmp(model, "models/plains/plains_rocks.mdl") == 0)
        return Rock;
    if (std::strcmp(model, "models/plains/plains_oak.mdl") == 0 ||
        std::strcmp(model, "models/plains/plains_birch.mdl") == 0 ||
        std::strcmp(model, "models/plains/plains_pine.mdl") == 0 ||
        std::strcmp(model, "models/plains/edana_apple_tree.mdl") == 0)
        return Tree;

    constexpr char prefix[] = "models/plains/meadow_sector_";
    constexpr unsigned int prefixLength = sizeof(prefix) - 1;
    if (std::strlen(model) == prefixLength + 7 &&
        std::strncmp(model, prefix, prefixLength) == 0 &&
        model[prefixLength] >= '0' && model[prefixLength] <= '9' &&
        model[prefixLength + 1] >= '0' && model[prefixLength + 1] <= '9' &&
        model[prefixLength + 2] >= '0' && model[prefixLength + 2] <= '9' &&
        std::strcmp(model + prefixLength + 3, ".mdl") == 0)
        return Grass;
    return None;
}

inline FadeBand BandFor(Kind kind)
{
    switch (kind)
    {
    case Grass: return {2400.0f, 4400.0f};
    case Bush: return {4200.0f, 6500.0f};
    case Rock: return {5000.0f, 7500.0f};
    case Tree: return {8000.0f, 12000.0f};
    // Reserved for explicitly classified decorative details; Classify does not
    // currently emit it. Use the bush band when a caller selects it explicitly.
    case Detail: return {4200.0f, 6500.0f};
    default: return {0.0f, 0.0f};
    }
}

// Zero disables the policy. Invalid values also disable it conservatively.
inline float DistanceScale(float scale)
{
    if (!std::isfinite(scale) || scale <= 0.0f)
        return 0.0f;
    return scale < 0.5f ? 0.5f : (scale > 2.0f ? 2.0f : scale);
}

// Inputs are world-space AABB coordinates, not entity origin/local bounds.
// A camera inside/on the bounds has distance zero. Unknown/malformed bounds
// also return zero so a failed bounds calculation never hides geometry.
inline double DistanceToBounds(const float view[3], const float mins[3], const float maxs[3])
{
    if (!view || !mins || !maxs)
        return 0.0;
    for (unsigned int axis = 0; axis < 3; ++axis)
    {
        if (!std::isfinite(view[axis]) || !std::isfinite(mins[axis]) ||
            !std::isfinite(maxs[axis]) || mins[axis] > maxs[axis])
            return 0.0;
    }
    double squaredDistance = 0.0;
    for (unsigned int axis = 0; axis < 3; ++axis)
    {
        // Promote before subtracting: two finite floats can overflow a float
        // difference or square, but their three squared differences fit double.
        const double coordinate = view[axis];
        const double delta = coordinate < mins[axis] ? double(mins[axis]) - coordinate :
            (coordinate > maxs[axis] ? coordinate - double(maxs[axis]) : 0.0);
        squaredDistance += delta * delta;
    }
    return std::sqrt(squaredDistance);
}

inline float VisibilityAlpha(Kind kind, const float view[3], const float mins[3],
    const float maxs[3], float scale)
{
    const float distanceScale = DistanceScale(scale);
    const FadeBand band = BandFor(kind);
    if (distanceScale == 0.0f || band.end <= band.start)
        return 1.0f;
    const double start = double(band.start) * distanceScale;
    const double end = double(band.end) * distanceScale;
    const double distance = DistanceToBounds(view, mins, maxs);
    if (distance <= start)
        return 1.0f;
    if (distance >= end)
        return 0.0f;
    const double t = (distance - start) / (end - start);
    return float(1.0 - t * t * (3.0 - 2.0 * t));
}

// 64 Bayer thresholds plus the empty mask. Validate before integer conversion
// so even NaN, infinity, and very large alpha values cannot overflow.
inline unsigned int StippleCoverage(float alpha)
{
    if (!std::isfinite(alpha) || alpha >= 1.0f)
        return 64;
    if (alpha <= 0.0f)
        return 0;
    return static_cast<unsigned int>(alpha * 64.0f + 0.5f);
}

// OpenGL's 32x32 GL_POLYGON_STIPPLE bitmap, with the default MSB-first bit
// order. Screen-stable ordered coverage preserves opaque depth writes.
inline void BuildStippleMask(float alpha, unsigned char (&mask)[128])
{
    static constexpr unsigned char bayer[8][8] = {
        { 0, 48, 12, 60,  3, 51, 15, 63},
        {32, 16, 44, 28, 35, 19, 47, 31},
        { 8, 56,  4, 52, 11, 59,  7, 55},
        {40, 24, 36, 20, 43, 27, 39, 23},
        { 2, 50, 14, 62,  1, 49, 13, 61},
        {34, 18, 46, 30, 33, 17, 45, 29},
        {10, 58,  6, 54,  9, 57,  5, 53},
        {42, 26, 38, 22, 41, 25, 37, 21}
    };
    const unsigned int coverage = StippleCoverage(alpha);
    for (unsigned int y = 0; y < 32; ++y)
    {
        unsigned char row = 0;
        for (unsigned int x = 0; x < 8; ++x)
        {
            if (bayer[y & 7][x] < coverage)
                row |= static_cast<unsigned char>(0x80u >> x);
        }
        for (unsigned int byte = 0; byte < 4; ++byte)
            mask[y * 4 + byte] = row;
    }
}
} // namespace MSRSceneryPolicy
