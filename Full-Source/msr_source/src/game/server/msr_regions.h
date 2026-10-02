// Per-region awareness for merged "big world" maps.
//
// A merged map carries one info_msr_region point entity per original map
// (written by the MSR-BigWorld builder right after worldspawn). Each entity
// names the region, the half-open cell of space it owns and the metadata the
// original map used to have: title, description, difficulty, low-HP warning,
// weather cycle, sky and view distance. With no such entities (every normal
// map) nothing here changes behaviour: lookups return REGION_NONE and callers
// fall back to their map-wide logic.
#pragma once

#include <string>
#include <vector>

class CBaseEntity;
class CBasePlayer;
class CMSMonster;
typedef struct edict_s edict_t;
typedef struct KeyValueData_s KeyValueData;

#define REGION_NONE (-1)

struct msr_region_t
{
	std::string name, title, desc, diff, weather, skyname;
	int warnhp = 0;
	bool allownight = true;
	float maxrange = 0;
	float cellMins[3] = {-65536, -65536, -65536}, cellMaxs[3] = {65536, 65536, 65536};
	float mins[3] = {0, 0, 0}, maxs[3] = {0, 0, 0}; // tight bounds of the region's world geometry
	std::string currentWeather;						 // last token rolled for this region
	std::vector<float> noLogout;					 // boxes (6 floats each) sealed off in a fresh copy of the region

	// Lifecycle: a region nobody has been in for ms_region_unload_time seconds is removed and
	// re-created fresh from its recorded map entities when a player heads back in.
	bool loaded = true;
	float lastOccupied = 0;
	float lastChange = 0;
	float nextLoadAttempt = 0;						 // after a failed load (no free edicts)
	int records = 0;								 // replayable map entities
	bool aheadUnentered = false;					 // loaded ahead of a player, nobody inside since
};

namespace MSRegions
{
bool SpawnSlotAvailable(); // Read-only counterpart for optional admission.
void Clear();											 // new map
bool Active();											 // map has a region table
int Count();
const msr_region_t *Get(int region);
int Find(const char *name);								 // REGION_NONE if unknown
int At(const float *point);								 // REGION_NONE when inactive or outside the world
int ForEntity(CBaseEntity *pEntity);					 // players: tracked region, pets: their player, monsters: home, else position
int ForScriptOwner(CBaseEntity *pOwner);				 // monsters/NPCs only; NONE for players, items, world, game master
bool IsPresent(CBasePlayer *pPlayer);					 // connected, loaded and placed in a region
const char *NameOr(int region, const char *fallback);

// Weather: the game master broadcasts one weather token to all players. With regions
// the home region (the one named like the BSP) keeps that token and every other region
// rolls its own from its list; each player is then sent their region's token. A broadcast
// from any other script only changes the caller's region.
// Returns false when regions are inactive (caller does the normal broadcast).
bool DispatchWeather(CBaseEntity *pCaller, const char *eventName, const char *token);
const char *WeatherFor(int region);						 // rolls on first use

bool Occupied(int region);								 // a loaded player is in it (NONE: always true)
bool Tracked(int region);								 // the tracker has a present player in it (what region player counts see)
void MarkOccupied(int region);							 // a player is being placed there before the tracker sees them
bool NoLogout(const float *point);						 // inside a place a fresh copy of its region seals off (no logout spot there)
CBasePlayer *PlayerMaster(CMSMonster *pMonster);		 // pet/summon/hireling's player, else NULL

// Region lifecycle. Map entities are recorded (classname + key/values, in load order) as the
// engine spawns them; an unloaded region is re-created by replaying its records.
bool RecordKeyValue(edict_t *pent, KeyValueData *pkvd);	 // true: consumed a builder region tag
void RecordSpawn(edict_t *pent, int spawnResult);
void EndLoad();											 // ServerActivate: stop recording
void Frame();											 // StartFrame: unload regions left empty, load ahead of players
bool IsLoaded(int region);								 // false while a load is under way
bool Replaying();										 // a region load is re-creating a map entity right now
bool TakeSpawnSlot();									 // one spawner monster per server frame on merged maps
bool EnsureLoaded(int region, const char *why);			 // re-create an unloaded region now (finishes a load under way)
bool PrepareArrival(const char *teleportTarget);		 // trigger_teleport about to move a player; false = destination can't load

void Init();											 // GameDLLInit: commands and cvars
void MapStart();										 // ServerActivate
} // namespace MSRegions

// Region-scoped player counts live in util.cpp: UTIL_NumActivePlayers(region),
// UTIL_TotalHP(region), UTIL_AvgHP(region), UTIL_NumPlayers(region).
