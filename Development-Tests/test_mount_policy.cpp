// Standalone deterministic policy test: compile without the game or an engine.
#include "../Full-Source/msr_source/src/game/shared/ms/mount_policy.h"
#include <cassert>
#include <cmath>
#include <cstdio>

int main()
{
    using namespace MSRMountPolicy;
    assert(Speed(false) == WalkSpeed);
    assert(Speed(true) == GallopSpeed);
    assert(Speed(true, 50.0f) == GallopSpeed / 2.0f);
    assert(Speed(false, 200.0f) == WalkSpeed);
    assert(Speed(true, -1.0f) == 0.0f);
    assert(Speed(true, std::nanf("")) == 0.0f);
    assert(Speed(true, 0.0f, true) == 0.0f);
    assert((MountedFlag & ((1 << 10) - 1)) == 0);
    MountGate valid{true, false, false, true, true, true, true, true, false, false, 0};
    assert(CanMount(valid));
    for (int rule = 0; rule < 11; ++rule)
    {
        MountGate gate = valid;
        switch (rule)
        {
        case 0: gate.enabled = false; break;
        case 1: gate.riderHasMount = true; break;
        case 2: gate.horseOccupied = true; break;
        case 3: gate.alive = false; break;
        case 4: gate.characterLoaded = false; break;
        case 5: gate.onGround = false; break;
        case 6: gate.standing = false; break;
        case 7: gate.walking = false; break;
        case 8: gate.attacking = true; break;
        case 9: gate.inMenu = true; break;
        case 10: gate.waterLevel = 2; break;
        }
        assert(!CanMount(gate));
    }
    std::puts("Mount policy: fixed speeds, effect caps, unique flag and 11 mount gates PASS.");
}
