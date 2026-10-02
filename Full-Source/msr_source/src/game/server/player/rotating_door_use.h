#pragma once

#include "../../shared/hl/vector.h"

// PlayerUse geometry only: engine rotation bounds are a broadphase cube, not
// the actual door leaf. Keep global brush origins used by effects unchanged.
namespace MSRRotatingDoorUse
{
struct Basis
{
    Vector forward, right, up;
};

inline Vector ToWorld(const Vector& local, const Basis& basis)
{
    // GoldSrc's right vector points along negative local Y at zero angles.
    return basis.forward * local.x - basis.right * local.y + basis.up * local.z;
}

inline Vector ToLocal(const Vector& world, const Basis& basis)
{
    return Vector(DotProduct(world, basis.forward), -DotProduct(world, basis.right), DotProduct(world, basis.up));
}

inline float Clamp(float value, float minimum, float maximum)
{
    return value < minimum ? minimum : (value > maximum ? maximum : value);
}

inline Vector NearestPoint(const Vector& point, const Vector& origin,
    const Vector& mins, const Vector& maxs, const Basis& basis)
{
    const Vector local = ToLocal(point - origin, basis);
    const Vector nearest(Clamp(local.x, mins.x, maxs.x), Clamp(local.y, mins.y, maxs.y), Clamp(local.z, mins.z, maxs.z));
    return origin + ToWorld(nearest, basis);
}

inline bool AimDirection(const Vector& searchOrigin, const Vector& eye,
    const Vector& origin, const Vector& mins, const Vector& maxs,
    const Basis& basis, float searchRadius, Vector& direction)
{
    // Preserve the existing search radius measured from the player's origin.
    // A rotated broadphase cube can otherwise admit distant, unreachable leaves.
    const float distance = (NearestPoint(searchOrigin, origin, mins, maxs, basis) - searchOrigin).Length();
    if (!(distance <= searchRadius))
        return false;

    // Match the historical normalized nearest-box direction before the view dot.
    direction = (NearestPoint(eye, origin, mins, maxs, basis) - eye).Normalize();
    return true;
}
}
