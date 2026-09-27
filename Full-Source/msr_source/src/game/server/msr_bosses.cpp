// Boss respawn timers for merged "big world" maps. See msr_bosses.h.

#include "msdllheaders.h"
#include "player/player.h"
#include "monsters/msmonster.h"
#include "script.h"
#include "svglobals.h"
#include "msr_regions.h"
#include "msr_worldstate.h"
#include "msr_bosses.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <map>
#include <set>
#include <string>
#include <vector>

void MSR_WorldStateDump(const char *prefix); // msr_worldstate.cpp

namespace
{
cvar_t g_BossCooldown = {"ms_boss_cooldown", "1800", FCVAR_SERVER}; // seconds a killed boss stays away unless the builder gave it its own; 0 = off for those

// Every boss slot seen on this map, so the command still knows a boss while its region is
// unloaded (its spawner is gone then): configured ones, and derived ones that have a timer.
struct boss_t
{
	std::string region;
	bool configured = false;
	float cooldown = 0;
	std::string open;
};
std::map<std::string, boss_t> g_Bosses;
std::string g_BossesMap;

// Always printed (dedicated console, -log file and rcon replies), unlike ALERT(at_console).
void Log(const char *fmt, ...)
{
	char text[1024];
	va_list args;
	va_start(args, fmt);
	vsnprintf(text, sizeof(text), fmt, args);
	va_end(args);
	g_engfuncs.pfnServerPrint(text);
}

// Keys are per map world anyway; this only drops what an earlier map left behind
void CheckMap()
{
	const char *map = STRING(gpGlobals->mapname);
	if (g_BossesMap != map)
	{
		g_Bosses.clear();
		g_BossesMap = map;
	}
}

int Minutes(double seconds)
{
	return (int)std::ceil(seconds / 60.0);
}

// Lowercase, key-safe, no dots (the key is split on them)
std::string KeyPart(const char *text)
{
	std::string out;
	for (const char *p = text; p && *p; p++)
	{
		const char c = (char)tolower((unsigned char)*p);
		out += ((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_' || c == '-') ? c : '_';
	}
	return out;
}

std::string RegionName(int region)
{
	const msr_region_t *r = region != REGION_NONE ? MSRegions::Get(region) : nullptr;
	return KeyPart(r ? r->name.c_str() : STRING(gpGlobals->mapname));
}

// "boss.<region>.<id>" -> region
std::string KeyRegion(const std::string &key)
{
	const size_t start = key.find('.');
	const size_t end = start == std::string::npos ? start : key.find('.', start + 1);
	return end == std::string::npos ? std::string() : key.substr(start + 1, end - start - 1);
}

// The damage list holds garbage in slots no player has hit (MarkDamage writes a player's id
// first), so only slots carrying a connected player's id count, as for XP in CMSMonster::Killed.
bool KilledByPlayer(CMSMonster *pMonster)
{
	for (int i = 1; i <= gpGlobals->maxClients && i <= (int)pMonster->m_PlayerDamage.size(); i++)
	{
		CBaseEntity *pEntity = UTIL_PlayerByIndex(i);
		if (!pEntity || !pEntity->IsPlayer())
			continue;
		CBasePlayer *pPlayer = (CBasePlayer *)pEntity;
		msstring id = pPlayer->AuthID() + "_" + pPlayer->m_CharacterNum;
		const playerdamage_t &damage = pMonster->m_PlayerDamage[i - 1];
		if (FStrEq(id, damage.msId) && damage.dmgInTotal > 0)
			return true;
	}
	return false;
}

bool IsBossSlot(const msr_bossslot_t &slot)
{
	if (slot.configured || g_Bosses.count(slot.key) || WorldState::TimeLeft(slot.key) != 0)
		return true;
	if (!slot.pAlive)
		return false;
	IScripted *pScripted = slot.pAlive->GetScripted();
	return pScripted && atoi(pScripted->GetFirstScriptVar("NPC_IS_BOSS")) > 0;
}

// Boss keys matching what an admin typed: "all", a full key, "<region>.<id>" or "<id>"
std::vector<std::string> Resolve(const std::string &what, const std::vector<msr_bossslot_t> &slots)
{
	std::set<std::string> known;
	for (const auto &kv : g_Bosses)
		known.insert(kv.first);
	for (const auto &slot : slots)
		if (IsBossSlot(slot))
			known.insert(slot.key);
	std::vector<std::string> out;
	for (const std::string &key : known)
	{
		const std::string region = KeyRegion(key);
		const std::string id = region.empty() ? std::string() : key.substr(5 + region.size() + 1);
		if (what == "all" || what == key || "boss." + what == key || what == id)
			out.push_back(key);
	}
	return out;
}

void List()
{
	std::vector<msr_bossslot_t> slots;
	MSR_BossSlots(slots);
	std::map<std::string, std::vector<const msr_bossslot_t *>> byKey;
	for (const auto &slot : slots)
		if (IsBossSlot(slot))
			byKey[slot.key].push_back(&slot);
	for (const auto &kv : g_Bosses)
		byKey[kv.first]; // region not loaded: no slot
	Log("MSR: bosses on %s: %u, ms_boss_cooldown %.0f s, world state %s\n", STRING(gpGlobals->mapname), (unsigned int)byKey.size(),
		g_BossCooldown.value, WorldState::Online() ? "saved to FN" : WorldState::Loaded() ? "in memory only" : "not loaded");
	for (const auto &kv : byKey)
	{
		const std::string &key = kv.first;
		const auto known = g_Bosses.find(key);
		const msr_bossslot_t *pSlot = kv.second.empty() ? nullptr : kv.second.front();
		const msr_bossslot_t *pAlive = nullptr;
		bool held = false, opened = false;
		for (const msr_bossslot_t *s : kv.second)
		{
			if (s->pAlive && !pAlive)
				pAlive = s;
			held |= s->held;
			opened |= s->opened;
		}
		const double left = WorldState::TimeLeft(key.c_str());
		const std::string region = KeyRegion(key);
		char state[160];
		if (pAlive)
			snprintf(state, sizeof(state), "alive (hp %.0f/%.0f)", pAlive->pAlive->pev->health, pAlive->pAlive->MaxHP());
		else if (left > 0) // "kept from spawning": its spawner tried and the hold stopped it
			snprintf(state, sizeof(state), "held, %d min left%s%s", Minutes(left), held ? ", kept from spawning" : "", opened ? ", exits opened" : "");
		else if (opened)
			snprintf(state, sizeof(state), "held until %s reloads (exits opened)", region.c_str());
		else
			snprintf(state, sizeof(state), "ready");
		std::string where;
		if (pSlot)
			where = std::string("spawner ") + pSlot->spawner + " in " + region;
		else
		{
			const int r = MSRegions::Find(region.c_str());
			where = r != REGION_NONE && !MSRegions::IsLoaded(r) ? region + " not loaded" : "no spawner now in " + region;
		}
		const bool configured = pSlot ? pSlot->configured : (known != g_Bosses.end() && known->second.configured);
		const float cooldown = pSlot ? pSlot->cooldown : (known != g_Bosses.end() ? known->second.cooldown : 0);
		const std::string open = pSlot ? pSlot->open : (known != g_Bosses.end() ? known->second.open : std::string());
		std::string extra = configured ? "configured, cooldown " + std::to_string((int)MSBosses::Cooldown(cooldown)) + " s" : std::string("flagged boss (NPC_IS_BOSS)");
		if (!open.empty())
			extra += ", open " + open;
		Log("  %s: %s | %s | %s\n", key.c_str(), state, where.c_str(), extra.c_str());
	}
}

void Reset(const std::string &what)
{
	std::vector<msr_bossslot_t> slots;
	MSR_BossSlots(slots);
	const std::vector<std::string> keys = Resolve(what, slots);
	if (keys.empty())
	{
		Log("MSR: no boss matches '%s' (msr_bosses lists them)\n", what.c_str());
		return;
	}
	int reset = 0;
	for (const std::string &key : keys)
	{
		if (WorldState::TimeLeft(key.c_str()) == 0)
		{
			if (what != "all")
				Log("MSR: boss %s has no timer\n", key.c_str());
			continue;
		}
		WorldState::Unset(key.c_str());
		MSR_BossRetry(key.c_str());
		reset++;
		Log("MSR: boss %s timer reset\n", key.c_str());
		for (const auto &slot : slots)
			if (key == slot.key && slot.opened)
			{
				Log("MSR: boss %s already opened its exits here: it stays away until %s reloads\n", key.c_str(), KeyRegion(key).c_str());
				break;
			}
	}
	if (what == "all")
		Log("MSR: %d boss timers reset\n", reset);
}

// Testing: kill a boss the way players would, so the normal death path runs (timer, killtarget,
// perishtarget, chests). The damage is credited to the first player (player 1 normally) without
// any skill damage, so it earns no XP.
void Kill(const std::string &what)
{
	std::vector<msr_bossslot_t> slots;
	MSR_BossSlots(slots);
	const std::vector<std::string> keys = Resolve(what, slots);
	const msr_bossslot_t *pTarget = nullptr;
	int alive = 0;
	for (const std::string &key : keys)
		for (const auto &slot : slots)
			if (key == slot.key && slot.pAlive)
			{
				if (!pTarget)
					pTarget = &slot;
				alive++;
				break;
			}
	if (!pTarget)
	{
		Log("MSR: boss '%s' is not alive now (msr_bosses lists them)\n", what.c_str());
		return;
	}
	if (alive > 1)
	{
		Log("MSR: '%s' names %d live bosses; give <region>.<id> or the key\n", what.c_str(), alive);
		return;
	}
	CBasePlayer *pPlayer = nullptr;
	for (int i = 1; i <= gpGlobals->maxClients && !pPlayer; i++)
	{
		CBaseEntity *pEntity = UTIL_PlayerByIndex(i);
		if (pEntity && pEntity->IsPlayer())
			pPlayer = (CBasePlayer *)pEntity;
	}
	CMSMonster *pMonster = pTarget->pAlive;
	const int slot = pPlayer ? pPlayer->entindex() - 1 : -1;
	if (!pPlayer || slot < 0 || slot >= (int)pMonster->m_PlayerDamage.size())
	{
		Log("MSR: msr_bosses kill needs a player on the server (the kill is credited to one)\n");
		return;
	}
	playerdamage_t &damage = pMonster->m_PlayerDamage[slot];
	msstring id = pPlayer->AuthID() + "_" + pPlayer->m_CharacterNum;
	if (!FStrEq(id, damage.msId))
	{
		damage.Clear();
		strncpy(damage.msId, id, sizeof(damage.msId) - 1);
		damage.msId[sizeof(damage.msId) - 1] = 0;
	}
	const float hp = std::max(pMonster->pev->health, 1.0f);
	damage.dmgInTotal += hp;
	Log("MSR: boss %s killed by msr_bosses (credited to %s)\n", pTarget->key, STRING(pPlayer->pev->netname));
	pMonster->TakeDamage(pPlayer->pev, pPlayer->pev, hp + 1.0f, DMG_GENERIC);
	if (pMonster->IsAlive()) // its script kept it standing
		pMonster->Killed(pPlayer->pev, GIB_NEVER);
}

// "msr_bosses [list | reset <id|key|all> | kill <id>]"
void Command()
{
	CheckMap();
	const std::string sub = CMD_ARGC() > 1 ? CMD_ARGV(1) : "list";
	if (sub == "list")
	{
		List();
		MSR_WorldStateDump("boss.");
	}
	else if (sub == "reset" && CMD_ARGC() > 2)
		Reset(CMD_ARGV(2));
	else if (sub == "kill" && CMD_ARGC() > 2)
		Kill(CMD_ARGV(2));
	else
		Log("usage: msr_bosses [list | reset <id|key|all> | kill <id>]\n");
}
} // namespace

namespace MSBosses
{
void Init()
{
	CVAR_REGISTER(&g_BossCooldown);
	g_engfuncs.pfnAddServerCommand((char *)"msr_bosses", Command);
}

float Cooldown(float configured)
{
	return configured > 0 ? configured : g_BossCooldown.value;
}

bool MakeKey(char *out, size_t size, int region, const char *id, const float *origin)
{
	if (!out || !size)
		return false;
	out[0] = 0;
	std::string key = "boss." + RegionName(region) + ".";
	if (id && *id)
		key += KeyPart(id);
	else if (origin)
	{
		char pos[64];
		snprintf(pos, sizeof(pos), "%d_%d_%d", (int)std::floor(origin[0] + 0.5f), (int)std::floor(origin[1] + 0.5f), (int)std::floor(origin[2] + 0.5f));
		key += pos;
	}
	else
		return false;
	if (key.size() >= size || !WorldState::ValidKey(key.c_str(), true))
		return false;
	strncpy(out, key.c_str(), size);
	return true;
}

void Seen(const char *key, int region, bool configured, float cooldown, const char *open)
{
	if (!key || !*key)
		return;
	CheckMap();
	if (!configured && (g_Bosses.count(key) || WorldState::TimeLeft(key) == 0))
		return;
	boss_t &boss = g_Bosses[key];
	boss.region = RegionName(region);
	boss.configured = configured;
	boss.cooldown = cooldown;
	boss.open = open ? open : "";
}

bool Died(const char *key, bool configured, float cooldown, CMSMonster *pMonster)
{
	if (!key || !*key || !pMonster)
		return false;
	// Unconfigured slots: only a flagged boss, and only on merged maps (on a normal map a held boss
	// with no "open" list could block the map's progression for the whole cooldown)
	if (!configured)
	{
		IScripted *pScripted = pMonster->GetScripted();
		if (!MSRegions::Active() || !pScripted || atoi(pScripted->GetFirstScriptVar("NPC_IS_BOSS")) <= 0)
			return false;
	}
	if (!KilledByPlayer(pMonster))
	{
		Log("MSR: boss %s died without player damage; no respawn timer\n", key);
		return false;
	}
	const float seconds = Cooldown(cooldown);
	if (seconds <= 0)
		return false;
	char value[32];
	snprintf(value, sizeof(value), "%.0f", WorldState::Now());
	WorldState::Set(key, value, seconds);
	CheckMap();
	boss_t &boss = g_Bosses[key];
	if (boss.region.empty())
	{
		boss.region = KeyRegion(key);
		boss.configured = configured;
		boss.cooldown = cooldown;
	}
	Log("MSR: boss %s killed, back in %d min\n", key, Minutes(seconds));
	return true;
}

void Held(const char *key, double secondsLeft, const char *spawner, const char *opened)
{
	Log("MSR: boss %s held, back in %d min (spawner %s)\n", key, Minutes(secondsLeft), spawner && *spawner ? spawner : "-");
	if (opened && *opened)
		Log("MSR: boss %s: fired %s as if it had died; it stays away until its region reloads\n", key, opened);
}
} // namespace MSBosses
