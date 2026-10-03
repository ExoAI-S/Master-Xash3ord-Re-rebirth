// Standalone policy regression test: no engine, graphics context, or game data.
#include "../Full-Source/msr_source/src/game/client/render/scenery_distance_policy.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <limits>

using namespace MSRSceneryPolicy;

static void ClassifierTests()
{
    struct Expected { const char *name; Kind kind; };
    const Expected generated[] = {
        {"models/plains/plains_grass.mdl", Grass},
        {"models/plains/meadow_grass_patch.mdl", Grass},
        {"models/plains/plains_bush.mdl", Bush},
        {"models/plains/plains_rocks.mdl", Rock},
        {"models/plains/plains_oak.mdl", Tree},
        {"models/plains/plains_birch.mdl", Tree},
        {"models/plains/plains_pine.mdl", Tree},
        {"models/plains/edana_apple_tree.mdl", Tree}
    };
    for (const Expected &item : generated)
    {
        assert(Classify(item.name) == item.kind);
        char altered[128];
        std::snprintf(altered, sizeof(altered), "%s.extra", item.name);
        assert(Classify(altered) == None);
        for (size_t length = 0; length < std::strlen(item.name); ++length)
        {
            std::memcpy(altered, item.name, length);
            altered[length] = '\0';
            assert(Classify(altered) == None);
        }
    }
    for (unsigned int sector = 0; sector < 1000; ++sector)
    {
        char model[64];
        std::snprintf(model, sizeof(model), "models/plains/meadow_sector_%03u.mdl", sector);
        assert(Classify(model) == Grass);
    }
    const char *excluded[] = {
        nullptr, "", "*0", "maps/daragoth.bsp", "models/mounts/plains_horse.mdl",
        "models/plains/plains_horse.mdl", "models/misc/p_misc.mdl",
        "models/player/player.mdl", "models/plains/monster.mdl",
        "models/plains/plains_oak_monster.mdl", "models/plains/meadow_grass_patch2.mdl",
        "models/other/plains_oak.mdl", "MODELS/PLAINS/PLAINS_OAK.MDL",
        "models\\plains\\plains_oak.mdl", "models/plains/../plains/plains_oak.mdl",
        "models/plains/meadow_sector_.mdl", "models/plains/meadow_sector_01.mdl",
        "models/plains/meadow_sector_0000.mdl", "models/plains/meadow_sector_-01.mdl",
        "models/plains/meadow_sector_0a1.mdl", "models/plains/meadow_sector_001.mdlx",
        "models/plains/meadow_sector_001", "models/plains/meadow_sector_001.MDL",
        "models/plains/meadow_sector_001.mdl/actor", "xmodels/plains/meadow_sector_001.mdl"
    };
    for (const char *model : excluded)
        assert(Classify(model) == None);
}

static void BoundsTests()
{
    const float origin[] = {0, 0, 0};
    const float min[] = {-10, -20, -30}, max[] = {10, 20, 30};
    const float onFace[] = {10, 0, 0}, corner[] = {13, 24, 42};
    assert(DistanceToBounds(origin, min, max) == 0);
    assert(DistanceToBounds(onFace, min, max) == 0);
    assert(DistanceToBounds(corner, min, max) == 13);

    // Huge sectors must survive when their origin/center is far from the view.
    const float sectorMin[] = {28000, -16000, -100}, sectorMax[] = {32760, 16000, 100};
    const float edgeView[] = {32750, 15990, 0};
    assert(VisibilityAlpha(Grass, edgeView, sectorMin, sectorMax, 1) == 1);
    const float nearSector[] = {32750, 17000, 0};
    assert(DistanceToBounds(nearSector, sectorMin, sectorMax) == 1000);
    assert(VisibilityAlpha(Grass, nearSector, sectorMin, sectorMax, 1) == 1);
    const float treeMin[] = {-100, -100, 0}, treeMax[] = {100, 100, 16000};
    const float canopyView[] = {200, 0, 15900};
    assert(DistanceToBounds(canopyView, treeMin, treeMax) == 100);
    assert(VisibilityAlpha(Tree, canopyView, treeMin, treeMax, 1) == 1);

    // Translation towards a map edge cannot change closest-bounds distance.
    const float movedMin[] = {29990, -30020, 11970}, movedMax[] = {30010, -29980, 12030};
    const float movedCorner[] = {30013, -29976, 12042};
    assert(DistanceToBounds(movedCorner, movedMin, movedMax) == 13);

    const float largest = std::numeric_limits<float>::max();
    const float positive[] = {largest, largest, largest};
    const float negative[] = {-largest, -largest, -largest};
    const double hugeDistance = DistanceToBounds(positive, negative, negative);
    assert(std::isfinite(hugeDistance));
    assert(hugeDistance > double(largest));
    assert(VisibilityAlpha(Tree, positive, negative, negative, 1) == 0);
    assert(VisibilityAlpha(Grass, origin, negative, positive, 1) == 1);

    const float invalid[] = {std::numeric_limits<float>::quiet_NaN(),
        std::numeric_limits<float>::infinity(), -std::numeric_limits<float>::infinity()};
    const float farView[] = {25000, 25000, 25000};
    for (float value : invalid)
    {
        for (unsigned int axis = 0; axis < 3; ++axis)
        {
            float badMin[] = {-10, -20, -30}, badMax[] = {10, 20, 30}, badView[] = {25000, 25000, 25000};
            badMin[axis] = badMax[axis] = badView[axis] = value;
            assert(VisibilityAlpha(Grass, farView, badMin, max, 1) == 1);
            assert(VisibilityAlpha(Grass, farView, min, badMax, 1) == 1);
            assert(VisibilityAlpha(Grass, badView, min, max, 1) == 1);
        }
    }
    for (unsigned int axis = 0; axis < 3; ++axis)
    {
        float reversed[] = {-10, -20, -30};
        reversed[axis] = max[axis] + 1;
        assert(VisibilityAlpha(Grass, farView, reversed, max, 1) == 1);
    }
    assert(VisibilityAlpha(Grass, nullptr, min, max, 1) == 1);
    assert(VisibilityAlpha(Grass, farView, nullptr, max, 1) == 1);
    assert(VisibilityAlpha(Grass, farView, min, nullptr, 1) == 1);
}

static void FadeTests()
{
    const float zero[] = {0, 0, 0};
    const float far[] = {1000000, 0, 0};
    const float invalidScales[] = {0, -1, -std::numeric_limits<float>::max(),
        std::numeric_limits<float>::quiet_NaN(), std::numeric_limits<float>::infinity(),
        -std::numeric_limits<float>::infinity()};
    for (float scale : invalidScales)
    {
        assert(DistanceScale(scale) == 0);
        assert(VisibilityAlpha(Grass, far, zero, zero, scale) == 1);
    }
    assert(DistanceScale(std::numeric_limits<float>::min()) == 0.5f);
    assert(DistanceScale(0.25f) == 0.5f);
    assert(DistanceScale(0.75f) == 0.75f);
    assert(DistanceScale(3) == 2);
    assert(DistanceScale(std::numeric_limits<float>::max()) == 2);
    assert(VisibilityAlpha(None, far, zero, zero, 1) == 1);
    assert(VisibilityAlpha(static_cast<Kind>(100), far, zero, zero, 1) == 1);
    const Kind kinds[] = {Grass, Bush, Rock, Tree, Detail};
    const float scales[] = {0.01f, 0.5f, 1, 1.5f, 2, 50};
    for (Kind kind : kinds)
    {
        const FadeBand band = BandFor(kind);
        for (float scale : scales)
        {
            const float start = band.start * DistanceScale(scale);
            const float end = band.end * DistanceScale(scale);
            const float close[] = {start, 0, 0}, middle[] = {(start + end) / 2, 0, 0}, distant[] = {end, 0, 0};
            assert(VisibilityAlpha(kind, zero, zero, zero, scale) == 1);
            assert(VisibilityAlpha(kind, close, zero, zero, scale) == 1);
            assert(VisibilityAlpha(kind, middle, zero, zero, scale) == 0.5f);
            assert(VisibilityAlpha(kind, distant, zero, zero, scale) == 0);
            float previous = 1;
            for (unsigned int step = 0; step <= 1000; ++step)
            {
                const float view[] = {end * 1.25f * step / 1000, 0, 0};
                const float alpha = VisibilityAlpha(kind, view, zero, zero, scale);
                assert(std::isfinite(alpha) && alpha >= 0 && alpha <= previous);
                previous = alpha;
            }
        }
    }
    // Larger view distance may never reduce visibility at the same location.
    for (unsigned int distance = 0; distance <= 25000; distance += 25)
    {
        const float view[] = {float(distance), 0, 0};
        for (Kind kind : kinds)
            assert(VisibilityAlpha(kind, view, zero, zero, 0.5f) <=
                VisibilityAlpha(kind, view, zero, zero, 2));
    }
}

static unsigned int BitCount(const unsigned char (&mask)[128])
{
    unsigned int count = 0;
    for (unsigned char byte : mask)
        for (unsigned int bit = 0; bit < 8; ++bit)
            count += (byte >> bit) & 1u;
    return count;
}

static void StippleTests()
{
    struct GuardedMask { unsigned char before[16], mask[128], after[16]; } guarded;
    std::memset(&guarded, 0xA5, sizeof(guarded));
    unsigned char previous[128] = {};
    for (unsigned int level = 0; level <= 64; ++level)
    {
        const float alpha = level / 64.0f;
        BuildStippleMask(alpha, guarded.mask);
        assert(StippleCoverage(alpha) == level);
        assert(BitCount(guarded.mask) == level * 16);
        for (unsigned int byte = 0; byte < 128; ++byte)
        {
            assert((previous[byte] & guarded.mask[byte]) == previous[byte]);
            previous[byte] = guarded.mask[byte];
            assert(guarded.mask[byte] == guarded.mask[byte % 32]);
        }
        unsigned char repeat[128];
        BuildStippleMask(alpha, repeat);
        assert(std::memcmp(repeat, guarded.mask, sizeof(repeat)) == 0);
        for (unsigned char guard : guarded.before) assert(guard == 0xA5);
        for (unsigned char guard : guarded.after) assert(guard == 0xA5);
    }
    const float fullValues[] = {1, 10, std::numeric_limits<float>::max(),
        std::numeric_limits<float>::quiet_NaN(), std::numeric_limits<float>::infinity(),
        -std::numeric_limits<float>::infinity()};
    for (float alpha : fullValues)
    {
        BuildStippleMask(alpha, guarded.mask);
        assert(BitCount(guarded.mask) == 1024);
    }
    BuildStippleMask(-std::numeric_limits<float>::max(), guarded.mask);
    assert(BitCount(guarded.mask) == 0);
    BuildStippleMask(0, guarded.mask);
    assert(BitCount(guarded.mask) == 0);
    // Near/far policy endpoints feed complete/empty masks with no near holes.
    const float zero[] = {0, 0, 0}, near[] = {2399, 0, 0}, far[] = {4400, 0, 0};
    BuildStippleMask(VisibilityAlpha(Grass, near, zero, zero, 1), guarded.mask);
    assert(BitCount(guarded.mask) == 1024);
    BuildStippleMask(VisibilityAlpha(Grass, far, zero, zero, 1), guarded.mask);
    assert(BitCount(guarded.mask) == 0);
}

int main()
{
    ClassifierTests();
    BoundsTests();
    FadeTests();
    StippleTests();
    std::puts("Scenery policy PASS: strict assets, safe world bounds, smooth scaled fades, conservative invalid inputs, monotone stipple coverage.");
}
