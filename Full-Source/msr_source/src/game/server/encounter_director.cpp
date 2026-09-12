#include "msdllheaders.h"
#include "player/player.h"
#include "monsters/msmonster.h"
#include "script.h"
#include "svglobals.h"
#include <algorithm>
#include <cmath>

namespace {
cvar_t automaticEvents = {"ms_dynamic_events", "0", FCVAR_SERVER};
cvar_t eventInterval = {"ms_event_interval", "600", FCVAR_SERVER};
cvar_t eventActive = {"ms_event_active", "0", FCVAR_SERVER};
EHANDLE actors[6];
EHANDLE dungeonMasters[32];
float nextCheck = 0, nextEvent = 0, eventDeadline = 0, nextManual = 0;
bool resourcesReady = false;
const char *activeName = "none";

void Reply(CBasePlayer *player, const char *text)
{
    if (player) ClientPrint(player->pev, HUD_PRINTTALK, text);
    else g_engfuncs.pfnServerPrint(text);
}
bool Playing(CBasePlayer *p)
{
    return p && p->IsAlive() && p->m_CharacterState == CHARSTATE_LOADED;
}
bool Allowed(CBasePlayer *p)
{
    if (!p) return true; // Only the registered server-console entry point uses null.
    if (!IS_DEDICATED_SERVER() && p->entindex() == 1) return true;
    for (auto &entry : dungeonMasters) if (entry.Get() == p->edict()) return true;
    return false;
}
int Alive()
{
    int count = 0;
    for (auto &actor : actors) if (actor && actor->IsAlive()) ++count;
    return count;
}
void Clear()
{
    // EHANDLE serial numbers prevent cleanup from touching a reused entity slot.
    for (auto &actor : actors) {
        if (actor) UTIL_Remove(actor);
        actor = nullptr;
    }
    activeName = "none";
    eventDeadline = 0;
    CVAR_SET_FLOAT("ms_event_active",0);
    nextEvent = gpGlobals->time + std::max(120.0f, eventInterval.value);
}
bool EdanaRaidActive()
{
    if (!g_pGameMasterEntity) return false;
    IScripted *script = g_pGameMasterEntity->GetScripted();
    const char *value=script ? script->GetFirstScriptVar("EDANA_RAID_ACTIVE") : nullptr;
    return value && atoi(value) != 0;
}
bool NearTransition(const Vector &pos)
{
    CBaseEntity *ent = nullptr;
    while ((ent = UTIL_FindEntityByClassname(ent, "msarea_transition"))) {
        const Vector &lo = ent->pev->absmin, &hi = ent->pev->absmax;
        if (pos.x > lo.x-128 && pos.x < hi.x+128 &&
            pos.y > lo.y-128 && pos.y < hi.y+128 &&
            pos.z > lo.z-128 && pos.z < hi.z+128) return true;
    }
    return false;
}
bool SpawnPoint(const Vector &candidate, Vector &result, CBasePlayer *anchor)
{
    TraceResult floor, space, line;
    UTIL_TraceLine(candidate + Vector(0,0,96), candidate - Vector(0,0,192),
                   ignore_monsters, nullptr, &floor);
    if (floor.fStartSolid || floor.fAllSolid || floor.flFraction == 1 || floor.vecPlaneNormal.z < 0.8f) return false;
    result = floor.vecEndPos + Vector(0,0,2);
    if (UTIL_PointContents(result) != CONTENTS_EMPTY || NearTransition(result)) return false;
    // Human hull covers the largest encounter creature. Model origins are at their feet.
    Vector center = result + Vector(0,0,38);
    UTIL_TraceHull(center, center, dont_ignore_monsters, human_hull, nullptr, &space);
    if (space.fStartSolid || space.fAllSolid) return false;
    if (anchor) {
        UTIL_TraceLine(anchor->pev->origin + Vector(0,0,24), center, ignore_monsters, anchor->edict(), &line);
        if (line.flFraction < 1) return false;
    }
    for (int i=1; i<=gpGlobals->maxClients; ++i) {
        auto *p = (CBasePlayer *)UTIL_PlayerByIndex(i);
        if (Playing(p) && (p->pev->origin-result).Length() < 192) return false;
    }
    for (auto &actor : actors) if (actor && (actor->pev->origin-result).Length() < 80) return false;
    return true;
}
bool Begin(const char *kind, CBasePlayer *requester)
{
    if (!resourcesReady) { Reply(requester, "Dungeon Master: encounter resources are unavailable on this map.\n"); return false; }
    if (eventDeadline || EdanaRaidActive()) { Reply(requester, "Dungeon Master: finish or clear the current encounter first.\n"); return false; }
    if (gpGlobals->time < nextManual) { Reply(requester, "Dungeon Master: wait a few seconds before starting another encounter.\n"); return false; }
    const bool edana = FStrEq(STRING(gpGlobals->mapname), "edana");
    CBasePlayer *anchor = Playing(requester) ? requester : nullptr;
    int players = 0;
    float partyHP = 0;
    for (int i=1; i<=gpGlobals->maxClients; ++i) {
        auto *p = (CBasePlayer *)UTIL_PlayerByIndex(i);
        if (Playing(p)) { ++players; partyHP += p->pev->max_health; if (!anchor) anchor=p; }
    }
    if (!edana && !anchor) { Reply(requester, "Dungeon Master: enter the map with a loaded character first.\n"); return false; }
    // Edana uses its outdoor entrance courtyard, away from the character shrine.
    Vector origin = edana ? Vector(1600,2250,-128) : anchor->pev->origin;
    if (edana && anchor && (anchor->pev->origin-origin).Length() > 1000) {
        Reply(requester, "Dungeon Master: approach Edana's Thornlands entrance to begin.\n"); return false;
    }
    const bool orcs = FStrEq(kind, "orcs");
    const int wanted = std::min(6, 2 + std::max(1, players));
    int spawned = 0;
    for (int attempt=0; attempt<48 && spawned<wanted; ++attempt) {
        const float angle=RANDOM_FLOAT(0,6.2831853f), distance=edana ? RANDOM_FLOAT(60,220) : RANDOM_FLOAT(320,560);
        Vector candidate=origin+Vector(std::cos(angle)*distance,std::sin(angle)*distance,0), position;
        if (!SpawnPoint(candidate,position,edana ? nullptr : anchor)) continue;
        auto *mob = (CMSMonster *)GET_PRIVATE(CREATE_NAMED_ENTITY(MAKE_STRING("ms_npc")));
        if (!mob) break;
        mob->pev->origin=position;
        const char *script=orcs ? ((partyHP>=300 && spawned==wanted-1) ? "monsters/orc_warrior" : "monsters/orc_weak") : "monsters/giantrat";
        mob->Spawn(script);
        mob->StoreEntity(g_pGameMasterEntity, ENT_CREATIONOWNER);
        msstringlist params;
        mob->CallScriptEvent("game_dynamically_created", &params);
        actors[spawned++]=mob;
    }
    nextManual=gpGlobals->time+15;
    if (!spawned) { Reply(requester,"Dungeon Master: no clear, dry spawn area found. Move to open ground.\n"); return false; }
    activeName=orcs ? "Orc raiding party" : "Giant rat infestation";
    eventDeadline=gpGlobals->time+180;
    CVAR_SET_FLOAT("ms_event_active",1);
    UTIL_ClientPrintAll(HUD_PRINTTALK, orcs ? "An Orc raiding party has appeared nearby!\n" : "Giant rats are gathering nearby!\n");
    char message[160];
    snprintf(message,sizeof(message),"[Director] Started %s with %d creatures.\n",activeName,spawned);
    Reply(nullptr,message);
    return true;
}
void Action(CBasePlayer *p,const char *action)
{
    if (!p && FStrEq(action,"inspect")) {
        CBaseEntity *ent=nullptr;
        while ((ent=UTIL_FindEntityByClassname(ent,"ms_npc"))) {
            if (!strstr(ent->DisplayName(),"Brenn")) continue;
            char row[180];
            snprintf(row,sizeof(row),"Guard: %s at %.0f %.0f %.0f, alive=%d\n",ent->DisplayName(),ent->pev->origin.x,ent->pev->origin.y,ent->pev->origin.z,ent->IsAlive());
            Reply(nullptr,row);
        }
        for (auto &actor:actors) if (actor) {
            char row[180];
            snprintf(row,sizeof(row),"Event actor: %s at %.0f %.0f %.0f, alive=%d\n",actor->DisplayName(),actor->pev->origin.x,actor->pev->origin.y,actor->pev->origin.z,actor->IsAlive());
            Reply(nullptr,row);
        }
        return;
    }
    if (FStrEq(action,"status")) {
        char status[240];
        snprintf(status,sizeof(status),"Dungeon Master: %s | random events %s | encounter: %s (%d alive)\n",
            Allowed(p) ? "control granted" : "host grant required", automaticEvents.value ? "ON" : "OFF",activeName,Alive());
        Reply(p,status); return;
    }
    if (!Allowed(p)) { Reply(p,"Dungeon Master: the host must grant you control with the Dungeon Master host tool.\n"); return; }
    if (FStrEq(action,"orcs") || FStrEq(action,"rats")) Begin(action,p);
    else if (FStrEq(action,"on") || FStrEq(action,"off")) {
        CVAR_SET_FLOAT("ms_dynamic_events",FStrEq(action,"on") ? 1 : 0);
        nextEvent=gpGlobals->time+std::max(120.0f,eventInterval.value);
        Reply(p,automaticEvents.value ? "Dungeon Master: random encounters enabled.\n" : "Dungeon Master: random encounters paused.\n");
    } else if (FStrEq(action,"clear")) { Clear(); Reply(p,"Dungeon Master: director encounter cleared.\n"); }
    else Reply(p,"Dungeon Master: status, orcs, rats, on, off, clear.\n");
}
void ServerAction() { Action(nullptr,CMD_ARGC()==2 ? CMD_ARGV(1) : "status"); }
void Grant()
{
    if (CMD_ARGC()!=2) { Reply(nullptr,"Usage: ms_dm_grant <zero-based slot from status>. Use ms_dm_revoke to revoke all.\n"); return; }
    const char *slotText=CMD_ARGV(1);
    if (!*slotText || strspn(slotText,"0123456789")!=strlen(slotText)) return;
    int slot=atoi(slotText);
    if (slot<0 || slot>=gpGlobals->maxClients || slot>=32) { Reply(nullptr,"Invalid player slot.\n"); return; }
    auto *p=(CBasePlayer *)UTIL_PlayerByIndex(slot+1);
    if (!p || !(p->pev->flags & FL_CLIENT)) { Reply(nullptr,"No connected player in that slot.\n"); return; }
    dungeonMasters[slot]=p;
    Reply(p,"Dungeon Master control granted. Open the game menu and choose Dungeon Master.\n");
    Reply(nullptr,"[Director] Granted Dungeon Master for this connection and map.\n");
}
void Revoke() { for (auto &entry:dungeonMasters) entry=nullptr; Reply(nullptr,"[Director] All grants revoked.\n"); }
}
void EncounterDirector_Init()
{
    CVAR_REGISTER(&automaticEvents); CVAR_REGISTER(&eventInterval); CVAR_REGISTER(&eventActive);
    g_engfuncs.pfnAddServerCommand((char *)"ms_event",ServerAction);
    g_engfuncs.pfnAddServerCommand((char *)"ms_dm_grant",Grant);
    g_engfuncs.pfnAddServerCommand((char *)"ms_dm_revoke",Revoke);
}
void EncounterDirector_MapStart()
{
    for (auto &actor:actors) actor=nullptr;
    for (auto &entry:dungeonMasters) entry=nullptr;
    nextCheck=0; eventDeadline=0; nextManual=0; activeName="none";
    CVAR_SET_FLOAT("ms_event_active",0);
    nextEvent=gpGlobals->time+std::max(120.0f,eventInterval.value);
    resourcesReady=true;
    for (const char *name:{"monsters/orc_weak","monsters/orc_warrior","monsters/giantrat"}) {
        CScript script;
        if (!script.Spawn(name,nullptr,nullptr,true)) resourcesReady=false;
    }
    Reply(nullptr,resourcesReady ? "[Director] Map initialized, resources ready.\n" : "[Director] Map initialized, resources unavailable.\n");
}
void EncounterDirector_Disconnect(CBasePlayer *p)
{
    if (!p) return;
    for (auto &entry:dungeonMasters) if (entry.Get()==p->edict()) entry=nullptr;
}
bool EncounterDirector_Command(CBasePlayer *p,const char *command)
{
    if (!FStrEq(command,"ms_dm")) return false;
    Action(p,CMD_ARGC()==2 ? CMD_ARGV(1) : "status");
    return true;
}
void EncounterDirector_Frame()
{
    if (gpGlobals->time<nextCheck) return;
    nextCheck=gpGlobals->time+1;
    if (eventDeadline && (gpGlobals->time>=eventDeadline || Alive()==0)) {
        UTIL_ClientPrintAll(HUD_PRINTTALK,Alive() ? "The remaining event creatures scatter.\n" : "The encounter is complete.\n");
        Clear();
    }
    if (!automaticEvents.value || eventDeadline || gpGlobals->time<nextEvent) return;
    nextEvent=gpGlobals->time+RANDOM_FLOAT(std::max(120.0f,eventInterval.value),std::max(120.0f,eventInterval.value)*1.5f);
    CBasePlayer *chosen=nullptr;
    int eligible=0;
    for (int i=1;i<=gpGlobals->maxClients;++i) {
        auto *p=(CBasePlayer *)UTIL_PlayerByIndex(i);
        if (Playing(p) && RANDOM_LONG(1,++eligible)==1) chosen=p;
    }
    if (chosen) Begin(RANDOM_LONG(0,1) ? "orcs" : "rats",chosen);
}
