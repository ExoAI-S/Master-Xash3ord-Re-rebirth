#include "sharedutil.h"
#include "statdefs.h"
#include "stats.h"
#include <math.h>
#include <string.h>

statinfo_t NatStatList[6] =
{
	{"Strength"},
	{"Agility"},
	{"Concentration"},
	{"Awareness"},
	{"Fitness"},
	{"Wisdom"},
};

skillstatinfo_t SkillStatList[9] =
{
	{"Swordsmanship", "swordsmanship", STAT_PROP_TOTAL},
	{"Martial Arts", "martialarts", STAT_PROP_TOTAL},
	{"Small Arms", "smallarms", STAT_PROP_TOTAL},
	{"Axe Handling", "axehandling", STAT_PROP_TOTAL},
	{"Blunt Arms", "bluntarms", STAT_PROP_TOTAL},
	{"Archery", "archery", STAT_PROP_TOTAL},
	//	"Shield handling",
	//	"Two-handed weapons",
	//	"Dual weapons",
	{"Spell Casting", "spellcasting", STAT_MAGIC_TOTAL},
	{"Parry", "parry", 1},
	{"Pole Arms", "polearms", STAT_PROP_TOTAL}, // MiB JUL2010_02 - Pole Arms!
	//	"Spell Preparation",
	//	"Swimming",
	//	"Pickpocket", true,
};

const char* SkillTypeList[3] =
{
	"Proficiency",
	"Balance",
	"Power" 
};

const char* SpellTypeList[5] =
{
	"Fire",
	"Ice",
	"Lightning",
	"Divination",
	"Affliction",
};

int GetSkillStatByName(const char* pszName) // Index lookup by name (Skill stats only)
{
	for (unsigned int i = 0; i < SKILL_MAX_STATS; i++)
		if (!_stricmp(pszName, SkillStatList[i].DllName))
			return SKILL_FIRSTSKILL + i;
	return -1;
}
const char* GetSkillName(int Skill) // Name lookup by index (Any stat)
{
	if (Skill < 0 || Skill >= STATS_TOTAL)
		return "(Invalid Skill)";

	if (Skill < SKILL_FIRSTSKILL)
		return NatStatList[Skill].Name;

	return SkillStatList[Skill - SKILL_FIRSTSKILL].Name;
}
int GetSubSkillByName(const char* pszName)
{
	if (!_stricmp(pszName, "prof")) // alias for proficiency
		return 0;
	for (unsigned int i = 0; i < STAT_PROP_TOTAL; i++)
		if (!_stricmp(pszName, SkillTypeList[i]))
			return i;
	for (unsigned int i = 0; i < STAT_MAGIC_TOTAL; i++)
		if (!_stricmp(pszName, SpellTypeList[i]))
			return i;
	return -1;
}
int GetNatStatByName(const char* pszName)
{
	for (unsigned int i = 0; i < NATURAL_MAX_STATS; i++)
		if (!_stricmp(pszName, NatStatList[i].Name))
			return i;
	return -1;
}
// Converts stat.prop into valid indices
void GetStatIndices(const char* Name, int& Stat, int& Prop)
{
	msstring FullName = Name;

	msstring StatName = FullName.thru_char(".");
	msstring PropName = FullName.substr(StatName.len() + 1);
	if (StatName.len())
		Stat = GetSkillStatByName(StatName);
	if (PropName.len())
		Prop = GetSubSkillByName(PropName);
}

CSubStat::~CSubStat()
{
}

CSubStat& CSubStat::operator=(const CSubStat& Other)
{
	Value = Other.Value;
	Exp = Other.Exp;
	return *this;
}

bool CStat::IsUnifiedWeapon() const
{
    return m_Type == STAT_SKILL && m_SubStats.size() == UnifiedWeapon::Tracks;
}

bool CStat::WeaponProgress(UnifiedWeapon::State& state) const
{
    if (!IsUnifiedWeapon()) return false;
    UnifiedWeapon::Record records[UnifiedWeapon::Tracks];
    for (int n = 0; n < UnifiedWeapon::Tracks; ++n)
        records[n] = { m_SubStats[n].Value, static_cast<std::int64_t>(m_SubStats[n].Exp) };
    return UnifiedWeapon::Read(records, state);
}

bool CStat::NormalizeWeapon()
{
    if (!IsUnifiedWeapon()) return true;
    UnifiedWeapon::State state{};
    UnifiedWeapon::Record records[UnifiedWeapon::Tracks];
    if (!WeaponProgress(state) || !UnifiedWeapon::Write(state, records)) return false;
    for (int n = 0; n < UnifiedWeapon::Tracks; ++n)
    {
        m_SubStats[n].Value = records[n].level;
        m_SubStats[n].Exp = static_cast<ulong>(records[n].xp);
    }
    return true;
}

bool CStat::SetWeaponLevel(int level)
{
    if (!IsUnifiedWeapon()) return false;
    UnifiedWeapon::Record records[UnifiedWeapon::Tracks];
    if (!UnifiedWeapon::SetLevel(records, level)) return false;
    for (int n = 0; n < UnifiedWeapon::Tracks; ++n)
    {
        m_SubStats[n].Value = records[n].level;
        m_SubStats[n].Exp = static_cast<ulong>(records[n].xp);
    }
    return true;
}

bool CStat::AwardWeaponXP(int amount, int& accepted, int& levels)
{
    accepted = 0; levels = 0;
    if (!IsUnifiedWeapon()) return false;
    UnifiedWeapon::Record records[UnifiedWeapon::Tracks];
    for (int n = 0; n < UnifiedWeapon::Tracks; ++n)
        records[n] = { m_SubStats[n].Value, static_cast<std::int64_t>(m_SubStats[n].Exp) };
    UnifiedWeapon::XP added = 0;
    if (!UnifiedWeapon::Award(records, amount, added, levels)) return false;
    accepted = static_cast<int>(added); // Award input is a nonnegative int.
    for (int n = 0; n < UnifiedWeapon::Tracks; ++n)
    {
        m_SubStats[n].Value = records[n].level;
        m_SubStats[n].Exp = static_cast<ulong>(records[n].xp);
    }
    return true;
}

int CStat::operator=(int Equals)
{
    if (IsUnifiedWeapon()) { SetWeaponLevel(Equals); return Value(); }
	int iAdd = int(Equals / (float)m_SubStats.size());
	int iExtra = Equals % m_SubStats.size(), i = 0;

	for (i = 0; i < (signed)m_SubStats.size(); i++)
		m_SubStats[i].Value = iAdd;

	for (iExtra; iExtra > 0; iExtra--)
	{
		int iLowestStat = 0;
		for (i = 0; i < (signed)m_SubStats.size(); i++)
			if (m_SubStats[i].Value < m_SubStats[iLowestStat].Value)
				iLowestStat = i;
		m_SubStats[iLowestStat].Value++;
	}

	return Value();
}

int CStat::operator+=(int Add)
{
    if (IsUnifiedWeapon())
    {
        const std::int64_t level = static_cast<std::int64_t>(Value()) + Add;
        if (level >= 0 && level <= UnifiedWeapon::LevelCap) SetWeaponLevel(static_cast<int>(level));
        return Value();
    }
	for (Add; abs(Add) > 0; Add -= Add / abs(Add))
	{
		int iLowestStat = 0, i;
		for (i = 0; i < (signed)m_SubStats.size(); i++)
			if (m_SubStats[i].Value < m_SubStats[iLowestStat].Value)
				iLowestStat = i;
		m_SubStats[iLowestStat].Value += Add / abs(Add);
	}
	return Value();
}

int CStat::Value()
{
    // Server load/set/award paths keep all three values identical. Reading a
    // base never derives a new level from a partially received XP message.
    if (IsUnifiedWeapon()) return m_SubStats[0].Value == 0 ? 1 : m_SubStats[0].Value;
	int Total = 0;
	unsigned int iSubStats = m_SubStats.size();
	for (unsigned int i = 0; i < iSubStats; i++)
		Total += m_SubStats[i].Value;

	// (x + floor(y / 2)) / y
	// As long as X is not negative, and Y is >= 2, this will work as expected. It
	// does rounding by adding half of the divisor to the dividend, then dividing 
	// that by the divisor.
	// 
	// Proof:
	// - x=3, y=5: [(3 + (5 / 2)) / 5] -> [(3 + 2) / 5] -> [5 / 5] -> [1]
	// - x=2, y=5: [(2 + (5 / 2)) / 5] -> [(2 + 2) / 5] -> [4 / 5] -> [0]
	// - x=2, y=4: [(2 + (4 / 2)) / 4] -> [(2 + 2) / 4] -> [4 / 4] -> [1]
	// - x=1, y=4: [(1 + (4 / 2)) / 4] -> [(1 + 2) / 4] -> [3 / 4] -> [0]
	// - x=2, y=3: [(2 + (3 / 2)) / 3] -> [(2 + 1) / 3] -> [3 / 3] -> [1]
	// - x=1, y=3: [(1 + (3 / 2)) / 3] -> [(1 + 1) / 3] -> [2 / 3] -> [0]
	// - x=-3, y=-3: [(-3 + (-3 / 2)) / -3] -> [(-3 + -1) / -3] -> [-4 / -3] -> [1]
	// 
	// This breaks if total is negative:
	// - x=-3, y=3: [(-3 + (3 / 2)) / 3] -> [(-3 + 1) / 3] -> [-2 / 3] -> [0] (should be -1)
	// but can be fixed by changing it to: (abs(x) + floor(y / 2)) / y * sign(x)
	int iVal = (Total + (iSubStats / 2)) / iSubStats;
	
	// if value is 0 then return 1, we don't want skills to be less than 1.
	return (iVal == 0) ? 1 : iVal;
}

int CStat::Value(int StatProperty)
{
	if (StatProperty < 0 || StatProperty >= (signed)m_SubStats.size())
		return -1;

	return IsUnifiedWeapon() ? Value() : m_SubStats[StatProperty].Value;
}

void CStat::OutDate() // Makes sure an update will be sent next frame
{
	bNeedsUpdate = true;
}

void CStat::Update() // Updates the stat to current - no updates sent
{
	bNeedsUpdate = false;

	for (unsigned int i = 0; i < m_SubStats.size(); i++)
	{
		m_SubStats[i].OldValue = m_SubStats[i].Value;
		m_SubStats[i].OldExp = m_SubStats[i].Exp;
	}
}

bool CStat::Changed()
{
	if (bNeedsUpdate)
		return true;

	// If any values changed -> update.
	for (unsigned int i = 0; i < m_SubStats.size(); i++)
		if ((m_SubStats[i].Exp != m_SubStats[i].OldExp) || (m_SubStats[i].Value != m_SubStats[i].OldValue))
			return true;

	return false;
}

bool CStat::operator!=(const CStat& Other)
{
	// Just check the substats
	for (unsigned int i = 0; i < m_SubStats.size(); i++)
	{
		if (i >= (signed)Other.m_SubStats.size())
			break;
		if (m_SubStats[i].Value != Other.m_SubStats[i].Value)
			return true;
		if (m_SubStats[i].Exp != Other.m_SubStats[i].Exp)
			return true;
	}
	return false;
}

void CStat::InitStatList(statlist& Stats)
{
	Stats.reserve_once(STATS_TOTAL, STATS_TOTAL);
	for (unsigned int i = 0; i < STATS_TOTAL; i++)
	{
		const char* Name = (i < NATURAL_MAX_STATS) ? NatStatList[i].Name : SkillStatList[i - NATURAL_MAX_STATS].DllName;
		CStat::skilltype_e Type = (i < NATURAL_MAX_STATS) ? CStat::STAT_NAT : CStat::STAT_SKILL;
		CStat& Stat = Stats[i];
		Stat.m_Name = Name;
		Stat.m_Type = Type;
		int iSubStats = (Stat.m_Type == CStat::STAT_NAT) ? 1 : SkillStatList[i - NATURAL_MAX_STATS].StatCount;
		Stat.m_SubStats.reserve_once(iSubStats, iSubStats);
	}
}
