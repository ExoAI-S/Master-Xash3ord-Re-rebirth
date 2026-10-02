// Shared, deterministic rules for the opt-in Daragoth ground-mount prototype.
#pragma once

namespace MSRMountPolicy
{
constexpr int MountedFlag = 1 << 10;
constexpr float WalkSpeed = 320.0f;
constexpr float GallopSpeed = 520.0f;
constexpr float RiderLift = 59.0f; // Three units of clearance above the padded saddle.
constexpr float RiderForward = 16.5f;
constexpr float ViewHeight = 64.0f;

// MSR stores a percentage in clientdata.maxspeed, with zero meaning normal.
// Slow effects still apply, but speed buffs cannot lift a horse above its cap.
constexpr float Speed(bool gallop, float effectPercent = 0.0f, bool stopped = false)
{
    if (stopped || effectPercent != effectPercent || effectPercent < 0.0f)
        return 0.0f;
    const float percent = effectPercent == 0.0f || effectPercent > 100.0f ? 100.0f : effectPercent;
    return (gallop ? GallopSpeed : WalkSpeed) * percent / 100.0f;
}

struct MountGate
{
    bool enabled, riderHasMount, horseOccupied, alive, characterLoaded;
    bool onGround, standing, walking, attacking, inMenu;
    int waterLevel;
};

constexpr bool CanMount(const MountGate &gate)
{
    return gate.enabled && !gate.riderHasMount && !gate.horseOccupied && gate.alive &&
        gate.characterLoaded && gate.onGround && gate.standing && gate.walking &&
        !gate.attacking && !gate.inMenu && gate.waterLevel < 2;
}
} // namespace MSRMountPolicy
