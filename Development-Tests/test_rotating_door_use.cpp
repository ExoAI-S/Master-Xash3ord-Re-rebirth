// Compiles the production geometry helper and exact production angle/clamp routines.
#include "../Full-Source/msr_source/src/game/server/player/rotating_door_use.h"
#include <cmath>
#include <cstdio>
#include <cstdlib>

void AngleVectors(const Vector&, Vector*, Vector*, Vector*);
Vector UTIL_ClampVectorToBox(const Vector&, const Vector&);
using namespace MSRRotatingDoorUse;
static unsigned checks = 0;

static void Check(bool value, const char* label)
{
    ++checks;
    if (!value) { std::fprintf(stderr, "FAIL: %s\n", label); std::exit(1); }
}
static bool Near(const Vector& a, const Vector& b, float tolerance = 0.001f)
{
    return (a - b).Length() < tolerance;
}
static Basis MakeBasis(const Vector& angles)
{
    Basis basis;
    AngleVectors(angles, &basis.forward, &basis.right, &basis.up);
    return basis;
}
// Independent Euler matrix composition, rather than the helper's basis operations.
static Vector ReferenceRotate(const Vector& v, const Vector& angles)
{
    constexpr double radians = 3.14159265358979323846 / 180;
    const double p = angles.x * radians, y = angles.y * radians, r = angles.z * radians;
    const double rx = v.x, ry = std::cos(r)*v.y - std::sin(r)*v.z, rz = std::sin(r)*v.y + std::cos(r)*v.z;
    const double px = std::cos(p)*rx + std::sin(p)*rz, py = ry, pz = -std::sin(p)*rx + std::cos(p)*rz;
    return Vector(float(std::cos(y)*px - std::sin(y)*py), float(std::sin(y)*px + std::cos(y)*py), float(pz));
}

int main()
{
    const Vector mins(-4, -1, -46), maxs(4, 73, 46);
    const Vector origin(-2893.952637f, 5280, 3174);
    const Basis zero = MakeBasis(Vector(0, 0, 0));
    const Vector inside(-2912.983887f, 5316, 3164.03125f);
    const Vector eye = inside + Vector(0, 0, 28);
    Vector direction;
    Check(AimDirection(inside, eye, origin, mins, maxs, zero, 64, direction), "recorded inside reopen is reachable");
    Check(Near(direction, Vector(1, 0, 0)), "recorded inside reopen faces east");
    const Vector oldCenter = Vector(-2967.952637f, 5206, 3100) + Vector(8, 74, 92) * 0.5f;
    const Vector oldDirection = UTIL_ClampVectorToBox(oldCenter - eye, Vector(8, 74, 92) * 0.5f);
    Check(DotProduct(oldDirection, Vector(1, 0, 0)) < 0, "recorded old rotation cube reproduces missed Use");
    const Vector outside(-2874.921387f, 5316, 3164.03125f);
    Check(AimDirection(outside, outside + Vector(0, 0, 28), origin, mins, maxs, zero, 64, direction), "recorded outside is reachable");
    Check(Near(direction, Vector(-1, 0, 0)), "recorded outside faces west");

    const Vector angles[] = {
        Vector(0,0,0), Vector(0,90,0), Vector(0,-90,0), Vector(0,45,0), Vector(0,-45,0),
        Vector(0,13,0), Vector(0,180,0), Vector(20,45,-15), Vector(90,0,0), Vector(0,0,90), Vector(35,-63,77)
    };
    const Vector boxes[][2] = { {mins,maxs}, {Vector(-11,8,-20),Vector(21,85,60)} };
    const Vector pivots[] = { Vector(0,0,0), origin, Vector(923,-477,105) };
    for (const Vector& angle : angles)
    {
        const Basis basis = MakeBasis(angle);
        Check(Near(ToWorld(Vector(7,-19,31), basis), ReferenceRotate(Vector(7,-19,31), angle)), "full engine angle basis matches independent Euler matrix");
        for (const auto& box : boxes)
        for (const Vector& pivot : pivots)
        for (int face = 0; face < 6; ++face)
        {
            const Vector lo = box[0], hi = box[1];
            Vector contact = (lo + hi) * 0.5f;
            Vector localNormal(0,0,0);
            const int axis = face / 2;
            const float sign = face % 2 ? 1.0f : -1.0f;
            contact[axis] = sign > 0 ? hi[axis] : lo[axis];
            localNormal[axis] = sign;
            const Vector point = pivot + ReferenceRotate(contact + localNormal * 27.0f, angle);
            const Vector expected = pivot + ReferenceRotate(contact, angle);
            const Vector expectedDirection = -ReferenceRotate(localNormal, angle);
            Check(Near(NearestPoint(point,pivot,lo,hi,basis), expected), "nearest rotated face with noncentral origin");
            Check(AimDirection(point,point,pivot,lo,hi,basis,28,direction), "nearest leaf within real reach");
            Check(Near(direction,expectedDirection), "normalized nearest-face direction");
            Check(std::fabs(direction.Length()-1) < 0.0001f, "view dot receives unit direction");
            Check(!AimDirection(point,point,pivot,lo,hi,basis,26,direction), "real leaf distance rejects broadphase false positive");
        }
    }
    const Vector atLimit = origin + Vector(-68,36,0);
    Check(AimDirection(atLimit,atLimit,origin,mins,maxs,zero,64,direction), "64-unit origin reach boundary");
    Check(!AimDirection(atLimit-Vector(0.25f,0,0),atLimit,origin,mins,maxs,zero,64,direction), "beyond 64-unit origin reach is rejected");
    Check(!AimDirection(atLimit,atLimit,origin,mins,maxs,zero,-1,direction), "negative reach is rejected");
    Check(!AimDirection(atLimit,atLimit,origin,mins,maxs,zero,std::nanf(""),direction), "NaN reach is rejected");
    Check(AimDirection(origin+Vector(0,36,0),origin+Vector(0,36,0),origin,mins,maxs,zero,64,direction), "zero-distance point is finite");
    Check(Near(direction,Vector(0,0,1)), "inside-box direction preserves historical Vector normalization fallback");
    std::printf("Rotating door Use: %u deterministic production geometry checks PASS.\n", checks);
}
