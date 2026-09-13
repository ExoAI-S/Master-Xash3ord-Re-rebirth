#include "sharedutil.h"
#include "stats/statdefs.h"
#include "stats/stats.h"
#include <array>
#include <vector>
#include <random>
#include <iostream>
#include <fstream>
#include <limits>
#include <stdexcept>
#include <cstring>

using namespace UnifiedWeapon;
static unsigned checks = 0;
static void require(bool ok, const char* message)
{
    ++checks;
    if (!ok) throw std::runtime_error(message);
}
static XP total(const Record (&r)[3])
{
    XP result = 0;
    for (const auto& item : r) result += EarnedBefore(item.level) + item.xp;
    return result;
}
static bool equal(const Record (&a)[3], const Record (&b)[3])
{
    for (int n = 0; n < 3; ++n)
        if (a[n].level != b[n].level || a[n].xp != b[n].xp) return false;
    return true;
}
// Exact existing skill-record envelope: byte count, then short level/int XP.
// This exercises old reader compatibility, not a complete character file.
static std::vector<unsigned char> oldSave(const Record (&r)[3])
{
    static_assert(sizeof(short) == 2 && sizeof(int) == 4, "Legacy record sizes");
    std::vector<unsigned char> bytes(19); bytes[0] = 3;
    for (int n = 0; n < 3; ++n)
    {
        const short level = static_cast<short>(r[n].level);
        const int xp = static_cast<int>(r[n].xp);
        std::memcpy(bytes.data() + 1 + 6 * n, &level, 2);
        std::memcpy(bytes.data() + 3 + 6 * n, &xp, 4);
    }
    return bytes;
}
static void oldLoad(const std::vector<unsigned char>& bytes, Record (&r)[3])
{
    require(bytes.size() == 19 && bytes[0] == 3, "Record format changed");
    for (int n = 0; n < 3; ++n)
    {
        short level; int xp;
        std::memcpy(&level, bytes.data() + 1 + 6 * n, 2);
        std::memcpy(&xp, bytes.data() + 3 + 6 * n, 4);
        r[n] = {level, xp};
    }
}
static void checkMigration(Record (&r)[3])
{
    const XP before = total(r);
    require(Normalize(r), "Valid migration rejected");
    require(r[0].level == r[1].level && r[1].level == r[2].level, "Separate levels remain");
    require(total(r) == before, "Migration created/lost XP");
    const auto saved = oldSave(r);
    Record reloaded[3]; oldLoad(saved, reloaded);
    require(Normalize(reloaded) && equal(r, reloaded), "Normalization is not idempotent");
    require(oldSave(reloaded) == saved, "Old save roundtrip bytes differ");
    State state{}; require(Read(reloaded, state), "Canonical read failed");
    require(state.level == LevelCap || state.xp < state.required, "Unconsumed threshold");
}
int main(int argc, char** argv)
{
    try
    {
        Record start[3] = {{0,0},{0,0},{1,0}};
        checkMigration(start);
        require(start[0].level == 1 && total(start) == 0, "New character baseline");
        Record uneven[3] = {{1,0},{2,0},{3,0}};
        checkMigration(uneven);
        require(uneven[0].level == 2 && uneven[0].xp == 3 && uneven[1].xp == 3 && uneven[2].xp == 2,
            "Uneven golden migration");
        if (argc > 1)
        {
            Record legacy[3] = {{1,0},{2,0},{3,0}};
            auto bytes = oldSave(legacy);
            std::ofstream(std::string(argv[1]) + "/legacy-uneven.skill-record", std::ios::binary).write(
                reinterpret_cast<const char*>(bytes.data()), bytes.size());
            bytes = oldSave(uneven);
            std::ofstream(std::string(argv[1]) + "/canonical-uneven.skill-record", std::ios::binary).write(
                reinterpret_cast<const char*>(bytes.data()), bytes.size());
        }
        for (int a = 0; a <= LevelCap; ++a)
            for (int b = 0; b <= LevelCap; ++b)
                for (int c = 0; c <= LevelCap; ++c)
                {
                    Record r[3] = {{a,0},{b,0},{c,0}}; checkMigration(r);
                }
        std::mt19937 random(0x4d5352);
        for (int n = 0; n < 30000; ++n)
        {
            Record r[3];
            for (auto& item : r) item = {static_cast<int>(random() % 46), random() % (MaxStoredXP + 1)};
            checkMigration(r);
        }
        for (int level = 1; level < LevelCap; ++level)
        {
            Record r[3]; require(SetLevel(r, level), "Set level");
            XP accepted = 0; int levels = 0;
            const XP threshold = 3 * TrackCost(level);
            require(Award(r, threshold - 1, accepted, levels) && accepted == threshold - 1 && levels == 0,
                "Early threshold crossing");
            require(Award(r, 1, accepted, levels) && accepted == 1 && levels == 1,
                "Exact threshold crossing lost/delayed");
            require(r[0].level == level + 1 && r[0].xp + r[1].xp + r[2].xp == 0, "Crossing remainder");
        }
        Record capped[3] = {{45,2147483647},{45,2147483647},{45,2147483647}};
        checkMigration(capped);
        const XP capBefore = total(capped);
        XP accepted; int levels;
        require(Award(capped, std::numeric_limits<std::int64_t>::max(), accepted, levels) && accepted == 0 && total(capped) == capBefore,
            "Cap overflow/residual loss");
        Record large[3]; SetLevel(large, 1);
        require(Award(large, std::numeric_limits<std::int64_t>::max(), accepted, levels), "Large award rejected");
        require(accepted == 3 * EarnedBefore(45) && levels == 44 && large[0].level == 45, "Large award cap");
        for (Record invalid : {Record{-1,0}, Record{46,0}, Record{100,0}, Record{32767,0},
             Record{1,-1}, Record{1,2147483648LL}, Record{1,4294967295LL}})
        {
            Record r[3] = {invalid,{1,0},{1,0}}, copy[3] = {invalid,{1,0},{1,0}};
            require(!Normalize(r) && equal(r,copy), "Invalid migration changed state");
            require(!Award(r, 1, accepted, levels) && equal(r,copy), "Invalid award changed state");
        }
        Record negative[3] = {{2,1},{2,1},{2,1}}, original[3] = {{2,1},{2,1},{2,1}};
        require(!Award(negative, -1, accepted, levels) && equal(negative, original), "Negative award accepted");

        // Real CStat and real mslist/msstring code, compiled from game source.
        statlist stats; CStat::InitStatList(stats);
        int weapons = 0;
        for (int n = 0; n < STATS_TOTAL; ++n)
        {
            CStat& stat = stats[n];
            for (unsigned p = 0; p < stat.m_SubStats.size(); ++p)
            { stat.m_SubStats[p].Value = static_cast<int>(p) + 2; stat.m_SubStats[p].Exp = p * 17; }
            if (stat.IsUnifiedWeapon())
            {
                ++weapons;
                require(stat.NormalizeWeapon(), "CStat migration");
                require(stat.Value(0) == stat.Value(1) && stat.Value(1) == stat.Value(2), "Getter alias differs");
                for (const char* alias : {"prof", "Proficiency", "Balance", "Power"})
                    require(stat.Value(GetSubSkillByName(alias)) == stat.Value(), "Script alias differs");
                require(stat.Value(-1) == -1 && stat.Value(3) == -1, "Property bounds");
                require(stat.SetWeaponLevel(10), "CStat setter");
                int added = 0, gained = 0;
                require(stat.AwardWeaponXP(15, added, gained) && added == 15 && gained == 0, "CStat award");
                State progress{}; require(stat.WeaponProgress(progress) && progress.xp == 15, "Single pool progress");
                require(stat.SetWeaponLevel(12) && stat.Value(0) == 12 && stat.Value(2) == 12, "Setter alias");
                require(stat.WeaponProgress(progress) && progress.xp == 0, "Explicit setter XP reset");
                require(!stat.SetWeaponLevel(46) && stat.Value() == 12, "Setter cap rejection");
            }
            else
            {
                require(stat.NormalizeWeapon(), "Nonweapon no-op");
                int added = 0, gained = 0;
                require(!stat.AwardWeaponXP(999, added, gained) && !stat.SetWeaponLevel(20), "Nonweapon became unified");
                for (unsigned p = 0; p < stat.m_SubStats.size(); ++p)
                    require(stat.Value(p) == static_cast<int>(p) + 2 && stat.m_SubStats[p].Exp == p * 17,
                        "Magic/Parry/natural record changed");
            }
        }
        require(weapons == 7 && stats[SKILL_SPELLCASTING].m_SubStats.size() == 5 && stats[SKILL_PARRY].m_SubStats.size() == 1,
            "Skill record layout changed");
        std::cout << "PASS " << checks << " assertions; 97336 level triples; 30000 seeded XP migrations; 44 thresholds; real CStat aliases, magic/Parry/natural isolation.\n";
        return 0;
    }
    catch (const std::exception& error)
    { std::cerr << "FAIL after " << checks << ": " << error.what() << '\n'; return 1; }
}
