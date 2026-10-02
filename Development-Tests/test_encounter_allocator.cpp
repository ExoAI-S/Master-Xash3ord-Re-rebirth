// Engine-free pressure model. Oracle independently executes SV_AllocEdict's
// scan/high-water/growth behavior; it does not call the production predicate.
#include "msr_encounter_allocator.h"
#include "msr_encounter_policy.h"
#include <algorithm>
#include <iostream>
#include <limits>
#include <random>
#include <stdexcept>
#include <vector>

namespace A = MSREncounterAllocator;
namespace P = MSREncounterPolicy;
struct Edict { bool free = true; float freetime = 0; };
struct Engine
{
    std::vector<Edict> edicts;
    int clients = 2, highwater = 3;
    double time = 10;
    explicit Engine(int size = 256) : edicts(size) {}
    int Allocate()
    {
        for (int i = clients + 1; i < highwater; ++i)
            if (edicts[i].free && (edicts[i].freetime < 2.0f || time - edicts[i].freetime > 0.5f))
            { edicts[i].free = false; return i; }
        if (highwater >= static_cast<int>(edicts.size())) return -1;
        edicts[highwater].free = false;
        return highwater++;
    }
    int Capacity() const
    {
        Engine copy = *this;
        int count = 0;
        while (copy.Allocate() >= 0) ++count;
        return count;
    }
    int Lower() const
    { return A::ReadyCount(edicts.data(), clients, static_cast<int>(edicts.size()), static_cast<float>(time)); }
    int Active() const
    { return static_cast<int>(std::count_if(edicts.begin(), edicts.end(), [](const auto& e) { return !e.free; })); }
};
int assertions = 0, groups = 0;
void Check(bool value, const char* why)
{ ++assertions; if (!value) throw std::runtime_error(why); }
void Group(const char* name, void (*test)())
{ test(); ++groups; std::cout << "PASS " << name << '\n'; }
P::PadReason Clear(P::ControllerKey, int, void*) { return P::PadReason::Allowed; }
P::AdmissionBudget Budget()
{
    P::AdmissionBudget budget;
    Check(budget.Register({7, 11}, 32, 32), "register bounded controller");
    Check(budget.SetReady({7, 11}, UINT32_MAX), "all pads ready");
    return budget;
}
void Boundaries()
{
    Check(A::Ready(true, 1.999, 0), "engine permits early free-time shortcut");
    Check(!A::Ready(true, 2, 2.5), "strict half second equality is unavailable");
    Check(A::Ready(true, 2, 2.500001), "aged slot available");
    Check(!A::Ready(true, 20, 10), "future-time hole unavailable");
    Check(!A::Ready(false, 0, 10), "occupied slot unavailable");
    Check(!A::Ready(true, NAN, 10), "invalid free time fails closed");
    Check(!A::Ready(true, 0, NAN), "invalid clock fails closed");
    Engine engine(16);
    Check(engine.Lower() == 13, "world and reserved clients excluded");
    Check(A::ReadyCount<Edict>(nullptr, 2, 16, 10) == 0, "missing array fails closed");
    Check(A::ReadyCount(engine.edicts.data(), -1, 16, 10) == 0, "invalid client count fails closed");
    Check(A::ReadyCount(engine.edicts.data(), 2, 16, -1) == 0, "negative SDK clock fails closed");
}
void RecentHoleRegression()
{
    Engine e;
    e.highwater = 256;
    for (auto& slot : e.edicts) { slot.free = false; slot.freetime = 10; }
    for (int i = 3; i < 68; ++i) e.edicts[i].free = true;
    Check(e.edicts.size() - e.Active() == 65, "65 inactive holes reproduce active-count overestimate");
    Check(e.Capacity() == 0 && e.Lower() == 0, "recent holes cannot allocate any edict");
    auto oldBudget = Budget();
    Check(oldBudget.Reserve(10, {}, e.Active(), 256, Clear).reason == P::AdmissionReason::Granted,
        "old active-count admission would reach Host_Error");
    auto repaired = Budget();
    Check(repaired.Reserve(10, {}, 256 - e.Lower(), 256, Clear).reason == P::AdmissionReason::EdictMargin,
        "allocator lower bound rejects false spare capacity");
    e.time = 10.5;
    Check(e.Lower() == 0 && e.Capacity() == 0, "half-second equality stays unavailable");
    e.time = 10.501;
    Check(e.Lower() == 65 && e.Capacity() == 65, "holes become ready after aging");
    auto grant = repaired.Reserve(e.time, {}, 256 - e.Lower(), 256, Clear);
    Check(grant.reason == P::AdmissionReason::Granted && e.Allocate() >= 0 && e.Capacity() == 64,
        "primary leaves required 64 allocator slots");
}
void PendingAndProbeReserve()
{
    auto budget = Budget();
    Check(budget.Reserve(10, {}, 191, 256, Clear).reason == P::AdmissionReason::Granted, "65 ready grants primary");
    Check(budget.Reserve(11, {}, 191, 256, Clear).reason == P::AdmissionReason::EdictMargin,
        "pending primary also consumes reserve");
    Engine e(78); // 75 ordinary slots, all fresh and immediately usable.
    for (int i = 0; i < 10; ++i)
    {
        Check(e.Lower() - 1 >= P::EdictReserve, "probe preserves reserve");
        Check(e.Allocate() >= 0, "probe allocation succeeds in engine oracle");
    }
    Check(e.Lower() == 65, "ten probes consume their own capacity");
    auto withProbes = Budget();
    auto primary = withProbes.Reserve(10, {}, 78 - e.Lower(), 78, Clear);
    Check(primary.reason == P::AdmissionReason::Granted, "primary can follow ten probes");
    Check(e.Lower() - withProbes.Inflight() == 64 && e.Allocate() >= 0 && e.Capacity() == 64,
        "recheck includes this reservation and preserves actual engine capacity");
    Check(e.Lower() - 1 < 64, "next probe cannot consume the required margin");
}
void MapResetAndClockRounding()
{
    Engine e(128);
    for (auto& slot : e.edicts) slot.freetime = 100;
    e.time = 3;
    Check(e.Lower() == 0 && e.Capacity() == 125, "old-map future slots excluded conservatively without highwater");
    for (int i = 3; i < 68; ++i) e.edicts[i].freetime = 0;
    Check(e.Lower() == 65 && e.Capacity() == 125, "known fresh slots still permit a safe lower bound");
    const float freed = 4095.500732421875f;
    e.time = static_cast<double>(freed) + 0.5;
    e.highwater = 128;
    for (auto& slot : e.edicts) { slot.free = true; slot.freetime = freed; }
    Check(A::Ready(true, freed, static_cast<float>(e.time)), "rounded SDK time alone can falsely cross strict deadline");
    Check(e.Capacity() == 0 && e.Lower() == 0, "predecessor clock prevents early reuse");
    Check(A::EngineTimeLowerBound(0) == 0, "zero clock remains a valid nonnegative lower bound");
}
void RandomCapacityAndAdmission()
{
    std::mt19937 rng(0xD4A640u);
    for (int iteration = 0; iteration < 8000; ++iteration)
    {
        Engine e(96 + static_cast<int>(rng() % 160));
        e.clients = 1 + static_cast<int>(rng() % 8);
        e.highwater = e.clients + 1 + static_cast<int>(rng() % (e.edicts.size() - e.clients));
        e.time = std::ldexp(3.125, static_cast<int>(rng() % 25));
        for (auto& slot : e.edicts)
        {
            slot.free = (rng() % 4 != 0);
            switch (rng() % 6)
            {
            case 0: slot.freetime = 0; break;
            case 1: slot.freetime = 1.5f; break;
            case 2: slot.freetime = static_cast<float>(e.time - 0.1); break;
            case 3: slot.freetime = static_cast<float>(e.time - 1); break;
            case 4: slot.freetime = static_cast<float>(e.time + 2); break;
            default: slot.freetime = static_cast<float>(e.time - 0.5); break;
            }
        }
        const int lower = e.Lower(), actual = e.Capacity();
        Check(lower >= 0 && lower <= actual, "production count never overstates independent allocator capacity");
        auto budget = Budget();
        const auto grant = budget.Reserve(e.time, {}, static_cast<int>(e.edicts.size()) - lower,
            static_cast<int>(e.edicts.size()), Clear);
        Check((grant.reason == P::AdmissionReason::Granted) == (lower > 64), "admission matches conservative resource margin");
        if (grant.reason == P::AdmissionReason::Granted)
        {
            Check(e.Lower() - budget.Inflight() >= 64, "fresh birth recheck includes pending primary");
            Check(e.Allocate() >= 0 && e.Capacity() >= 64, "every accepted model birth avoids exhaustion and leaves margin");
        }
    }
}
void RandomLifecycle()
{
    std::mt19937 rng(0xF4EE123u);
    Engine e(256);
    for (int step = 0; step < 10000; ++step)
    {
        switch (rng() % 8)
        {
        case 0:
            e.time += static_cast<double>(rng() % 1000) / 1000;
            break;
        case 1:
            e.time = 3; e.highwater = e.clients + 1;
            for (auto& slot : e.edicts) slot.free = true; // Persist prior free times at map reset.
            break;
        case 2:
        case 3:
            if (e.highwater > e.clients + 1)
            {
                const int i = e.clients + 1 + static_cast<int>(rng() % (e.highwater - e.clients - 1));
                e.edicts[i].free = true; e.edicts[i].freetime = static_cast<float>(e.time);
            }
            break;
        default:
            if (e.Lower() > 64)
                Check(e.Allocate() >= 0 && e.Capacity() >= 64, "lifecycle guarded allocation preserves margin");
            break;
        }
        Check(e.Lower() <= e.Capacity(), "lower bound survives allocate/free/aging/map-reset history");
    }
}
int main()
{
    try
    {
        Group("strict reuse boundaries and reserved client slots", Boundaries);
        Group("65 recent-hole exhaustion regression and aging", RecentHoleRegression);
        Group("outstanding reservations and ten real probe allocations", PendingAndProbeReserve);
        Group("map-reset leftovers and rounded SDK clock", MapResetAndClockRounding);
        Group("8000 independent allocator/admission snapshots", RandomCapacityAndAdmission);
        Group("10000 allocation/free/aging/map-reset actions", RandomLifecycle);
        std::cout << "RESULT groups=" << groups << " assertions=" << assertions << " PASS\n";
        return 0;
    }
    catch (const std::exception& e) { std::cerr << "FAIL " << e.what() << '\n'; return 1; }
}
