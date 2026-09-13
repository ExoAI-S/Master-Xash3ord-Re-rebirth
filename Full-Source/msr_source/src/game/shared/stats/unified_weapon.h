#ifndef MS_UNIFIED_WEAPON_H
#define MS_UNIFIED_WEAPON_H

#include <cstdint>
#include <cmath>

// The three legacy records are a storage envelope, not separate skills.
// Costs are integral XP: ceil(the original GetExpNeeded formula) per track.
namespace UnifiedWeapon
{
    using XP = std::uint64_t;
    constexpr int Tracks = 3;
    constexpr int LevelCap = 45;
    constexpr XP MaxStoredXP = 2147483647ULL;
    struct Record { int level; std::int64_t xp; };
    struct State { int level; XP xp; XP required; XP lifetime; };

    inline XP TrackCost(int level)
    {
        if (level <= 0 || level > LevelCap) return 0;
        return static_cast<XP>(std::ceil(std::pow(1.248, level) * (4.0 * level)));
    }
    inline XP EarnedBefore(int level)
    {
        XP result = 0;
        for (int n = 1; n < level; ++n) result += TrackCost(n);
        return result;
    }
    inline bool Read(const Record (&records)[Tracks], State& state)
    {
        XP total = 0;
        for (const auto& record : records)
        {
            // Unsupported/invalid records are rejected atomically; never clamp
            // a save and silently destroy training or a privileged >cap level.
            if (record.level < 0 || record.level > LevelCap ||
                record.xp < 0 || static_cast<XP>(record.xp) > MaxStoredXP) return false;
            total += EarnedBefore(record.level) + static_cast<XP>(record.xp);
        }
        state.level = 1; // Original zero -> one transition costs zero XP.
        state.xp = total;
        state.lifetime = total;
        while (state.level < LevelCap && state.xp >= Tracks * TrackCost(state.level))
        {
            state.xp -= Tracks * TrackCost(state.level);
            ++state.level;
        }
        state.required = state.level < LevelCap ? Tracks * TrackCost(state.level) : 0;
        return state.xp <= Tracks * MaxStoredXP;
    }
    inline bool Write(const State& state, Record (&records)[Tracks])
    {
        if (state.level < 1 || state.level > LevelCap || state.xp > Tracks * MaxStoredXP)
            return false;
        for (int n = 0; n < Tracks; ++n)
        {
            records[n].level = state.level;
            records[n].xp = static_cast<std::int64_t>(state.xp / Tracks +
                (static_cast<XP>(n) < state.xp % Tracks ? 1 : 0));
        }
        return true;
    }
    inline bool Normalize(Record (&records)[Tracks])
    {
        State state{};
        return Read(records, state) && Write(state, records);
    }
    inline bool SetLevel(Record (&records)[Tracks], int level)
    {
        if (level < 0 || level > LevelCap) return false;
        State state{};
        state.level = level == 0 ? 1 : level;
        return Write(state, records);
    }
    // Returns accepted XP separately from the cap's rejected excess. Existing
    // residual XP at cap is retained; new awards cannot increase it.
    inline bool Award(Record (&records)[Tracks], std::int64_t amount, XP& accepted, int& levels)
    {
        accepted = 0; levels = 0;
        State state{};
        if (amount < 0 || !Read(records, state)) return false;
        const int oldLevel = state.level;
        const XP toCap = Tracks * EarnedBefore(LevelCap);
        const XP room = state.lifetime < toCap ? toCap - state.lifetime : 0;
        accepted = static_cast<XP>(amount) < room ? static_cast<XP>(amount) : room;
        state.xp += accepted;
        while (state.level < LevelCap && state.xp >= Tracks * TrackCost(state.level))
        {
            state.xp -= Tracks * TrackCost(state.level);
            ++state.level;
        }
        levels = state.level - oldLevel;
        return Write(state, records);
    }
}
#endif
