// Opt-in ground mounts. The rider remains the one predicted collision body;
// the horse is a networked visual, never a second physics simulation.
#include "msdllheaders.h"
#include "player/player.h"
#include "msr_mounts.h"
#include "ms/mount_policy.h"
#include "usercmd.h"
#include <cmath>
#include <cstring>

namespace
{
cvar_t g_Mounts = {"ms_mounts", "0", FCVAR_SERVER};
int g_PrecachedHorseIndex = 0; // Diagnostics only; never used as a cross-map model handle.
constexpr const char *kHorseModel = "models/mounts/plains_horse.mdl";
constexpr const char *kStablemasterModel = "models/npc/human1.mdl";
constexpr int kBlockedButtons = IN_ATTACK | IN_ATTACK2 | IN_JUMP | IN_DUCK;
constexpr int kRestrictions = PLAYER_MOVE_NOATTACK | PLAYER_MOVE_NOJUMP | PLAYER_MOVE_NODUCK;

bool Enabled() { return g_Mounts.value != 0.0f; }
void Tell(CBasePlayer *player, const char *message)
{
    if (player)
        ClientPrint(player->pev, HUD_PRINTCENTER, message);
}
bool Cheats()
{
    if (CVAR_GET_FLOAT("sv_cheats") != 0.0f)
        return true;
    g_engfuncs.pfnServerPrint("Mount test commands require sv_cheats 1.\n");
    return false;
}
CBasePlayer *SlotPlayer(int argument = 1)
{
    const int index = CMD_ARGC() > argument ? atoi(CMD_ARGV(argument)) : 1;
    if (index < 1 || index > gpGlobals->maxClients)
        return NULL;
    CBasePlayer *player = (CBasePlayer *)UTIL_PlayerByIndex(index);
    return player && player->IsPlayer() ? player : NULL;
}
CBasePlayer *TestPlayer(int argument = 1)
{
    CBasePlayer *player = SlotPlayer(argument);
    return player && player->m_fInServer && player->m_CharacterState == CHARSTATE_LOADED ? player : NULL;
}
bool Dry(const Vector &point)
{
    const int contents = UTIL_PointContents(point);
    return contents != CONTENTS_WATER && contents != CONTENTS_SLIME && contents != CONTENTS_LAVA;
}
// A swept standing-player hull validates both the route and the destination.
// No crouching, wall teleporting, dropping off ledges or dismounting in water.
bool GroundSpot(CBasePlayer *player, const Vector &wanted, Vector &result)
{
    TraceResult path, ground;
    UTIL_TraceHull(player->pev->origin, wanted, dont_ignore_monsters, human_hull, player->edict(), &path);
    if (path.fStartSolid || path.fAllSolid || path.flFraction < 1.0f)
        return false;
    UTIL_TraceHull(wanted + Vector(0, 0, 18), wanted - Vector(0, 0, 64),
        dont_ignore_monsters, human_hull, player->edict(), &ground);
    if (ground.fStartSolid || ground.fAllSolid || ground.flFraction >= 1.0f || ground.vecPlaneNormal.z < 0.7f)
        return false;
    result = ground.vecEndPos + Vector(0, 0, 1);
    return Dry(result + Vector(0, 0, player->pev->mins.z + 4));
}
// A loan is placed in the paddock without relocating the requesting player.
// Only the pad and its floor must be clear; the NPC may stand between them.
bool LoanPad(CBasePlayer *player, const Vector &feet, Vector &result)
{
    TraceResult ground;
    const Vector center=feet+Vector(0,0,36);
    UTIL_TraceHull(center+Vector(0,0,18),center-Vector(0,0,64),
        dont_ignore_monsters,human_hull,player->edict(),&ground);
    if (ground.fStartSolid || ground.fAllSolid || ground.flFraction>=1 || ground.vecPlaneNormal.z<0.7f)
        return false;
    result=ground.vecEndPos-Vector(0,0,35);
    return Dry(result+Vector(0,0,4));
}
}

class CMSRHorse : public CBaseAnimating
{
public:
    EHANDLE m_Rider{};
    EHANDLE m_Customer{}, m_Stablemaster{};
    bool m_Assigned = false;
    Vector m_HomeOrigin, m_HomeAngles, m_SavedView;
    int m_SavedPhysicsFlags = 0;
    float m_NextUse = 0;
    usercmd_s m_LastCommand{}; // Read-only diagnostics of actual server input.
    float m_LastCommandTime = 0;

    int ObjectCaps() { return (CBaseAnimating::ObjectCaps() & ~FCAP_ACROSS_TRANSITION) | FCAP_IMPULSE_USE; }
    void Precache() { MSRMounts::Precache(); }
    void Spawn()
    {
        Precache();
        if (!MODEL_INDEX(kHorseModel))
        {
            ALERT(at_console, "MSR mounts: missing %s; horse removed.\n", kHorseModel);
            UTIL_Remove(this);
            return;
        }
        SET_MODEL(edict(), kHorseModel);
        pev->movetype = MOVETYPE_NONE;
        // Prototype geometry uses the already compiled standing-player hull.
        // An unmounted horse is also non-solid so it cannot trap a dismount.
        pev->solid = SOLID_NOT;
        pev->takedamage = DAMAGE_NO;
        UTIL_SetSize(pev, Vector(-28, -18, 0), Vector(28, 18, 80));
        UTIL_SetOrigin(pev, pev->origin);
        m_HomeOrigin = pev->origin;
        m_HomeAngles = pev->angles;
        m_DisplayName = "Plains Horse";
        pev->sequence = 0;
        pev->framerate = 1;
        ResetSequenceInfo();
        SetUse(&CMSRHorse::HorseUse);
        SetThink(&CMSRHorse::HorseThink);
        pev->nextthink = gpGlobals->time + 0.05f;
        ALERT(at_console, "MSR mounts: horse %d spawned, model=%d enabled=%d at %.1f,%.1f,%.1f.\n",
            entindex(), pev->modelindex, Enabled() ? 1 : 0, pev->origin.x, pev->origin.y, pev->origin.z);
    }
    CBasePlayer *GetRider()
    {
        CBaseEntity *entity = m_Rider;
        return entity && entity->IsPlayer() ? (CBasePlayer *)entity : NULL;
    }
    CBasePlayer *GetCustomer()
    {
        CBaseEntity *entity = m_Customer;
        return entity && entity->IsPlayer() ? (CBasePlayer *)entity : NULL;
    }
    bool TryMount(CBasePlayer *player, bool quiet = false)
    {
        if (!player)
            return false;
        if (m_Assigned && GetCustomer() != player)
        {
            if (!quiet) Tell(player, "This horse belongs to another rider. Ask the stablemaster for yours.");
            return false;
        }
        const MSRMountPolicy::MountGate gate{
            Enabled(), (bool)(int)player->m_hMount, (bool)(int)m_Rider,
            player->IsAlive() != 0, player->m_fInServer && player->m_CharacterState == CHARSTATE_LOADED,
            FBitSet(player->pev->flags, FL_ONGROUND) != 0,
            !FBitSet(player->pev->flags, FL_DUCKING) && !player->pev->bInDuck,
            player->pev->movetype == MOVETYPE_WALK, player->IsActing() || player->IsShielding(),
            player->InMenu || player->HasConditions(MONSTER_TRADING) || player->HasConditions(MONSTER_OPENCONTAINER) ||
                FBitSet(player->m_StatusFlags, PLAYER_MOVE_SITTING | PLAYER_MOVE_NOMOVE | PLAYER_MOVE_NOATTACK) ||
                FBitSet(player->pev->flags, FL_FROZEN | FL_SPECTATOR | FL_ONTRAIN) || player->m_pTank != NULL,
            player->pev->waterlevel};
        if (!MSRMountPolicy::CanMount(gate))
        {
            if (!quiet)
                Tell(player, gate.horseOccupied ? "This horse already has a rider." :
                    "Stand on dry ground, finish your action, then use the horse.");
            return false;
        }
        if ((player->pev->origin - pev->origin).Length2D() > 96)
            return false;
        Vector destination;
        if (!GroundSpot(player, pev->origin - Vector(0, 0, player->pev->mins.z), destination))
        {
            if (!quiet) Tell(player, "There is no safe space to mount here.");
            return false;
        }
        m_SavedView = player->pev->view_ofs;
        m_SavedPhysicsFlags = player->pev->iuser3;
        m_Rider = player;
        player->m_hMount = this;
        pev->owner = player->edict(); // ordinary entity delta already carries the owner index
        SetBits(player->m_StatusFlags, PLAYER_MOVE_MOUNTED);
        ClearBits(player->m_StatusFlags, PLAYER_MOVE_RUNNING | PLAYER_MOVE_ATTACKING);
        UTIL_SetOrigin(player->pev, destination);
        player->pev->velocity = player->pev->basevelocity = g_vecZero;
        MSRMounts::ApplyRestrictions(player);
        Follow(player);
        m_NextUse = gpGlobals->time + 0.35f;
        if (!quiet) Tell(player, "Mounted. Move normally, hold Run to gallop, and Use to dismount.");
        return true;
    }
    bool EndRide(bool forced, const char *reason, bool quiet = false)
    {
        CBasePlayer *player = GetRider();
        if (!player)
        {
            m_Rider = (CBaseEntity *)NULL;
            pev->owner = NULL;
            return true;
        }
        Vector destination = player->pev->origin;
        if (!forced)
        {
            if (!FBitSet(player->pev->flags, FL_ONGROUND))
            {
                if (!quiet) Tell(player, "Wait until the horse is on the ground to dismount.");
                return false;
            }
            Vector forward, right;
            UTIL_MakeVectorsPrivate(Vector(0, player->pev->v_angle.y, 0), forward, right, NULL);
            const Vector offsets[] = {right * 64, right * -64, forward * -72, forward * 72};
            bool found = false;
            for (const Vector &offset : offsets)
                if (GroundSpot(player, player->pev->origin + offset, destination)) { found = true; break; }
            if (!found)
            {
                if (!quiet) Tell(player, "No safe room beside the horse. Move into open ground first.");
                return false;
            }
        }
        m_Rider = (CBaseEntity *)NULL;
        pev->owner = NULL;
        player->m_hMount = (CBaseEntity *)NULL;
        ClearBits(player->m_StatusFlags, PLAYER_MOVE_MOUNTED | PLAYER_MOVE_RUNNING);
        player->pev->iuser3 = m_SavedPhysicsFlags;
        player->pev->view_ofs = m_SavedView;
        player->pev->framerate = 1;
        player->pev->gaitsequence = 0;
        const int standing = player->LookupSequence("stand");
        player->pev->sequence = standing >= 0 ? standing : 0;
        player->pev->frame = 0;
        player->pev->animtime = gpGlobals->time;
        if (!forced)
        {
            UTIL_SetOrigin(player->pev, destination);
            player->pev->velocity = player->pev->basevelocity = g_vecZero;
        }
        else
        {
            // Forced release never teleports a player (death, disconnect, water,
            // server teardown). Return the visual to its stable/home instead.
            UTIL_SetOrigin(pev, m_HomeOrigin);
            pev->angles = m_HomeAngles;
        }
        pev->sequence = 0;
        pev->frame = 0;
        pev->framerate = 1;
        ResetSequenceInfo();
        m_NextUse = gpGlobals->time + 0.35f;
        if (!quiet && !forced) Tell(player, "Dismounted.");
        ALERT(at_console, "MSR mounts: rider %d released (%s).\n", player->entindex(), reason);
        return true;
    }
    void Follow(CBasePlayer *player)
    {
        UTIL_SetOrigin(pev, player->pev->origin + Vector(0, 0, player->pev->mins.z));
        pev->angles = Vector(0, player->pev->v_angle.y, 0);
        const float speed = player->pev->velocity.Length2D();
        const int sequence = speed < 10 ? 0 : speed > MSRMountPolicy::WalkSpeed + 20 ? 2 : 1;
        if (sequence != pev->sequence)
        {
            pev->sequence = sequence;
            pev->frame = 0;
            ResetSequenceInfo();
        }
        pev->framerate = sequence == 0 ? 1 : V_max(0.35f, V_min(1.75f,
            speed / (sequence == 2 ? MSRMountPolicy::GallopSpeed : MSRMountPolicy::WalkSpeed)));
    }
    void EXPORT HorseUse(CBaseEntity *activator, CBaseEntity *, USE_TYPE, float)
    {
        if (activator && activator->IsPlayer() && gpGlobals->time >= m_NextUse)
            TryMount((CBasePlayer *)activator);
    }
    void EXPORT HorseThink()
    {
        if (m_Assigned)
        {
            CBasePlayer *customer = GetCustomer();
            if (!customer || !customer->m_fInServer || !customer->IsAlive() ||
                customer->m_CharacterState != CHARSTATE_LOADED || !Enabled())
            {
                EndRide(true, "customer unavailable", true);
                UTIL_Remove(this);
                return;
            }
        }
        CBasePlayer *player = GetRider();
        if (player)
        {
            if (!player->m_fInServer || !player->IsAlive() || !Enabled())
                EndRide(true, "rider unavailable");
            else
                Follow(player);
        }
        else if (pev->owner)
        {
            pev->owner = NULL;
            m_Rider = (CBaseEntity *)NULL;
            UTIL_SetOrigin(pev, m_HomeOrigin);
        }
        StudioFrameAdvance();
        pev->nextthink = gpGlobals->time + 0.05f;
    }
    void Deactivate() { EndRide(true, "horse deactivated", true); }
};

LINK_ENTITY_TO_CLASS(ms_horse, CMSRHorse);

// Per-session loan horses: no character/FN writes and no shared rider slot.
class CMSRStablemaster : public CBaseAnimating
{
public:
    float m_NextUse = 0;
    int ObjectCaps() { return (CBaseAnimating::ObjectCaps() & ~FCAP_ACROSS_TRANSITION) | FCAP_IMPULSE_USE; }
    void Precache() { PRECACHE_MODEL(kStablemasterModel); MSRMounts::Precache(); }
    void Spawn()
    {
        Precache();
        SET_MODEL(edict(), kStablemasterModel);
        pev->movetype = MOVETYPE_NONE;
        pev->solid = SOLID_BBOX;
        pev->takedamage = DAMAGE_NO;
        UTIL_SetSize(pev, Vector(-16,-16,0), Vector(16,16,72));
        UTIL_SetOrigin(pev, pev->origin);
        m_DisplayName = "Stablemaster";
        const int idle = LookupSequence("idle1");
        pev->sequence = idle >= 0 ? idle : 0;
        pev->framerate = 1;
        ResetSequenceInfo();
        SetUse(&CMSRStablemaster::StableUse);
        SetThink(&CMSRStablemaster::StableThink);
        pev->nextthink = gpGlobals->time + 0.1f;
    }
    CMSRHorse *Request(CBasePlayer *player)
    {
        if (!Enabled() || !player || !player->m_fInServer || !player->IsAlive() ||
            player->m_CharacterState != CHARSTATE_LOADED || !MODEL_INDEX(kHorseModel))
            return NULL;
        if ((player->pev->origin - pev->origin).Length() > 112 ||
            player->InMenu || player->IsActing() || player->IsShielding())
            return NULL;
        // Search the authoritative entities, including an unmounted loan horse.
        for (int index=gpGlobals->maxClients+1; index<gpGlobals->maxEntities; ++index)
        {
            edict_t *entity=INDEXENT(index);
            if (!entity || entity->free || !entity->pvPrivateData || (entity->v.flags & FL_KILLME)) continue;
            if (!FStrEq(STRING(entity->v.classname), "ms_horse")) continue;
            CMSRHorse *horse=(CMSRHorse *)CBaseEntity::Instance(entity);
            if (horse->m_Assigned && horse->GetCustomer()==player)
            {
                Tell(player, "Your horse is already waiting. Use it to ride; Use again to dismount.");
                return horse;
            }
        }
        if ((int)player->m_hMount)
        {
            Tell(player, "Dismount before requesting a horse.");
            return NULL;
        }
        for (int pad=0; pad<8; ++pad)
        {
            const Vector feet=pev->origin+Vector(180+(pad%4)*220,140+(pad/4)*180,0);
            bool occupied=false;
            for (int index=gpGlobals->maxClients+1; index<gpGlobals->maxEntities; ++index)
            {
                edict_t *entity=INDEXENT(index);
                if (!entity || entity->free || !entity->pvPrivateData || (entity->v.flags & FL_KILLME)) continue;
                if (FStrEq(STRING(entity->v.classname), "ms_horse") &&
                    (entity->v.origin-feet).Length2D()<155) { occupied=true; break; }
            }
            Vector point;
            if (occupied || !LoanPad(player,feet,point)) continue;
            CMSRHorse *horse=(CMSRHorse *)CBaseEntity::Create("ms_horse",
                point,Vector(0,0,0));
            if (!horse || (horse->pev->flags & FL_KILLME)) return NULL;
            horse->m_Customer=player;
            horse->m_Stablemaster=this;
            horse->m_Assigned=true;
            Tell(player, "Your horse is ready beside the stable. Use it to mount.");
            ALERT(at_console,"Stablemaster: player %d assigned horse %d pad=%d.\n",player->entindex(),horse->entindex(),pad);
            return horse;
        }
        Tell(player,"The paddock is full or blocked. Clear some space and ask again.");
        return NULL;
    }
    void EXPORT StableUse(CBaseEntity *activator,CBaseEntity *,USE_TYPE,float)
    {
        if (activator && activator->IsPlayer() && gpGlobals->time>=m_NextUse)
        {
            m_NextUse=gpGlobals->time+0.25f;
            Request((CBasePlayer *)activator);
        }
    }
    void EXPORT StableThink() { StudioFrameAdvance(); pev->nextthink=gpGlobals->time+0.1f; }
};
LINK_ENTITY_TO_CLASS(ms_stablemaster, CMSRStablemaster);

namespace
{
CMSRHorse *Horse(CBaseEntity *entity)
{
    return entity && entity->pev && FStrEq(STRING(entity->pev->classname), "ms_horse") ? (CMSRHorse *)entity : NULL;
}
CMSRHorse *MountedHorse(CBasePlayer *player)
{
    return player ? Horse((CBaseEntity *)player->m_hMount) : NULL;
}
void StableTestCommand()
{
    if (!Cheats()) return;
    CBasePlayer *first=TestPlayer(), *second=TestPlayer(2);
    CBaseEntity *entity=UTIL_FindEntityByClassname(NULL,"ms_stablemaster");
    if (!entity || !first || !second || first==second || (int)first->m_hMount || (int)second->m_hMount)
    {
        g_engfuncs.pfnServerPrint("Stablemaster test needs two loaded, unmounted players beside the stablemaster.\n");
        return;
    }
    CMSRStablemaster *stable=(CMSRStablemaster *)entity;
    CMSRHorse *a=stable->Request(first), *b=stable->Request(second);
    const bool ok=a && b && a!=b && a->GetCustomer()==first && b->GetCustomer()==second &&
        stable->Request(first)==a && stable->Request(second)==b &&
        !a->TryMount(second,true) && !b->TryMount(first,true);
    g_engfuncs.pfnServerPrint(ok ? "Stablemaster: two customers, distinct horses, repeat reuse and other-rider denial PASS.\n" :
        "Stablemaster test FAILED.\n");
}
void SpawnCommand()
{
    if (!Cheats()) return;
    CBasePlayer *player = TestPlayer();
    if (!Enabled() || !player || !MODEL_INDEX(kHorseModel))
    {
        g_engfuncs.pfnServerPrint("Set ms_mounts 1 before loading a map, load a character, then ms_mount_spawn [player index].\n");
        return;
    }
    Vector forward;
    UTIL_MakeVectorsPrivate(Vector(0, player->pev->v_angle.y, 0), forward, NULL, NULL);
    Vector point;
    if (!GroundSpot(player, player->pev->origin + forward * 64, point))
    {
        g_engfuncs.pfnServerPrint("Mount spawn: no clear dry ground ahead.\n");
        return;
    }
    CBaseEntity *horse = CBaseEntity::Create("ms_horse", point + Vector(0, 0, player->pev->mins.z),
        Vector(0, player->pev->v_angle.y, 0));
    if (horse) ALERT(at_console, "MSR mounts: horse %d spawned for test.\n", horse->entindex());
}
void StatusCommand()
{
    int count = 0;
    for (int index = gpGlobals->maxClients + 1; index < gpGlobals->maxEntities; ++index)
    {
        edict_t *entity = INDEXENT(index);
        if (!entity || entity->free || !entity->pvPrivateData) continue;
        CMSRHorse *horse = Horse(CBaseEntity::Instance(entity));
        if (!horse) continue;
        ++count;
        CBasePlayer *rider = horse->GetRider();
        ALERT(at_console, "Mount %d rider=%d owner=%d solid=%d xyz=%.1f,%.1f,%.1f seq=%d customer=%d\n",
            horse->entindex(), rider ? rider->entindex() : 0, horse->pev->owner ? ENTINDEX(horse->pev->owner) : 0,
            horse->pev->solid, horse->pev->origin.x, horse->pev->origin.y, horse->pev->origin.z, horse->pev->sequence,
            horse->GetCustomer() ? horse->GetCustomer()->entindex() : 0);
        if (rider)
        {
            ALERT(at_console, "  rider status=%d physics=%d view=%.1f speed=%.1f effect-percent=%.1f hull=%.1f..%.1f\n",
                rider->m_StatusFlags, rider->pev->iuser3, rider->pev->view_ofs.z,
                rider->pev->velocity.Length2D(), rider->pev->maxspeed, rider->pev->mins.z, rider->pev->maxs.z);
            ALERT(at_console, "  rider xyz=%.4f,%.4f,%.4f velocity=%.4f,%.4f,%.4f view-yaw=%.4f buttons=%d base-cap=%.1f\n",
                rider->pev->origin.x, rider->pev->origin.y, rider->pev->origin.z,
                rider->pev->velocity.x, rider->pev->velocity.y, rider->pev->velocity.z,
                rider->pev->v_angle.y, rider->pbs.ButtonsDown, rider->CurrentSpeed());
            ALERT(at_console, "  usercmd age=%.3f msec=%d buttons=%d forward=%.1f side=%.1f up=%.1f yaw=%.1f\n",
                gpGlobals->time - horse->m_LastCommandTime, horse->m_LastCommand.msec,
                horse->m_LastCommand.buttons, horse->m_LastCommand.forwardmove,
                horse->m_LastCommand.sidemove, horse->m_LastCommand.upmove, horse->m_LastCommand.viewangles[1]);
            if (CVAR_GET_FLOAT("sv_cheats") != 0.0f)
            {
                entvars_t *pev = rider->pev;
                edict_t *ground = pev->groundentity;
                ALERT(at_console, "  hull flags=0x%x movetype=%d solid=%d deadflag=%d waterlevel=%d watertype=%d onground=%d ground=%d classname=%s frozen=%d train=%d nomove=%d norun=%d\n",
                    pev->flags, pev->movetype, pev->solid, pev->deadflag, pev->waterlevel, pev->watertype,
                    FBitSet(pev->flags, FL_ONGROUND) ? 1 : 0, ground ? ENTINDEX(ground) : -1,
                    ground ? STRING(ground->v.classname) : "none", FBitSet(pev->flags, FL_FROZEN) ? 1 : 0,
                    FBitSet(pev->flags, FL_ONTRAIN) ? 1 : 0, FBitSet(pev->iuser3, PLAYER_MOVE_NOMOVE) ? 1 : 0,
                    FBitSet(pev->iuser3, PLAYER_MOVE_NORUN) ? 1 : 0);
                ALERT(at_console, "  bounds mins=%.4f,%.4f,%.4f maxs=%.4f,%.4f,%.4f basevelocity=%.4f,%.4f,%.4f gravity=%.4f friction=%.4f contents-origin=%d contents-feet=%d sv-stepsize=%.4f\n",
                    pev->mins.x, pev->mins.y, pev->mins.z, pev->maxs.x, pev->maxs.y, pev->maxs.z,
                    pev->basevelocity.x, pev->basevelocity.y, pev->basevelocity.z, pev->gravity, pev->friction,
                    UTIL_PointContents(pev->origin), UTIL_PointContents(pev->origin + Vector(0, 0, pev->mins.z + 1)),
                    CVAR_GET_FLOAT("sv_stepsize"));
                Vector forward;
                UTIL_MakeVectorsPrivate(Vector(0, pev->v_angle.y, 0), forward, NULL, NULL);
                const Vector lifted = pev->origin + Vector(0, 0, 18);
                const Vector starts[] = {pev->origin, pev->origin, pev->origin, lifted, pev->origin};
                const Vector ends[] = {pev->origin, pev->origin + forward * 16, lifted, lifted + forward * 16,
                    pev->origin - Vector(0, 0, 2)};
                const char *names[] = {"stationary", "forward16", "stepup18", "raised-forward16", "ground-down2"};
                ALERT(at_console, "  TraceHull human_hull: authoritative server API; diagnostic probes, not the PM physent/playertrace list.\n");
                for (int n = 0; n < 5; ++n)
                {
                    TraceResult trace;
                    UTIL_TraceHull(starts[n], ends[n], dont_ignore_monsters, human_hull, rider->edict(), &trace);
                    edict_t *hit = trace.pHit;
                    ALERT(at_console, "  trace %s startsolid=%d allsolid=%d fraction=%.6f end=%.4f,%.4f,%.4f normal=%.4f,%.4f,%.4f plane-dist=%.4f hit=%d class=%s solid=%d movetype=%d model=%s\n",
                        names[n], trace.fStartSolid, trace.fAllSolid, trace.flFraction,
                        trace.vecEndPos.x, trace.vecEndPos.y, trace.vecEndPos.z,
                        trace.vecPlaneNormal.x, trace.vecPlaneNormal.y, trace.vecPlaneNormal.z, trace.flPlaneDist,
                        hit ? ENTINDEX(hit) : -1, hit ? STRING(hit->v.classname) : "none",
                        hit ? hit->v.solid : -1, hit ? hit->v.movetype : -1, hit ? STRING(hit->v.model) : "none");
                }
            }
        }
    }
    ALERT(at_console, "MSR mounts: %d native horses; enabled=%d precached-model=%d.\n",
        count, Enabled() ? 1 : 0, g_PrecachedHorseIndex);
}
void PlaceCommand()
{
    if (!Cheats()) return;
    CBasePlayer *player = TestPlayer();
    if (CMD_ARGC() != 6 || !player || !player->IsAlive())
    {
        g_engfuncs.pfnServerPrint("Usage: ms_mount_place <loaded player index> <origin x> <y> <z> <view yaw>; sv_cheats 1 required.\n");
        return;
    }
    float values[4];
    for (int n = 0; n < 4; ++n)
    {
        char *end = NULL;
        const double value = strtod(CMD_ARGV(n + 2), &end);
        if (!end || *end || !std::isfinite(value) || fabs(value) > 32768.0)
        {
            g_engfuncs.pfnServerPrint("Mount place: coordinates and yaw must be finite numbers within +/-32768.\n");
            return;
        }
        values[n] = (float)value;
    }
    const Vector point(values[0], values[1], values[2]);
    TraceResult clear;
    UTIL_TraceHull(point, point, dont_ignore_monsters, human_hull, player->edict(), &clear);
    if (clear.fStartSolid || clear.fAllSolid || !Dry(point + Vector(0, 0, player->pev->mins.z + 4)))
    {
        g_engfuncs.pfnServerPrint("Mount place: destination standing hull is blocked or wet.\n");
        return;
    }
    MSRMounts::Release(player, "test placement");
    const float yaw = fmodf(values[3], 360.0f);
    UTIL_SetOrigin(player->pev, point);
    player->pev->velocity = player->pev->basevelocity = player->pev->avelocity = g_vecZero;
    player->pev->v_angle = player->pev->angles = Vector(0, yaw, 0);
    player->pev->fixangle = 1; // Engine sends the authoritative view rotation.
    ClearBits(player->pev->flags, FL_ONGROUND);
    player->pev->groundentity = NULL;
    ALERT(at_console, "Mount place: player %d origin=%.1f,%.1f,%.1f view-yaw=%.1f fixangle=%d.\n",
        player->entindex(), point.x, point.y, point.z, yaw, player->pev->fixangle);
}
void LifecycleCommand()
{
    if (!Cheats()) return;
    CBasePlayer *player = TestPlayer();
    if (!Enabled() || !player || (int)player->m_hMount || !MODEL_INDEX(kHorseModel))
    {
        CBasePlayer *raw = SlotPlayer();
        ALERT(at_console, "Mount test admission: slot=%d found=%d enabled=%d in-server=%d character-state=%d mount=%d model=%d flags=%d movement-status=%d.\n",
            CMD_ARGC() > 1 ? atoi(CMD_ARGV(1)) : 1, raw ? 1 : 0, Enabled() ? 1 : 0,
            raw && raw->m_fInServer ? 1 : 0, raw ? (int)raw->m_CharacterState : -1,
            raw ? (int)raw->m_hMount : 0, g_PrecachedHorseIndex, raw ? raw->pev->flags : 0,
            raw ? raw->m_StatusFlags : 0);
        g_engfuncs.pfnServerPrint("Mount lifecycle test needs ms_mounts 1 and an unmounted, loaded character on dry ground.\n");
        return;
    }
    const Vector initialOrigin = player->pev->origin, initialView = player->pev->view_ofs;
    const int initialStatus = player->m_StatusFlags, initialPhysics = player->pev->iuser3;
    CMSRHorse *horse = Horse(CBaseEntity::Create("ms_horse", initialOrigin + Vector(0, 0, player->pev->mins.z),
        Vector(0, player->pev->v_angle.y, 0)));
    if (!horse || !horse->TryMount(player, true))
    {
        if (horse) UTIL_Remove(horse);
        g_engfuncs.pfnServerPrint("Mount lifecycle test: cannot mount in this location.\n");
        return;
    }
    bool ok = horse->GetRider() == player && (CBaseEntity *)player->m_hMount == horse &&
        FBitSet(player->m_StatusFlags, PLAYER_MOVE_MOUNTED) && horse->pev->owner == player->edict() &&
        horse->pev->solid == SOLID_NOT && !horse->TryMount(player, true);
    CBasePlayer *other = CMD_ARGC() > 2 ? TestPlayer(2) : NULL;
    if (other && other != player) ok = ok && !horse->TryMount(other, true);
    // Airborne Use must leave the link intact. Forced cleanup must clear both
    // directions and restore the camera without relocating the player.
    const int initialFlags = player->pev->flags;
    ClearBits(player->pev->flags, FL_ONGROUND);
    ok = ok && !horse->EndRide(false, "test airborne", true) && horse->GetRider() == player;
    player->pev->flags = initialFlags;
    horse->EndRide(true, "lifecycle test", true);
    ok = ok && !(int)player->m_hMount && !horse->GetRider() && !horse->pev->owner &&
        !FBitSet(player->m_StatusFlags, PLAYER_MOVE_MOUNTED) && player->pev->view_ofs == initialView;
    UTIL_SetOrigin(player->pev, initialOrigin);
    player->m_StatusFlags = initialStatus;
    player->pev->iuser3 = initialPhysics;
    UTIL_Remove(horse);
    g_engfuncs.pfnServerPrint(ok ? "Mount lifecycle: ownership, duplicate denial, airborne denial and cleanup PASS.\n" :
        "Mount lifecycle test FAILED.\n");
}
}

namespace MSRMounts
{
void Init()
{
    CVAR_REGISTER(&g_Mounts);
    g_engfuncs.pfnAddServerCommand((char *)"ms_mount_spawn", SpawnCommand);
    g_engfuncs.pfnAddServerCommand((char *)"ms_mount_status", StatusCommand);
    g_engfuncs.pfnAddServerCommand((char *)"ms_mount_test", LifecycleCommand);
    g_engfuncs.pfnAddServerCommand((char *)"ms_mount_place", PlaceCommand);
    g_engfuncs.pfnAddServerCommand((char *)"ms_stable_test", StableTestCommand);
}
void Precache()
{
    // A missing optional asset must never abort a legacy map's load.
    int length = 0;
    byte *file = LOAD_FILE_FOR_ME((char *)kHorseModel, &length);
    if (file)
    {
        FREE_FILE(file);
        g_PrecachedHorseIndex = PRECACHE_MODEL(kHorseModel);
        ALERT(at_console, "MSR mounts: precached %s (%d bytes), model index=%d.\n",
            kHorseModel, length, g_PrecachedHorseIndex);
    }
    else
        ALERT(at_console, "MSR mounts: optional asset %s was not found through the game filesystem.\n", kHorseModel);
}
void ApplyRestrictions(CBasePlayer *player)
{
    if (!player) return;
    CMSRHorse *horse = MountedHorse(player);
    if (!horse || horse->GetRider() != player) return;
    // The server-owned link is authoritative even if an ordinary script rebuilt
    // the player's movement status during the frame.
    SetBits(player->m_StatusFlags, PLAYER_MOVE_MOUNTED | kRestrictions);
    ClearBits(player->pbs.ButtonsDown, kBlockedButtons);
    ClearBits(player->m_afButtonPressed, kBlockedButtons);
    ClearBits(player->pev->button, kBlockedButtons);
    player->pev->view_ofs = Vector(0, 0, MSRMountPolicy::ViewHeight);
    // Server PM receives entvars.iuser3, while client PM receives clientdata.
    // Both must carry the same mount/restriction/immobilization bits.
    player->pev->iuser3 = player->m_StatusFlags & (PLAYER_MOVE_MOUNTED | kRestrictions | PLAYER_MOVE_NOMOVE | PLAYER_MOVE_NORUN);
}
void Release(CBasePlayer *player, const char *reason)
{
    if (!player) return;
    CMSRHorse *horse = MountedHorse(player);
    if (horse && horse->GetRider() == player) horse->EndRide(true, reason, true);
    else if (FBitSet(player->m_StatusFlags, PLAYER_MOVE_MOUNTED))
    {
        player->m_hMount = (CBaseEntity *)NULL;
        ClearBits(player->m_StatusFlags, PLAYER_MOVE_MOUNTED | PLAYER_MOVE_RUNNING);
        ClearBits(player->pev->iuser3, PLAYER_MOVE_MOUNTED | kRestrictions);
        player->pev->view_ofs = Vector(0, 0, 28);
    }
    if (!strcmp(reason,"disconnect") || !strcmp(reason,"death") || !strcmp(reason,"spawn") || !strcmp(reason,"map end"))
        for (int index=gpGlobals->maxClients+1; index<gpGlobals->maxEntities; ++index)
        {
            edict_t *entity=INDEXENT(index);
            if (!entity || entity->free || !entity->pvPrivateData) continue;
            CMSRHorse *loan=Horse(CBaseEntity::Instance(entity));
            if (loan && loan->m_Assigned && loan->GetCustomer()==player)
            {
                loan->EndRide(true,reason,true);
                UTIL_Remove(loan);
            }
        }
}
void RecordCommand(CBasePlayer *player, const usercmd_s *command)
{
    CMSRHorse *horse = MountedHorse(player);
    if (!horse || horse->GetRider() != player || !command) return;
    horse->m_LastCommand = *command;
    horse->m_LastCommandTime = gpGlobals->time;
}
void PlayerPreThink(CBasePlayer *player)
{
    CMSRHorse *horse = MountedHorse(player);
    if (!horse || horse->GetRider() != player)
    {
        Release(player, "missing horse");
        return;
    }
    if (!Enabled() || !player->IsAlive() || player->m_CharacterState != CHARSTATE_LOADED ||
        player->pev->waterlevel >= 2 || player->pev->movetype != MOVETYPE_WALK)
    {
        Release(player, "mount movement ended");
        return;
    }
    ApplyRestrictions(player);
}
void PlayerPostThink(CBasePlayer *player)
{
    CMSRHorse *horse = MountedHorse(player);
    if (!horse || horse->GetRider() != player) return;
    ApplyRestrictions(player);
    horse->Follow(player);
    // Use the relaxed sitting upper body. The client overrides its root and
    // legs into a symmetric saddle pose after animation/gait interpolation.
    const int sitting = player->LookupSequence("sitdown");
    if (sitting >= 0)
    {
        player->pev->sequence = sitting;
        player->pev->frame = 255;
        player->pev->framerate = 0;
        player->pev->gaitsequence = 0;
        player->pev->animtime = gpGlobals->time;
    }
}
bool PlayerUse(CBasePlayer *player)
{
    CMSRHorse *horse = MountedHorse(player);
    if (!horse || horse->GetRider() != player) return false;
    if ((player->m_afButtonPressed & IN_USE) && gpGlobals->time >= horse->m_NextUse)
        horse->EndRide(false, "Use");
    return true;
}
void MapEnd()
{
    for (int index = 1; index <= gpGlobals->maxClients; ++index)
        Release((CBasePlayer *)UTIL_PlayerByIndex(index), "map end");
    g_PrecachedHorseIndex = 0;
}
CBasePlayer *Rider(CBaseEntity *entity)
{
    CMSRHorse *horse = Horse(entity);
    return horse ? horse->GetRider() : NULL;
}
bool HasRider(CBaseEntity *entity) { return Rider(entity) != NULL; }
} // namespace MSRMounts
