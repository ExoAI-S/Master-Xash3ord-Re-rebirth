// Per-region awareness for merged "big world" maps. See msr_regions.h.

#include "msdllheaders.h"
#include "player/player.h"
#include "monsters/msmonster.h"
#include "weapons/genericitem.h"
#include "script.h"
#include "svglobals.h"
#include "store.h"
#include "msr_regions.h"
#include "msr_bigworld.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <unordered_set>
#include <utility>
#include <vector>

void MSR_QuickStartSpawner(CBaseEntity *pEntity); // msmapents.cpp
extern double g_MSRScriptLoadMs, g_MSRScriptParseMs, g_MSRScriptPrecacheMs, g_MSRScriptTopMs; // script.cpp profiling
extern int g_MSRScriptFiles;

namespace
{
std::vector<msr_region_t> g_Regions;

// A map entity as the engine spawned it at load: classname and key/values in file order
// (after the engine's own rewrites), which is all a fresh copy needs.
struct record_t
{
	std::string classname;
	std::vector<std::pair<std::string, std::string>> pairs;
	int region = REGION_NONE;
	bool keep = false;		  // never unloaded (spawn points, teleport destinations, links, exits)
	edict_t *live = nullptr;  // current instance
	int liveSerial = 0;
};
std::vector<record_t> g_Records;
bool g_Recording = false;
bool g_Replaying = false;
edict_t *g_PendingEdict = nullptr;
record_t g_Pending;
float g_NextLifecycleCheck = 0;

// A region being re-created (see "Re-creating a region" below)
struct held_t
{
	edict_t *pent;
	int serial;
	float nextthink; // as its Spawn left it
	float createdAt;
};
struct load_t
{
	int region = REGION_NONE;
	std::string why;
	size_t cursor = 0; // next record to look at
	std::vector<held_t> created; // the region's map entities
	std::vector<held_t> extra;	 // what their spawning made (gear, createnpc, delayed triggers): held, not activated
	std::vector<int> serials;	 // edict serial numbers before the current entity spawned (-1: free)
	bool stepping = false;		 // inside StepLoad (no nested loads)
	bool ahead = false;			 // started ahead of a player (not for one arriving)
	int failed = 0, frames = 0, scriptFiles = 0;
	double workMs = 0, maxStepMs = 0, scriptMs = 0, parseMs = 0;
	float startedAt = 0;
	std::vector<std::pair<std::string, double>> classTime; // profiling: ms per class
	std::vector<std::pair<double, std::string>> slowest;   // and the costliest single entities
};
load_t g_Load;

// Walk-through links between regions (the builder's trigger_teleports) and where they lead
struct region_link_t
{
	edict_t *pent;
	int serial;
	int toRegion;
};
std::vector<region_link_t> g_Links;

cvar_t g_UnloadTime = {"ms_region_unload_time", "600", FCVAR_SERVER}; // seconds empty before a region unloads; 0 = never
cvar_t g_LoadBudget = {"ms_region_load_budget", "10", FCVAR_SERVER};  // ms per server frame for a region loading ahead of a player
cvar_t g_PreloadRange = {"ms_region_preload_range", "1500", FCVAR_SERVER}; // start loading when a player is this close to a way in; 0 = off
cvar_t g_MemLogMinutes = {"ms_mem_log_minutes", "10", FCVAR_SERVER};		// "MSR: memory" log line every N minutes; 0 = only at map start
float g_NextMemLog = 0;

// Map entities that stay loaded in every region: players and characters point at them
// (spawn points by name, teleport destinations, exits and town areas by pointer).
// ambient_generic too: its load-time loop sits in every late joiner's connection data under
// the original entity number, which a re-created copy could not stop or replace.
const char *const kKeepClasses[] = {"worldspawn", "info_msr_region", "ms_player_spawn", "ms_player_begin", "ms_player_spec",
	"ms_player_spawn_dis", "info_player_start", "info_player_deathmatch", "info_teleport_destination", "msarea_transition",
	"msarea_town", "light_environment", "infodecal", "ambient_generic"};

// Short-lived helpers region content leaves behind (clones, temp entities, gibs, corpses).
const char *const kTransientClasses[] = {"multi_manager", "mstrig_multi", "ms_npcscript", "mstrig_act", "gib", "corpse"};

bool ClassIn(const char *classname, const char *const *list, size_t count)
{
	for (size_t i = 0; i < count; i++)
		if (FStrEq(classname, list[i]))
			return true;
	return false;
}

bool LiveValid(const record_t &rec)
{
	return rec.live && !rec.live->free && rec.live->pvPrivateData && rec.live->serialnumber == rec.liveSerial;
}

// Always printed (dedicated console and -log file), unlike ALERT(at_console).
void Log(const char *fmt, ...)
{
	char text[1024];
	va_list args;
	va_start(args, fmt);
	vsnprintf(text, sizeof(text), fmt, args);
	va_end(args);
	g_engfuncs.pfnServerPrint(text);
}

// Positions further than this outside a region's own geometry are "nowhere":
// the game master lives at (20000,-10000,-20000) and dynamic spawns park monsters
// at (40000,40000,4000) until they find a spot.
constexpr float kBoundsSlack = 512.0f;

void ParseVec(const char *text, float *out)
{
	float v[3] = {0, 0, 0};
	if (sscanf(text, "%f %f %f", &v[0], &v[1], &v[2]) == 3)
		for (int i = 0; i < 3; i++)
			out[i] = v[i];
}

std::vector<std::string> Tokens(const std::string &list)
{
	std::vector<std::string> out;
	size_t start = 0;
	while (start <= list.size())
	{
		size_t end = list.find(';', start);
		if (end == std::string::npos)
			end = list.size();
		if (end > start)
			out.push_back(list.substr(start, end - start));
		start = end + 1;
	}
	return out;
}

bool HasBounds(const msr_region_t &r)
{
	return r.maxs[0] > r.mins[0] && r.maxs[1] > r.mins[1] && r.maxs[2] > r.mins[2];
}

bool IsGameMaster(CBaseEntity *pEntity)
{
	if (pEntity == g_pGameMasterEntity)
		return true;
	return pEntity->pev->netname && FStrEq(STRING(pEntity->pev->netname), "-game_master");
}

void RollWeather(msr_region_t &r)
{
	std::vector<std::string> list = Tokens(r.weather.empty() ? std::string("clear") : r.weather);
	r.currentWeather = list.empty() ? std::string("clear") : list[RANDOM_LONG(0, (long)list.size() - 1)];
}
} // namespace

// One entity per region, written by the builder right after worldspawn so the table
// exists before any monster or trigger spawns.
class CMSRegionInfo : public CBaseEntity
{
public:
	msr_region_t m_Def;
	int m_Index = -1;

	void KeyValue(KeyValueData *pkvd) override
	{
		const char *k = pkvd->szKeyName, *v = pkvd->szValue;
		pkvd->fHandled = TRUE;
		if (FStrEq(k, "region")) m_Def.name = v;
		else if (FStrEq(k, "index")) m_Index = atoi(v);
		else if (FStrEq(k, "cell_mins")) ParseVec(v, m_Def.cellMins);
		else if (FStrEq(k, "cell_maxs")) ParseVec(v, m_Def.cellMaxs);
		else if (FStrEq(k, "tight_mins")) ParseVec(v, m_Def.mins); // "mins"/"maxs" would land in pev
		else if (FStrEq(k, "tight_maxs")) ParseVec(v, m_Def.maxs);
		else if (FStrEq(k, "title")) m_Def.title = v;
		else if (FStrEq(k, "desc")) m_Def.desc = v;
		else if (FStrEq(k, "diff")) m_Def.diff = v;
		else if (FStrEq(k, "warnhp")) m_Def.warnhp = atoi(v);
		else if (FStrEq(k, "weather")) m_Def.weather = v;
		else if (FStrEq(k, "allownight")) m_Def.allownight = atoi(v) != 0;
		else if (FStrEq(k, "skyname")) m_Def.skyname = v;
		else if (FStrEq(k, "maxrange")) m_Def.maxrange = atof(v);
		else if (!strncmp(k, "no_logout_", 10))
		{
			float b[6];
			if (sscanf(v, "%f %f %f %f %f %f", &b[0], &b[1], &b[2], &b[3], &b[4], &b[5]) == 6)
				m_Def.noLogout.insert(m_Def.noLogout.end(), b, b + 6);
		}
		else if (FStrEq(k, "offset")) {}
		else
		{
			pkvd->fHandled = FALSE;
			CBaseEntity::KeyValue(pkvd);
		}
	}

	void Spawn() override
	{
		if (m_Def.name.empty())
			Log("MSR: info_msr_region without a region name ignored\n");
		else if (MSRegions::Find(m_Def.name.c_str()) != REGION_NONE)
			Log("MSR: duplicate info_msr_region '%s' ignored\n", m_Def.name.c_str());
		else
		{
			if (m_Index >= 0 && m_Index != (int)g_Regions.size())
				Log("MSR: region '%s' has index %d but spawned as %d\n", m_Def.name.c_str(), m_Index, (int)g_Regions.size());
			g_Regions.push_back(std::move(m_Def));
			m_Def = msr_region_t(); // entity destructors never run; hold no heap memory
			const msr_region_t &r = g_Regions.back();
			Log("MSR: region %d '%s' cell (%.0f %.0f %.0f)-(%.0f %.0f %.0f) sky %s weather %s\n",
				(int)g_Regions.size() - 1, r.name.c_str(), r.cellMins[0], r.cellMins[1], r.cellMins[2],
				r.cellMaxs[0], r.cellMaxs[1], r.cellMaxs[2], r.skyname.c_str(), r.weather.c_str());
		}
		UTIL_Remove(this);
	}
};
LINK_ENTITY_TO_CLASS(info_msr_region, CMSRegionInfo);

namespace MSRegions
{
void Clear()
{
	// New map: record its entities as they spawn (only kept if the map has a region table)
	g_Regions.clear();
	g_Records.clear();
	g_Recording = true;
	g_PendingEdict = nullptr;
	g_Pending = record_t();
	g_NextLifecycleCheck = 0;
	g_Load = load_t();
	g_Links.clear();
}
bool Active() { return !g_Regions.empty(); }
int Count() { return (int)g_Regions.size(); }

const msr_region_t *Get(int region)
{
	return (region >= 0 && region < (int)g_Regions.size()) ? &g_Regions[region] : NULL;
}

int Find(const char *name)
{
	if (!name)
		return REGION_NONE;
	for (size_t i = 0; i < g_Regions.size(); i++)
		if (!stricmp(g_Regions[i].name.c_str(), name))
			return (int)i;
	return REGION_NONE;
}

int At(const float *p)
{
	for (size_t i = 0; i < g_Regions.size(); i++)
	{
		const msr_region_t &r = g_Regions[i];
		bool inCell = true;
		for (int a = 0; a < 3 && inCell; a++)
			inCell = p[a] >= r.cellMins[a] && p[a] < r.cellMaxs[a];
		if (!inCell)
			continue;
		if (HasBounds(r))
			for (int a = 0; a < 3; a++)
				if (p[a] < r.mins[a] - kBoundsSlack || p[a] > r.maxs[a] + kBoundsSlack)
					return REGION_NONE;
		return (int)i;
	}
	return REGION_NONE;
}

int ForEntity(CBaseEntity *pEntity)
{
	if (!Active() || !pEntity || !pEntity->pev || pEntity->entindex() == 0 || IsGameMaster(pEntity))
		return REGION_NONE;
	if (pEntity->IsPlayer())
	{
		CBasePlayer *pPlayer = (CBasePlayer *)pEntity;
		return pPlayer->m_iRegion != REGION_NONE ? pPlayer->m_iRegion : At(pEntity->pev->origin);
	}
	if (pEntity->IsMSMonster())
	{
		CMSMonster *pMonster = (CMSMonster *)pEntity;
		// Pets, summons and hirelings follow their player between regions.
		if (CBasePlayer *pMaster = PlayerMaster(pMonster))
			return ForEntity(pMaster);
		if (pMonster->m_iHomeRegion != REGION_NONE)
			return pMonster->m_iHomeRegion;
	}
	// A linked brush entity keeps its region offset in pev->origin; use the middle of the
	// brush. Point entities (and brushes never linked, whose absmin/absmax stay zero) use
	// their origin.
	const bool linkedBrush = pEntity->pev->modelindex && pEntity->pev->absmin != pEntity->pev->absmax;
	Vector spot = linkedBrush ? pEntity->Center() : Vector(pEntity->pev->origin);
	return At(spot);
}

int ForScriptOwner(CBaseEntity *pOwner)
{
	// Only monsters/NPCs answer game.map.name and game.players.* for their own region;
	// players (CBasePlayer is a CMSMonster too), items and world scripts keep map-wide
	// answers (saves, bank, votes). They can ask game.map.region instead.
	if (!Active() || !pOwner || !pOwner->pev || !pOwner->IsMSMonster() || pOwner->IsPlayer() || IsGameMaster(pOwner))
		return REGION_NONE;
	return ForEntity(pOwner);
}

bool IsPresent(CBasePlayer *pPlayer)
{
	// Xash never frees a client's edict on disconnect; skip those and players still loading.
	return UTIL_IsConnectedPlayer(pPlayer) && pPlayer->m_iRegion != REGION_NONE && pPlayer->m_CharacterState == CHARSTATE_LOADED;
}

const char *NameOr(int region, const char *fallback)
{
	const msr_region_t *r = Get(region);
	return r ? r->name.c_str() : fallback;
}

const char *WeatherFor(int region)
{
	msr_region_t *r = (region >= 0 && region < (int)g_Regions.size()) ? &g_Regions[region] : NULL;
	if (!r)
		return "clear";
	if (r->currentWeather.empty())
		RollWeather(*r);
	return r->currentWeather.c_str();
}

bool DispatchWeather(CBaseEntity *pCaller, const char *eventName, const char *token)
{
	if (!Active() || !eventName || !token)
		return false;

	// Another script (an NPC's festive snow, a boss storm) changes only its own region,
	// like it changed only its own map before.
	const int callerRegion = pCaller && !IsGameMaster(pCaller) ? ForEntity(pCaller) : REGION_NONE;
	if (callerRegion != REGION_NONE)
	{
		g_Regions[callerRegion].currentWeather = token;
		Log("MSR: weather %s=%s (from %s)\n", g_Regions[callerRegion].name.c_str(), token, pCaller->DisplayName());
		for (int i = 1; i <= gpGlobals->maxClients; i++)
		{
			CBasePlayer *pPlayer = (CBasePlayer *)UTIL_PlayerByIndex(i);
			if (!pPlayer || !pPlayer->GetScripted() || ForEntity(pPlayer) != callerRegion)
				continue;
			msstringlist params;
			params.add(token);
			pPlayer->CallScriptEvent(eventName, &params);
		}
		return true;
	}

	// The game master's cycle: the home region keeps its token, the others roll their own.
	const int home = Find(STRING(gpGlobals->mapname));
	std::string rolled;
	for (size_t i = 0; i < g_Regions.size(); i++)
	{
		if ((int)i == home)
			g_Regions[i].currentWeather = token;
		else
			RollWeather(g_Regions[i]);
		rolled += " " + g_Regions[i].name + "=" + g_Regions[i].currentWeather;
	}
	Log("MSR: weather%s\n", rolled.c_str());

	for (int i = 1; i <= gpGlobals->maxClients; i++)
	{
		CBasePlayer *pPlayer = (CBasePlayer *)UTIL_PlayerByIndex(i);
		if (!pPlayer || !pPlayer->GetScripted())
			continue;
		const int region = ForEntity(pPlayer);
		msstringlist params;
		params.add(region == REGION_NONE ? token : WeatherFor(region));
		pPlayer->CallScriptEvent(eventName, &params);
	}
	return true;
}

// "msr_regions [monsters]": region table, where each player is, monsters per region.
void ReportCommand()
{
	if (!Active())
	{
		Log("MSR: no region table on this map\n");
		return;
	}
	for (size_t i = 0; i < g_Regions.size(); i++)
	{
		const msr_region_t &r = g_Regions[i];
		Log("region %d %s: %s, %d map entities, %d no-logout boxes, empty for %.0f s | title '%s' diff '%s' warnhp %d sky %s view %.0f weather now '%s' of '%s'\n",
			(int)i, r.name.c_str(), r.loaded ? "loaded" : (g_Load.region == (int)i ? "LOADING" : "UNLOADED"), r.records, (int)(r.noLogout.size() / 6), Occupied((int)i) ? 0.0f : gpGlobals->time - r.lastOccupied,
			r.title.c_str(), r.diff.c_str(), r.warnhp, r.skyname.c_str(), r.maxrange, r.currentWeather.c_str(), r.weather.c_str());
	}
	int used = 0;
	for (int e = 1; e < gpGlobals->maxEntities; e++)
		if (INDEXENT(e))
			used++;
	Log("edicts in use: %d of %d, stores: %d, unload after %.0f s empty\n", used, gpGlobals->maxEntities, (int)CStore::m_gStores.size(),
		g_UnloadTime.value);
	for (int i = 1; i <= gpGlobals->maxClients; i++)
	{
		CBasePlayer *pPlayer = (CBasePlayer *)UTIL_PlayerByIndex(i);
		if (!pPlayer) // connected players only (UTIL_PlayerByIndex)
			continue;
		Log("player %d %s: region %s at (%.0f %.0f %.0f) weather '%s' sky '%s'\n", i, pPlayer->DisplayName(),
			NameOr(pPlayer->m_iRegion, "none"), pPlayer->pev->origin.x, pPlayer->pev->origin.y, pPlayer->pev->origin.z,
			pPlayer->GetScripted() ? pPlayer->GetFirstScriptVar("PLR_WEATHER") : "", pPlayer->m_RegionSky.c_str());
	}
	const bool listAll = CMD_ARGC() > 1 && FStrEq(CMD_ARGV(1), "monsters");
	std::vector<int> perRegion(g_Regions.size() + 1, 0);
	for (int e = 1; e < gpGlobals->maxEntities; e++)
	{
		edict_t *pEdict = INDEXENT(e);
		if (!pEdict || pEdict->free || !pEdict->pvPrivateData)
			continue;
		CBaseEntity *pEntity = CBaseEntity::Instance(pEdict);
		if (!pEntity || !pEntity->IsMSMonster() || pEntity->IsPlayer())
			continue;
		CMSMonster *pMonster = (CMSMonster *)pEntity;
		const int region = ForEntity(pMonster);
		perRegion[region == REGION_NONE ? g_Regions.size() : region]++;
		if (listAll)
			Log("  #%d %s home %s hp %.0f/%.0f at (%.0f %.0f %.0f)\n", e, pMonster->m_ScriptName.c_str(), NameOr(pMonster->m_iHomeRegion, "none"),
				pMonster->pev->health, pMonster->pev->max_health, pMonster->pev->origin.x, pMonster->pev->origin.y, pMonster->pev->origin.z);
	}
	std::string counts;
	for (size_t i = 0; i < g_Regions.size(); i++)
		counts += " " + g_Regions[i].name + "=" + std::to_string(perRegion[i]);
	Log("monsters/NPCs:%s none=%d\n", counts.c_str(), perRegion[g_Regions.size()]);
}


void MapStart()
{
	if (Active())
		Log("MSR: %d regions active on %s\n", Count(), STRING(gpGlobals->mapname));
	MSR_LogMemory(UTIL_VarArgs("%s loaded", STRING(gpGlobals->mapname)));
}

bool Occupied(int region)
{
	if (region == REGION_NONE)
		return true;
	// Players placed by the tracker (connected, loaded and in the world); also where a loaded
	// player stands right now, since the tracker only looks four times a second.
	for (int i = 1; i <= gpGlobals->maxClients; i++)
	{
		CBasePlayer *pPlayer = (CBasePlayer *)UTIL_PlayerByIndex(i);
		if (!IsPresent(pPlayer))
			continue;
		if (pPlayer->m_iRegion == region || At(pPlayer->pev->origin) == region)
			return true;
	}
	return false;
}

bool Tracked(int region)
{
	if (region == REGION_NONE)
		return true;
	// Only players the tracker has placed here: region player counts (UTIL_TotalHP(region) etc.)
	// see exactly these, while Occupied also counts one who arrived since the last check
	for (int i = 1; i <= gpGlobals->maxClients; i++)
	{
		CBasePlayer *pPlayer = (CBasePlayer *)UTIL_PlayerByIndex(i);
		if (IsPresent(pPlayer) && pPlayer->m_iRegion == region)
			return true;
	}
	return false;
}

void MarkOccupied(int region)
{
	// A rejoining player counts from now on, like a traveller in PrepareArrival: the tracker
	// only places them once they are in the world, and Frame must not unload the region first.
	if (region >= 0 && region < (int)g_Regions.size())
		g_Regions[region].lastOccupied = gpGlobals->time;
}

bool NoLogout(const float *point)
{
	const msr_region_t *r = Get(At(point));
	if (!r)
		return false;
	for (size_t b = 0; b + 6 <= r->noLogout.size(); b += 6)
	{
		const float *box = &r->noLogout[b];
		if (point[0] >= box[0] && point[1] >= box[1] && point[2] >= box[2] && point[0] <= box[3] && point[1] <= box[4] && point[2] <= box[5])
			return true;
	}
	return false;
}

CBasePlayer *PlayerMaster(CMSMonster *pMonster)
{
	if (!pMonster || pMonster->IsPlayer())
		return NULL;
	if (gpGlobals->time >= pMonster->m_flRegionMasterCheck || pMonster->m_flRegionMasterCheck < 0)
	{
		// Pets are stored as ENT_OWNER; summons and hirelings keep their master in script
		// variables or as the creating/experience owner (a player or a player's item).
		pMonster->m_flRegionMasterCheck = gpGlobals->time + 2.0f;
		CBaseEntity *pFound = pMonster->RetrieveEntity(ENT_OWNER);
		if (!pFound || !pFound->IsPlayer())
			pFound = pMonster->RetrieveEntity(ENT_EXPOWNER);
		if (!pFound || !pFound->IsPlayer())
		{
			pFound = pMonster->RetrieveEntity(ENT_CREATIONOWNER);
			if (pFound && pFound->IsMSItem())
				pFound = ((CGenericItem *)pFound)->Owner();
		}
		if ((!pFound || !pFound->IsPlayer()) && pMonster->GetScripted())
			for (const char *var : {"SUMMON_MASTER", "MY_OWNER"})
			{
				// a disbanded hireling keeps SUMMON_MASTER but sets IS_HIRED back to 0
				if (FStrEq(var, "SUMMON_MASTER") && FStrEq(pMonster->GetFirstScriptVar("IS_HIRED"), "0"))
				{
					pFound = NULL;
					continue;
				}
				pFound = StringToEnt(pMonster->GetFirstScriptVar(var));
				if (pFound && pFound->IsPlayer())
					break;
			}
		pMonster->m_iRegionMaster = (pFound && pFound->IsPlayer() && pFound != pMonster) ? pFound->entindex() : 0;
	}
	if (pMonster->m_iRegionMaster <= 0)
		return NULL;
	CBasePlayer *pPlayer = (CBasePlayer *)UTIL_PlayerByIndex(pMonster->m_iRegionMaster);
	return pPlayer; // NULL once the player left (UTIL_PlayerByIndex returns connected players only)
}

// ---------------------------------------------------------------------------
// Recording map entities as the engine spawns them at load

bool RecordKeyValue(edict_t *pent, KeyValueData *pkvd)
{
	const char *key = pkvd->szKeyName ? pkvd->szKeyName : "";
	const bool tag = FStrEq(key, "msr_region") || FStrEq(key, "msr_keep");
	if (g_Recording && Active())
	{
		// The engine sends "classname" first, before the entity's object exists.
		if (!pkvd->szClassName && FStrEq(key, "classname"))
		{
			g_PendingEdict = pent;
			g_Pending = record_t();
			g_Pending.classname = pkvd->szValue ? pkvd->szValue : "";
			return false;
		}
		if (pent == g_PendingEdict)
		{
			if (FStrEq(key, "msr_region"))
				g_Pending.region = Find(pkvd->szValue);
			else if (FStrEq(key, "msr_keep"))
				g_Pending.keep = atoi(pkvd->szValue) != 0;
			else
				g_Pending.pairs.emplace_back(key, pkvd->szValue ? pkvd->szValue : "");
		}
	}
	if (tag) // builder bookkeeping, never an entity setting
	{
		pkvd->fHandled = TRUE;
		return true;
	}
	return false;
}

void RecordSpawn(edict_t *pent, int spawnResult)
{
	if (!g_Recording || !pent || pent != g_PendingEdict)
		return;
	g_PendingEdict = nullptr;
	record_t rec = std::move(g_Pending);
	g_Pending = record_t();
	// Entities that removed themselves (unnamed lights, info_null...) have nothing to re-create.
	if (spawnResult == -1 || pent->free || !pent->pvPrivateData || (pent->v.flags & FL_KILLME))
		return;
	if (ClassIn(rec.classname.c_str(), kKeepClasses, sizeof(kKeepClasses) / sizeof(kKeepClasses[0])))
		rec.keep = true;
	rec.live = pent;
	rec.liveSerial = pent->serialnumber;
	g_Records.push_back(std::move(rec));
}

void EndLoad()
{
	g_Recording = false;
	g_PendingEdict = nullptr;
	if (!Active())
	{
		g_Records.clear();
		return;
	}
	for (record_t &rec : g_Records)
	{
		// Maps without builder tags: fall back to where the entity is now.
		if (rec.region == REGION_NONE && !rec.keep && LiveValid(rec))
			rec.region = ForEntity(CBaseEntity::Instance(rec.live));
		if (rec.region == REGION_NONE)
			rec.keep = true; // nowhere in particular: never unloaded
		else if (!rec.keep)
			g_Regions[rec.region].records++;
	}
	std::string counts;
	for (msr_region_t &r : g_Regions)
	{
		r.loaded = true;
		r.lastOccupied = r.lastChange = gpGlobals->time;
		counts += " " + r.name + "=" + std::to_string(r.records);
	}
	Log("MSR: recorded %d map entities; re-creatable per region:%s\n", (int)g_Records.size(), counts.c_str());

	// The walk-through links, so a region can start loading while a player heads for it
	g_Links.clear();
	for (const record_t &rec : g_Records)
	{
		if (!rec.keep || rec.classname != "trigger_teleport" || !LiveValid(rec))
			continue;
		const char *target = nullptr;
		for (const auto &kv : rec.pairs)
			if (kv.first == "target")
				target = kv.second.c_str();
		if (!target || !*target)
			continue;
		CBaseEntity *pDest = NULL;
		while ((pDest = UTIL_FindEntityByTargetname(pDest, target)) != NULL)
			if (FClassnameIs(pDest->pev, "info_teleport_destination"))
				break;
		const int to = pDest ? At(pDest->pev->origin) : REGION_NONE;
		if (to != REGION_NONE && to != rec.region)
			g_Links.push_back({rec.live, rec.liveSerial, to});
	}
	Log("MSR: %d walk-through links between regions\n", (int)g_Links.size());
}

bool IsLoaded(int region)
{
	const msr_region_t *r = Get(region);
	return !r || r->loaded;
}

bool Replaying() { return g_Replaying; }

bool TakeSpawnSlot()
{
	static float lastSlotTime = -1;
	if (gpGlobals->time == lastSlotTime) // one per server frame (time is unique per frame)
		return false;
	lastSlotTime = gpGlobals->time;
	return true;
}

// ---------------------------------------------------------------------------
// Unloading a region nobody is in

namespace
{
bool IsClientEntity(int index)
{
	for (int i = 0; i < CLPERMENT_TOTAL; i++)
		if (MSGlobals::ClEntities[i] == index)
			return true;
	return false;
}

void RemoveEdict(edict_t *pent)
{
	if (!pent || pent->free || !pent->pvPrivateData)
		return;
	CBaseEntity *pEntity = CBaseEntity::Instance(pent);
	if (pEntity)
	{
		// Looping ambient sounds live on in clients unless stopped explicitly
		if (FClassnameIs(pent, "ambient_generic") && pEntity->pev->message)
			UTIL_EmitAmbientSound(pent, pEntity->pev->origin, STRING(pEntity->pev->message), 0, 0, SND_STOP, 0);
		pEntity->UpdateOnRemove(); // node graph links
		pEntity->Deactivate();	   // scripts, stats (no death events, like a map change)
	}
	REMOVE_ENTITY(pent);
}

bool Unload(int region, const char *why)
{
	msr_region_t &R = g_Regions[region];
	if (!R.loaded || Occupied(region))
		return false;
	const auto started = std::chrono::steady_clock::now();

	std::unordered_set<edict_t *> recordEdicts;
	for (const record_t &rec : g_Records)
		if (rec.region == region && !rec.keep && LiveValid(rec))
			recordEdicts.insert(rec.live);

	// Collect: the region's map entities, its runtime monsters and loose items, and the
	// helpers they left behind. Never players, their gear, pets, summons or hirelings.
	std::vector<edict_t *> monsters, items, others;
	for (int e = gpGlobals->maxClients + 1; e < gpGlobals->maxEntities; e++)
	{
		edict_t *pent = INDEXENT(e);
		if (!pent || pent->free || !pent->pvPrivateData || IsClientEntity(e))
			continue;
		CBaseEntity *pEntity = CBaseEntity::Instance(pent);
		if (!pEntity || pEntity->IsPlayer() || IsGameMaster(pEntity))
			continue;
		const bool isRecord = recordEdicts.count(pent) > 0;
		if (pEntity->IsMSItem())
		{
			CGenericItem *pItem = (CGenericItem *)pEntity;
			if (pItem->Owner()) // carried: goes with its monster, stays with its player
				continue;
			CGenericItem *pOuter = pItem;
			while (pOuter->m_pParentContainer)
				pOuter = pOuter->m_pParentContainer;
			if (isRecord || At(pOuter->pev->origin) == region)
				items.push_back(pent);
			continue;
		}
		if (pEntity->IsMSMonster())
		{
			CMSMonster *pMonster = (CMSMonster *)pEntity;
			if (PlayerMaster(pMonster))
				continue; // with a connected player, wherever they are
			if (!isRecord && pMonster->m_iHomeRegion == region)
			{
				// moved by a script into another region (e.g. Galat's chest): it lives there now
				const int here = At(pMonster->pev->origin);
				if (here != REGION_NONE && here != region)
				{
					pMonster->m_iHomeRegion = here;
					continue;
				}
			}
			if (isRecord || pMonster->m_iHomeRegion == region)
				monsters.push_back(pent);
			continue;
		}
		if (isRecord || (ClassIn(STRING(pent->v.classname), kTransientClasses, sizeof(kTransientClasses) / sizeof(kTransientClasses[0])) &&
							At(pent->v.origin) == region))
			others.push_back(pent);
	}

	std::unordered_set<edict_t *> removed;
	for (auto *list : {&monsters, &items, &others})
		removed.insert(list->begin(), list->end());
	std::vector<std::pair<int, int>> removedIds; // for stores: index + serial
	for (edict_t *pent : removed)
		removedIds.push_back({ENTINDEX(pent), pent->serialnumber});

	// Monsters' gear first (items unhook from their owner), then loose items, then the rest.
	int gear = 0;
	for (edict_t *pent : monsters)
	{
		if (pent->free || !pent->pvPrivateData)
			continue;
		CMSMonster *pMonster = (CMSMonster *)CBaseEntity::Instance(pent);
		std::vector<CGenericItem *> carried;
		for (unsigned int i = 0; i < pMonster->Gear.size(); i++)
			carried.push_back(pMonster->Gear[i]);
		for (CGenericItem *pItem : carried)
			if (pItem && pItem->edict() && !pItem->edict()->free)
			{
				removed.insert(pItem->edict());
				pItem->SUB_Remove();
				gear++;
			}
	}
	for (edict_t *pent : items)
		if (!pent->free && pent->pvPrivateData)
			((CGenericItem *)CBaseEntity::Instance(pent))->SUB_Remove();
	for (edict_t *pent : monsters)
		RemoveEdict(pent);
	for (edict_t *pent : others)
		RemoveEdict(pent);

	// Vendor and chest stores only this region's entities were using
	int stores = 0;
	std::vector<CStore *> allStores;
	for (unsigned int i = 0; i < CStore::m_gStores.size(); i++)
		allStores.push_back(CStore::m_gStores[i]);
	for (CStore *pStore : allStores)
	{
		if (pStore->m_Creators.empty())
			continue;
		std::vector<CStore::creator_t> alive;
		for (const CStore::creator_t &c : pStore->m_Creators)
		{
			bool gone = false;
			for (const auto &id : removedIds)
				if (id.first == c.index && id.second == c.serial)
					gone = true;
			edict_t *pCreator = INDEXENT(c.index);
			if (!gone && pCreator && !pCreator->free && pCreator->serialnumber == c.serial)
				alive.push_back(c);
		}
		pStore->m_Creators = alive;
		if (alive.empty())
		{
			pStore->Deactivate();
			stores++;
		}
	}

	// Nothing left may point at what was removed
	for (int e = 1; e < gpGlobals->maxEntities; e++)
	{
		edict_t *pent = INDEXENT(e);
		if (!pent || pent->free)
			continue;
		if (pent->v.owner && removed.count(pent->v.owner))
			pent->v.owner = NULL;
		if (pent->v.aiment && removed.count(pent->v.aiment))
			pent->v.aiment = NULL;
		if (pent->v.enemy && removed.count(pent->v.enemy))
			pent->v.enemy = NULL;
	}

	R.loaded = false;
	R.lastChange = gpGlobals->time;
	const long ms = (long)std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - started).count();
	Log("MSR: region %s unloaded (%s): %d monsters, %d items, %d carried items, %d other entities, %d stores removed in %ld ms\n",
		R.name.c_str(), why, (int)monsters.size(), (int)items.size(), gear, (int)others.size(), stores, ms);
	return true;
}
} // namespace

// ---------------------------------------------------------------------------
// Re-creating a region from its records. NPC scripts take 10-30 ms each to parse, so a
// region loading ahead of a player (one walking toward a way in) takes ms_region_load_budget
// ms per server frame; a player arriving, respawning or joining inside finishes it at once.
// What a load creates holds still (no thinking) until the whole region exists, and then
// everything is activated together, as after a map load.

namespace
{
double MsSince(std::chrono::steady_clock::time_point t)
{
	return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t).count();
}

void AddClassTime(load_t &L, const std::string &cls, double ms)
{
	for (auto &ct : L.classTime)
		if (ct.first == cls)
		{
			ct.second += ms;
			return;
		}
	L.classTime.push_back({cls, ms});
}

bool BeginLoad(int region, const char *why)
{
	msr_region_t &R = g_Regions[region];
	if (R.loaded || g_Load.region == region)
		return true;
	if (g_Load.region != REGION_NONE)
		return false; // one at a time

	// Running out of edicts stops the whole server, so check first (room for its monsters too).
	// Count slots the way the engine allocates: past the client slots, and not freed in the
	// last half second (a freetime ahead of now is left from the previous map).
	if (gpGlobals->time < R.nextLoadAttempt)
		return false;
	int freeSlots = 0;
	edict_t *pEdicts = INDEXENT(0); // the edict array is contiguous
	for (int e = gpGlobals->maxClients + 1; e < gpGlobals->maxEntities; e++)
	{
		const edict_t *p = pEdicts + e;
		const bool recentlyFreed = p->freetime >= 2.0f && p->freetime <= gpGlobals->time && gpGlobals->time - p->freetime <= 0.5f;
		if (p->free && !recentlyFreed)
			freeSlots++;
	}
	if (freeSlots < R.records + 256)
	{
		R.nextLoadAttempt = gpGlobals->time + 5.0f; // retry later instead of on every region check
		Log("MSR: region %s NOT loaded (%s): %d free edicts, needs %d\n", R.name.c_str(), why, freeSlots, R.records + 256);
		return false;
	}

	g_Load = load_t();
	g_Load.region = region;
	g_Load.why = why;
	g_Load.startedAt = gpGlobals->time;
	return true;
}

void CreateOne(load_t &L, record_t &rec)
{
	const auto started = std::chrono::steady_clock::now();
	const int filesBefore = g_MSRScriptFiles;
	const double scriptBefore = g_MSRScriptTopMs, parseBefore = g_MSRScriptParseMs;
	struct Profile
	{
		load_t &L;
		const record_t &rec;
		std::chrono::steady_clock::time_point started;
		int filesBefore;
		double scriptBefore, parseBefore;
		~Profile()
		{
			const double ms = MsSince(started);
			AddClassTime(L, rec.classname, ms);
			L.scriptFiles += g_MSRScriptFiles - filesBefore;
			L.scriptMs += g_MSRScriptTopMs - scriptBefore;
			L.parseMs += g_MSRScriptParseMs - parseBefore;
			if (ms >= 10.0)
			{
				std::string what = rec.classname;
				for (const auto &kv : rec.pairs)
					if (kv.first == "scriptfile" || kv.first == "targetname")
						what += ":" + kv.second;
				L.slowest.push_back({ms, what});
			}
		}
	} profile{L, rec, started, filesBefore, scriptBefore, parseBefore};

	// Remember which edicts are in use, to hold whatever this entity's spawning creates too
	edict_t *pEdicts = INDEXENT(0); // the edict array is contiguous
	L.serials.resize(gpGlobals->maxEntities);
	for (int e = 0; e < gpGlobals->maxEntities; e++)
		L.serials[e] = pEdicts[e].free ? -1 : pEdicts[e].serialnumber;

	edict_t *pent = CREATE_NAMED_ENTITY(ALLOC_STRING(rec.classname.c_str()));
	if (FNullEnt(pent) || !pent->pvPrivateData)
	{
		L.failed++;
		return;
	}
	g_Replaying = true;
	// Same calls the engine makes at load: key/values in order, then Spawn
	for (const auto &kv : rec.pairs)
	{
		std::vector<char> key(kv.first.begin(), kv.first.end()), value(kv.second.begin(), kv.second.end());
		key.push_back(0);
		value.push_back(0);
		KeyValueData kvd;
		kvd.szClassName = (char *)rec.classname.c_str();
		kvd.szKeyName = key.data();
		kvd.szValue = value.data();
		kvd.fHandled = FALSE;
		DispatchKeyValue(pent, &kvd);
	}
	const int spawnResult = DispatchSpawn(pent);
	g_Replaying = false;
	const bool spawned = spawnResult != -1 && !pent->free && pent->pvPrivateData;
	if (spawnResult == -1 && !pent->free && !(pent->v.flags & FL_KILLME))
		REMOVE_ENTITY(pent);
	if (spawned)
	{
		rec.live = pent;
		rec.liveSerial = pent->serialnumber;
		L.created.push_back({pent, pent->serialnumber, pent->v.nextthink, gpGlobals->time});
	}
	for (int e = gpGlobals->maxClients + 1; e < gpGlobals->maxEntities; e++)
	{
		edict_t *p = pEdicts + e;
		if (p != pent && !p->free && p->pvPrivateData && L.serials[e] != p->serialnumber)
			L.extra.push_back({p, p->serialnumber, p->v.nextthink, gpGlobals->time});
	}
	// Hold everything still until the whole region exists. That includes anything an entity's
	// spawn set thinking again (a Use); it keeps its latest think.
	for (std::vector<held_t> *list : {&L.created, &L.extra})
		for (held_t &h : *list)
			if (!h.pent->free && h.pent->serialnumber == h.serial && h.pent->v.nextthink != 0)
			{
				h.nextthink = h.pent->v.nextthink;
				h.createdAt = gpGlobals->time;
				h.pent->v.nextthink = 0;
			}
}

bool HeldValid(const held_t &h)
{
	return !h.pent->free && h.pent->pvPrivateData && h.pent->serialnumber == h.serial;
}

// Let a held entity think again as if it had spawned now (a pusher thinks on its own clock)
void Release(const held_t &h)
{
	if (HeldValid(h) && h.pent->v.nextthink == 0 && h.nextthink > 0)
		h.pent->v.nextthink = h.pent->v.movetype == MOVETYPE_PUSH ? h.nextthink : h.nextthink + (gpGlobals->time - h.createdAt);
}

// The world's game master took in each region's game_master at map start (script.cpp) and ran
// its game_spawn then. A re-created region runs its own again, as a fresh map would (Helena
// swaps in Old Helena's axe once someone has taken it). The script is loaded for this alone,
// so events it would call later are lost; no region's game_master schedules any.
void RerunGameMaster(const msr_region_t &R)
{
	// (dev mode loads no region game_master at map start either, see script.cpp)
	if (!g_pGameMasterEntity || !stricmp(R.name.c_str(), STRING(gpGlobals->mapname)) || MSGlobals::DevModeEnabled)
		return;
	IScripted *pScripted = g_pGameMasterEntity->GetScripted();
	if (!pScripted)
		return;
	CScript *pScript = msnew CScript;
	if (pScript->Spawn(msstring(R.name.c_str()) + "/game_master", g_pGameMasterEntity, pScripted, false, true))
	{
		pScript->RunScriptEventByName("game_spawn");
		Log("MSR: region %s ran its game_master game_spawn again\n", R.name.c_str());
	}
	delete pScript;
}

void FinishLoad(const char *finishedBy)
{
	// Off the books first: activating what was made may start another load
	load_t L = std::move(g_Load);
	g_Load = load_t();
	msr_region_t &R = g_Regions[L.region];
	const auto started = std::chrono::steady_clock::now();

	// Let everything think again as if it had all spawned now, then Activate the map entities
	// together, as after map load (templates join their spawners here)
	for (const held_t &h : L.created)
		Release(h);
	for (const held_t &h : L.extra)
		Release(h);
	for (const held_t &h : L.created)
		if (HeldValid(h) && !(h.pent->v.flags & (FL_DORMANT | FL_KILLME)))
			if (CBaseEntity *pEntity = CBaseEntity::Instance(h.pent))
				pEntity->Activate();
	for (const held_t &h : L.created)
		if (HeldValid(h))
			MSR_QuickStartSpawner(CBaseEntity::Instance(h.pent));
	R.loaded = true;
	R.lastOccupied = R.lastChange = gpGlobals->time;
	R.aheadUnentered = L.ahead && !finishedBy; // loaded ahead and nobody has arrived: a short stay if nobody comes
	RerunGameMaster(R);
	const double finishMs = MsSince(started);
	AddClassTime(L, "(activate)", finishMs);
	L.workMs += finishMs;

	std::sort(L.classTime.begin(), L.classTime.end(), [](const auto &a, const auto &b) { return a.second > b.second; });
	std::string top;
	for (size_t i = 0; i < L.classTime.size() && i < 8; i++)
		top += UTIL_VarArgs(" %s=%.0f", L.classTime[i].first.c_str(), L.classTime[i].second);
	Log("MSR: region %s load time by class (ms):%s\n", R.name.c_str(), top.c_str());
	if (!L.slowest.empty())
	{
		std::sort(L.slowest.begin(), L.slowest.end(), [](const auto &a, const auto &b) { return a.first > b.first; });
		top.clear();
		for (size_t i = 0; i < L.slowest.size() && i < 6; i++)
			top += UTIL_VarArgs(" %s=%.0f", L.slowest[i].second.c_str(), L.slowest[i].first);
		Log("MSR: region %s slowest entities (ms, %d over 10):%s\n", R.name.c_str(), (int)L.slowest.size(), top.c_str());
	}
	Log("MSR: region %s loaded (%s%s%s): %d entities re-created%s, %.0f ms of work (scripts %d files %.0f ms, parsing %.0f) "
		"over %d frames in %.1f s, longest frame %.0f ms\n",
		R.name.c_str(), L.why.c_str(), finishedBy ? ", finished for " : "", finishedBy ? finishedBy : "", (int)L.created.size(),
		L.failed ? UTIL_VarArgs(", %d failed", L.failed) : "", L.workMs, L.scriptFiles, L.scriptMs, L.parseMs, L.frames,
		gpGlobals->time - L.startedAt, L.maxStepMs);
}

// Continue the current load for about budgetMs (at least one entity), or to the end if negative.
void StepLoad(double budgetMs, const char *finishedBy)
{
	load_t &L = g_Load;
	if (L.region == REGION_NONE || L.stepping)
		return;
	const auto started = std::chrono::steady_clock::now();
	L.frames++;
	L.stepping = true;
	while (L.cursor < g_Records.size())
	{
		record_t &rec = g_Records[L.cursor++];
		if (rec.region != L.region || rec.keep || LiveValid(rec)) // a kept hireling is still its record's instance
			continue;
		CreateOne(L, rec);
		if (budgetMs >= 0 && MsSince(started) >= budgetMs)
			break;
	}
	L.stepping = false;
	const double ms = MsSince(started);
	L.workMs += ms;
	if (ms > L.maxStepMs)
		L.maxStepMs = ms;
	if (L.cursor >= g_Records.size())
		FinishLoad(finishedBy);
}

float DistanceToBox(const float *p, const float *mins, const float *maxs)
{
	float sq = 0;
	for (int a = 0; a < 3; a++)
	{
		const float d = p[a] < mins[a] ? mins[a] - p[a] : (p[a] > maxs[a] ? p[a] - maxs[a] : 0);
		sq += d * d;
	}
	return sqrtf(sq);
}

// A player near a way into a region keeps it loaded, or starts loading it
void Preload()
{
	if (g_PreloadRange.value <= 0)
		return;
	for (int i = 1; i <= gpGlobals->maxClients; i++)
	{
		CBasePlayer *pPlayer = (CBasePlayer *)UTIL_PlayerByIndex(i);
		if (!IsPresent(pPlayer))
			continue;
		for (const region_link_t &link : g_Links)
		{
			if (link.pent->free || link.pent->serialnumber != link.serial ||
				DistanceToBox(pPlayer->pev->origin, link.pent->v.absmin, link.pent->v.absmax) > g_PreloadRange.value)
				continue;
			msr_region_t &R = g_Regions[link.toRegion];
			R.lastOccupied = gpGlobals->time;
			if (!R.loaded && g_Load.region == REGION_NONE && BeginLoad(link.toRegion, UTIL_VarArgs("%s approaching", pPlayer->DisplayName())))
			{
				g_Load.ahead = true;
				Log("MSR: region %s loading ahead of %s\n", R.name.c_str(), pPlayer->DisplayName());
			}
		}
	}
}

// Give up a load under way ahead of a player, so that a region someone needs now loads
// without waiting for it. What it made so far is held still, so this is an ordinary unload.
bool CancelLoad(const char *why)
{
	const int region = g_Load.region;
	if (region == REGION_NONE || g_Load.stepping || Occupied(region))
		return false; // someone is in it already: it has to finish
	std::vector<held_t> extra = std::move(g_Load.extra);
	const int made = (int)g_Load.created.size();
	g_Load = load_t();
	g_Regions[region].loaded = true; // Unload only takes loaded regions
	if (!Unload(region, why))
	{
		g_Regions[region].loaded = false;
		return false;
	}
	for (const held_t &h : extra) // leftovers Unload has no reason to pick up (e.g. delayed triggers)
		if (HeldValid(h))
			RemoveEdict(h.pent);
	Log("MSR: region %s load cancelled after %d entities (%s)\n", g_Regions[region].name.c_str(), made, why);
	return true;
}
} // namespace

bool EnsureLoaded(int region, const char *why)
{
	if (region < 0 || region >= (int)g_Regions.size() || g_Regions[region].loaded)
		return true;
	if (g_Load.stepping)
		return false; // an entity being re-created right now asked for another region
	if (g_Load.region != REGION_NONE && g_Load.region != region && !CancelLoad(UTIL_VarArgs("%s needed now", g_Regions[region].name.c_str())))
		StepLoad(-1, why); // finish the other region's load first
	if (g_Load.region != region && !BeginLoad(region, why))
		return false;
	StepLoad(-1, g_Load.why == why ? nullptr : why);
	return g_Regions[region].loaded;
}

bool PrepareArrival(const char *teleportTarget)
{
	if (!Active() || !teleportTarget || !*teleportTarget)
		return true;
	// The teleport picks one of the destinations with this name: have all their regions ready
	bool ready = true;
	CBaseEntity *pDest = NULL;
	while ((pDest = UTIL_FindEntityByClassname(pDest, "info_teleport_destination")) != NULL)
		if (FStrEq(STRING(pDest->pev->targetname), teleportTarget))
		{
			const int region = At(pDest->pev->origin);
			if (region == REGION_NONE)
				continue;
			// the traveller counts as there from now on, before the tracker notices
			g_Regions[region].lastOccupied = gpGlobals->time;
			if (!IsLoaded(region) && !EnsureLoaded(region, "player on the way"))
				ready = false;
		}
	return ready;
}

void Frame()
{
	if (g_MemLogMinutes.value > 0 && (gpGlobals->time >= g_NextMemLog || gpGlobals->time < g_NextMemLog - g_MemLogMinutes.value * 60))
	{
		if (g_NextMemLog > 0)
			MSR_LogMemory("uptime check");
		g_NextMemLog = gpGlobals->time + g_MemLogMinutes.value * 60;
	}
	if (!Active() || g_Recording)
		return;
	// Diagnostics: report server frames that stalled (e.g. many monster scripts loading at once)
	static std::chrono::steady_clock::time_point lastFrame;
	const auto now = std::chrono::steady_clock::now();
	const long frameMs = (long)std::chrono::duration_cast<std::chrono::milliseconds>(now - lastFrame).count();
	if (lastFrame.time_since_epoch().count() && frameMs > 200)
		Log("MSR: slow server frame: %ld ms\n", frameMs);
	lastFrame = now;
	if (g_Load.region != REGION_NONE)
		StepLoad(g_LoadBudget.value > 0 ? g_LoadBudget.value : 10.0, nullptr);
	if (gpGlobals->time < g_NextLifecycleCheck)
		return;
	g_NextLifecycleCheck = gpGlobals->time + 1.0f;
	Preload();
	const int home = Find(STRING(gpGlobals->mapname)); // the start region (spawns, raid, tavern) stays loaded
	for (size_t i = 0; i < g_Regions.size(); i++)
	{
		msr_region_t &r = g_Regions[i];
		if (Occupied((int)i))
		{
			r.lastOccupied = gpGlobals->time;
			r.aheadUnentered = false;
		}
		// loaded ahead of a player who then went elsewhere: a minute is enough
		const float emptyFor = r.aheadUnentered ? std::min(g_UnloadTime.value, 60.0f) : g_UnloadTime.value;
		if (g_UnloadTime.value > 0 && (int)i != home && r.loaded && r.records > 0 &&
			gpGlobals->time - r.lastOccupied >= emptyFor && gpGlobals->time - r.lastChange >= 5.0f)
			Unload((int)i, r.aheadUnentered ? "loaded ahead, nobody came" : "nobody there");
	}
}

// "msr_region_unload <name>" / "msr_region_load <name>": for testing and admins
void UnloadCommand()
{
	const int region = CMD_ARGC() > 1 ? Find(CMD_ARGV(1)) : REGION_NONE;
	if (region == REGION_NONE)
		Log("usage: msr_region_unload <region>\n");
	else if (region == Find(STRING(gpGlobals->mapname)))
		Log("MSR: %s is the start region and stays loaded\n", CMD_ARGV(1));
	else if (!Unload(region, "command"))
		Log("MSR: %s not unloaded (already unloaded, or a player is there)\n", CMD_ARGV(1));
}

void LoadCommand()
{
	const int region = CMD_ARGC() > 1 ? Find(CMD_ARGV(1)) : REGION_NONE;
	if (region == REGION_NONE)
		Log("usage: msr_region_load <region> [ahead]\n");
	else if (IsLoaded(region))
		Log("MSR: %s is already loaded\n", CMD_ARGV(1));
	else if (CMD_ARGC() > 2 && FStrEq(CMD_ARGV(2), "ahead")) // over several frames, as for an approaching player
	{
		if (BeginLoad(region, "command, ahead"))
			g_Load.ahead = true;
		else
			Log("MSR: %s not started (another region is loading, or no free edicts)\n", CMD_ARGV(1));
	}
	else
		EnsureLoaded(region, "command");
}

// "msr_weather <token> [region]": change the weather now, everywhere or in one region (testing and
// admins; also on maps without regions). The game master's next roll replaces it as usual.
void WeatherCommand()
{
	if (CMD_ARGC() < 2)
	{
		Log("usage: msr_weather <clear|rain|storm|snow|fog_white|...> [region]\n");
		return;
	}
	const std::string token = CMD_ARGV(1);
	const int only = CMD_ARGC() > 2 ? Find(CMD_ARGV(2)) : REGION_NONE;
	if (CMD_ARGC() > 2 && only == REGION_NONE)
	{
		Log("MSR: no region %s\n", CMD_ARGV(2));
		return;
	}
	for (size_t i = 0; i < g_Regions.size(); i++)
		if (only == REGION_NONE || (int)i == only)
			g_Regions[i].currentWeather = token;
	int told = 0;
	for (int i = 1; i <= gpGlobals->maxClients; i++)
	{
		CBasePlayer *pPlayer = (CBasePlayer *)UTIL_PlayerByIndex(i);
		if (!pPlayer || !pPlayer->GetScripted())
			continue;
		if (only != REGION_NONE && ForEntity(pPlayer) != only)
			continue;
		msstringlist params;
		params.add(token.c_str());
		pPlayer->CallScriptEvent("ext_weather_change", &params);
		told++;
	}
	Log("MSR: weather set to %s in %s (%d players)\n", token.c_str(), only == REGION_NONE ? "all regions" : g_Regions[only].name.c_str(), told);
}

void Init()
{
	g_engfuncs.pfnAddServerCommand((char *)"msr_weather", WeatherCommand);
	CVAR_REGISTER(&g_UnloadTime);
	CVAR_REGISTER(&g_LoadBudget);
	CVAR_REGISTER(&g_PreloadRange);
	CVAR_REGISTER(&g_MemLogMinutes);
	g_engfuncs.pfnAddServerCommand((char *)"msr_mem", [] { MSR_LogMemory("msr_mem"); });
	g_engfuncs.pfnAddServerCommand((char *)"msr_regions", ReportCommand);
	g_engfuncs.pfnAddServerCommand((char *)"msr_region_unload", UnloadCommand);
	g_engfuncs.pfnAddServerCommand((char *)"msr_region_load", LoadCommand);
}
} // namespace MSRegions

// ---------------------------------------------------------------------------
// Player region tracking: runs from UpdateClientData every frame, checks the
// region four times a second and plays the region intro on its own timer.

void CBasePlayer::UpdateRegion()
{
	if (!MSRegions::Active() || m_CharacterState != CHARSTATE_LOADED)
		return;
	IScripted *pScripted = GetScripted();
	if (!pScripted || atoi(pScripted->GetFirstScriptVar("PLR_IN_WORLD")) != 1)
		return;

	if (gpGlobals->time >= m_flNextRegionCheck)
	{
		m_flNextRegionCheck = gpGlobals->time + 0.25f;
		const int region = MSRegions::At(pev->origin);
		if (region != REGION_NONE && !MSRegions::IsLoaded(region)) // rejoined or respawned into an unloaded region
			MSRegions::EnsureLoaded(region, "player inside");
		if (region != REGION_NONE && (region != m_iRegion || m_fRegionResync))
			OnRegionChange(m_iRegion, region);
		UpdateLogoutSpot(); // last spot a rejoin may put the player back on (player.cpp)
	}

	if (m_flRegionMusicStopAt && gpGlobals->time >= m_flRegionMusicStopAt)
	{
		m_flRegionMusicStopAt = 0;
		if (m_iMusicArea == -100 - m_iRegion) // no music area of this region touched since
			SwapMusic(-200 - m_iRegion, MUSIC_STOP, "");
	}

	if (m_iRegionIntroStage && gpGlobals->time >= m_flRegionIntroTime)
		RunRegionIntro();
}

void CBasePlayer::OnRegionChange(int oldRegion, int newRegion)
{
	const msr_region_t *r = MSRegions::Get(newRegion);
	if (!r)
		return;
	const bool moved = newRegion != oldRegion;
	const bool firstPlacement = oldRegion == REGION_NONE;
	m_iRegion = newRegion;
	m_fRegionResync = false;
	SetScriptVar("PLR_REGION", r->name.c_str());

	// The old map's area music would keep playing; a real map change stops it. Forget the
	// current music area so the arrival area's trigger re-sends its track (the client keeps
	// playing an identical track), and stop the music only if no area claims the player.
	if (moved && !firstPlacement)
	{
		m_iMusicArea = -100 - newRegion;
		m_flRegionMusicStopAt = gpGlobals->time + 0.5f;
	}

	// Sky: the engine keeps one sky per server, but each client can switch its own.
	std::string sky = r->skyname.empty() ? std::string(CVAR_GET_STRING("sv_skyname")) : r->skyname;
	const std::string sentSky = m_RegionSky.len() ? std::string(m_RegionSky.c_str()) : std::string(CVAR_GET_STRING("sv_skyname"));
	if (!sky.empty() && stricmp(sky.c_str(), sentSky.c_str()))
		CLIENT_COMMAND(edict(), "skyname %s\n", sky.c_str());
	m_RegionSky = sky.c_str();

	// View distance, as game_player_putinworld does with the map-wide value.
	msstringlist viewParams;
	viewParams.add(UTIL_VarArgs("%i", r->maxrange > 512 ? (int)r->maxrange : 16384));
	CallScriptEvent("ext_viewdist", &viewParams);

	// Weather of the region's own cycle (also fixes joiners waiting for the next roll).
	std::string weather = MSRegions::WeatherFor(newRegion);
	std::string shown = weather == "storm" ? std::string("rain_storm") : weather;
	if (shown != GetFirstScriptVar("PLR_WEATHER"))
	{
		msstringlist weatherParams;
		weatherParams.add(weather.c_str());
		CallScriptEvent("ext_weather_change", &weatherParams);
	}

	Log("MSR: %s region %s -> %s (sky %s, weather %s, view %s)\n", DisplayName(), MSRegions::NameOr(oldRegion, "none"),
		r->name.c_str(), sky.c_str(), weather.c_str(), viewParams[0].c_str());

	if (moved)
	{
		m_iRegionIntroFor = newRegion;
		m_iRegionIntroStage = 1;
		m_flRegionIntroTime = gpGlobals->time + (firstPlacement ? 10.0f : 1.5f);

		msstringlist changeParams;
		changeParams.add(r->name.c_str());
		changeParams.add(MSRegions::NameOr(oldRegion, "none"));
		CallScriptEvent("game_region_change", &changeParams);
	}
}

void CBasePlayer::RunRegionIntro()
{
	const msr_region_t *r = MSRegions::Get(m_iRegionIntroFor);
	if (!r || m_iRegion != m_iRegionIntroFor)
	{
		m_iRegionIntroStage = 0; // left before the intro played
		return;
	}
	if (m_iRegionIntroStage == 1)
	{
		if (!r->title.empty())
		{
			SendHUDMsg(r->title.c_str(), r->desc.c_str());
			Log("MSR: %s intro '%s'\n", DisplayName(), r->title.c_str());
		}
		if (!m_fRegionGaveFirstIntro)
		{
			m_fRegionGaveFirstIntro = true;
			CallScriptEventTimed("pet_notice", 0.1f);
		}
		m_iRegionIntroStage = 2;
		m_flRegionIntroTime = gpGlobals->time + 3.0f;
		return;
	}
	m_iRegionIntroStage = 0;
	if (!r->diff.empty())
		SendHUDMsg("Intended Difficulty", r->diff.c_str());
	const bool warn = MaxHP() >= 5 && MaxHP() < r->warnhp;
	if (warn)
		SendHUDMsg("WARNING", "This area maybe too difficult at your level!");
	if (!r->diff.empty() || warn)
		Log("MSR: %s difficulty '%s'%s\n", DisplayName(), r->diff.c_str(), warn ? " + low-HP warning" : "");
}

void CBasePlayer::PrepareRegionPutInWorld()
{
	if (!MSRegions::Active())
		return;
	// The map-wide intro would announce the merged map's first region everywhere;
	// the region tracker plays each region's own intro instead.
	SetScriptVar("GAVE_MAP_INTRO", 1);
	m_fRegionResync = true; // putinworld resets view distance; send the region's again
}
