// Persistent world state: key/values that outlive the map and the server.
//
// A world is (realm, map): realm = cvar ms_realm (empty: "port<hostport>"), map = the loaded
// BSP name, lowercased. Keys are region-prefixed by convention ("thornlands.raid.cooldown").
// The in-memory copy here is the source of truth for the running server; FN keeps the
// durable copy (/api/v2/internal/world/<realm>/<map>), loaded once at map start and written
// back as batches of changed keys. Timers are TTLs on the wall clock, so they keep running
// while the map is down. With FN off (LAN, dev mode) the world lives in memory for the map.
//
// Scripts: "worldstate set|add|unset|dump", $get_worldstate(key[,default]),
// $get_worldstate_exists(key), $get_worldstate_ttl(key), game.worldstate.<key>, and the
// event game_worldstate_loaded (PARAM1 fn|offline|retry) on the world script and the game
// master. Admins: "msr_worldstate [list [prefix] | set <key> <value> [ttl] | del <key> | reload | flush]".
#pragma once

#include <string>

namespace WorldState {
void Init();                                  // GameDLLInit: cvars (ms_realm registered in svglobals), commands
void MapStart();                              // MSWorldSpawn after FN validation: blocking load (or offline)
void MapEnd();                                // MSGameEnd: blocking final flush of dirty keys
void Shutdown();                              // GameDLLShutdown: final flush + drain the FN request queue
void Frame();                                 // once per server frame (cheap); batches at most once per second
bool Loaded();                                // true once the world's keys are known (FN load ok, or offline)
bool Online();                                // syncing to FN
bool Pending();                               // FN on but its keys not in yet (unreachable at map start); false after 90 s
bool Get(const char *key, std::string &value);   // false if absent or expired
double TimeLeft(const char *key);             // seconds left; -1 permanent; 0 absent/expired
void Set(const char *key, const char *value, double ttlSeconds = -1); // ttl <= 0: permanent
void Unset(const char *key);
long Add(const char *key, long delta, double ttlSeconds = -1);      // numeric counter; missing = 0; returns new value
bool ValidKey(const char *key, bool allowReserved); // lowercase [a-z0-9][a-z0-9_.:-]{0,63}; reserved prefixes boss. logout. sys. (C++ only) and global. local. game. const. (never)
double Now();                                 // wall clock epoch seconds (time(NULL) with sub-second if available)
}
