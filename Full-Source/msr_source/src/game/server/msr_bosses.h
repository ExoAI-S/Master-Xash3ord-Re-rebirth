// Boss respawn timers for merged "big world" maps.
//
// Policy "hold, don't complete": a boss killed by players gets a world state timer
// (msr_worldstate.h) "boss.<region>.<id>" = epoch of death, ttl = its cooldown. While the timer
// runs, its spawner slot neither spawns it nor fires anything it would fire (killtarget,
// perishtarget); the rest of its encounter waits at the boss. Exits and progression walls its
// death opens (the builder's "open" list, never loot) fire once per region instance instead, the
// first time a hold keeps it away.
//
// The builder (tools/build_edana_world.py, config "bosses") writes msr_boss (id),
// msr_boss_cooldown (seconds) and msr_boss_open ("a;b") onto the boss's spawner template;
// CMSMonster::KeyValue keeps them and CAreaMonsterSpawn::Activate (msmapents.cpp) hands them to
// the spawner slot. Every other slot gets a key derived from its template origin
// ("boss.<region>.<x>_<y>_<z>") that is only used when the monster dies as a flagged boss
// (NPC_IS_BOSS > 0) on a merged map.
//
// Admins: "msr_bosses [list | reset <id|key|all> | kill <id>]", cvar ms_boss_cooldown (seconds,
// default 1800) for bosses without their own cooldown.
#pragma once

#include <cstddef>
#include <vector>

class CMSMonster;

namespace MSBosses
{
void Init();		   // GameDLLInit: cvar ms_boss_cooldown, command msr_bosses
float Cooldown(float configured); // configured seconds if > 0, else ms_boss_cooldown

// "boss.<region>.<id>" (id given) or "boss.<region>.<x>_<y>_<z>" (template origin, rounded);
// region is the map name when REGION_NONE. false (out empty) if no valid key can be made.
bool MakeKey(char *out, size_t size, int region, const char *id, const float *origin);

// A spawner slot was set up (Activate): remembers configured bosses, and derived ones with a
// timer, so the command can list and reset them while their region is unloaded.
void Seen(const char *key, int region, bool configured, float cooldown, const char *open);

// A slot's monster died (DeathNotice, before perishtarget/killtarget fire). Starts the timer
// when the slot is configured, or the monster is a flagged boss on a merged map, and a player
// dealt it damage. true if a timer was started.
bool Died(const char *key, bool configured, float cooldown, CMSMonster *pMonster);

// A hold started keeping a boss away (logged once per hold); opened = the names it fired, or NULL
void Held(const char *key, double secondsLeft, const char *spawner, const char *opened);
} // namespace MSBosses

// msmapents.cpp: the boss slots of every spawner now in the map (for the admin command)
struct msr_bossslot_t
{
	const char *key;	   // valid until the spawner goes
	const char *spawner;   // its targetname
	int region;
	bool configured;
	bool held;			   // a hold is keeping it away now
	bool opened;		   // its open names fired: held until the region re-creates the spawner
	float cooldown;
	const char *open;	   // "" if none
	CMSMonster *pAlive;	   // its monster, if alive now
};
void MSR_BossSlots(std::vector<msr_bossslot_t> &out);
void MSR_BossRetry(const char *key); // held slots of this key look again now (after a reset)
