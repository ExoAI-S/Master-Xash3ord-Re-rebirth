// Mounted-only pose for MSR's Bip01 human skeleton. Euler angles are radians,
// in studio AngleQuaternion's roll/pitch/yaw order, rather than view angles.
#pragma once

namespace MSRMountedRiderPose
{
struct Bone
{
    const char *name;
    float angle[3];
};

// Thighs spread 35 degrees and bend forward 50 degrees; knees bend 55 degrees.
// The ankle rotations bring both boots upright with toes pointing forward.
// Root yaw zero removes the floor-sitting animation's asymmetric body turn.
constexpr Bone Bones[] = {
    {"Bip01", {0.0f, 0.0f, 0.0f}},
    {"Bip01 Pelvis", {-1.570796327f, -1.570796327f, 0.0f}},
    {"Bip01 L Leg", {0.0f, 3.752457892f, -0.872664626f}},
    {"Bip01 L Leg1", {0.0f, 0.0f, -0.959931089f}},
    {"Bip01 L Foot", {0.492334136f, -0.377597008f, -0.008679635f}},
    {"Bip01 L Toe0", {0.0f, 0.0f, 1.570796327f}},
    {"Bip01 R Leg", {0.0f, 2.530727415f, -0.872664626f}},
    {"Bip01 R Leg1", {0.0f, 0.0f, -0.959931089f}},
    {"Bip01 R Foot", {-0.492334136f, 0.377597008f, -0.008679635f}},
    {"Bip01 R Toe0", {0.0f, 0.0f, 1.570796327f}}
};
constexpr int BoneCount = sizeof(Bones) / sizeof(Bones[0]);
} // namespace MSRMountedRiderPose
