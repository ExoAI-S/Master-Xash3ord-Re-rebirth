#pragma once
#include <cmath>
#include <limits>

namespace MSREncounterAllocator
{
// Exact SV_AllocEdict reuse predicate, including its strict half-second boundary.
// Counting this over the whole contiguous array is a conservative lower bound:
// fresh unused slots have free=true/freetime=0; future-time leftovers from a
// previous map are excluded because the SDK exposes no allocation high-water.
inline bool Ready(bool free, double freeTime, double now)
{
    return free && std::isfinite(freeTime) && std::isfinite(now) && now >= 0 &&
        (freeTime < 2.0 || now - freeTime > 0.5);
}
inline double EngineTimeLowerBound(float reportedTime)
{
    // SV uses double time, whereas the SDK reports it through a float. Using
    // that rounded-up float could admit a hole before the real half-second
    // deadline. One float predecessor is a conservative bound, not exact time.
    if (!std::isfinite(reportedTime) || reportedTime < 0)
        return std::numeric_limits<double>::quiet_NaN();
    const float predecessor = std::nextafter(reportedTime,
        -std::numeric_limits<float>::infinity());
    return predecessor > 0 ? static_cast<double>(predecessor) : 0;
}
template<class Edict>
int ReadyCount(const Edict* world, int maxClients, int maxEntities, float reportedTime)
{
    const double now = EngineTimeLowerBound(reportedTime);
    if (!world || maxClients < 0 || maxEntities <= maxClients ||
        !std::isfinite(now) || now < 0) return 0;
    int count = 0;
    // World/client slots are never available to SV_AllocEdict's ordinary scan.
    for (int i = maxClients + 1; i < maxEntities; ++i)
        if (Ready(world[i].free != 0, world[i].freetime, now)) ++count;
    return count;
}
} // namespace MSREncounterAllocator
