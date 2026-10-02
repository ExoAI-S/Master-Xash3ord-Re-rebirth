// Included once by msmapents.cpp after CAreaMonsterSpawn is defined.
// Opt-in adapter; no persistent player/FN state and no legacy actor registration.
namespace MSREncounters
{
namespace
{
namespace P = MSREncounterPolicy;
constexpr std::size_t MaxLedger = P::MaxControllers * P::MaxSlots;
struct Template
{
    EHANDLE handle{};
    P::Descriptor bounds;
    bool width = false, height = false, bad = false;
};
struct Ledger
{
    std::string controller, name, script, classname;
    int region = REGION_NONE, lives = -1, left = -1;
    P::Vec3 pad, angles;
    P::Descriptor descriptor;
    double death = 0, delay = 0, retry = 0;
    bool suspended = false;
};
struct Controller
{
    bool used = false;
    EHANDLE handle{};
    P::ControllerKey key;
};
struct Child
{
    bool used = false, touched = false, credit = false, uncertain = false;
    bool retiring = false, hasActivity = false, deathSeen = false, deathNotified = false;
    EHANDLE actor{}, owner{};
    P::ControllerKey actorKey, ownerKey;
    long actorAddress = 0; // Comparison only; never dereferenced after removal.
    P::Ticket ticket;
    int slot = -1, ledger = -1, region = REGION_NONE;
    P::Config config;
    P::Descriptor descriptor;
    double born = 0, lastActivity = 0, touchedTime = -1, creditTime = -1;
    P::IdleState idle;
    P::RetentionReason hold = P::RetentionReason::InvalidObservation;
};
struct Event
{
    std::uint64_t sequence = 0, frame = 0, generation = 0;
    double time = 0;
    const char* kind = "none";
    P::ControllerKey owner, actor;
    int slot = -1, detail = 0;
};
std::array<Template, MaxLedger> templates{};
std::array<Controller, P::MaxControllers> controllers{};
std::array<Child, P::MaxActors> children{};
std::array<Child, P::MaxActors> deadObservers{}; // No charge; serial-valid corpse telemetry only.
std::unordered_map<const void*, std::pair<EHANDLE, P::ControllerKey>> liveItems;
std::array<EHANDLE, P::InitialScripts.size()> probes{};
std::array<Event, 512> events{};
std::vector<Ledger> ledger;
P::AdmissionBudget budget;
cvar_t capCvar = {"ms_encounter_max_active", "16", FCVAR_SERVER};
cvar_t intervalCvar = {"ms_encounter_spawn_interval", "0.2", FCVAR_SERVER};
bool enabled = false, requested = false, insideFrame = false;
std::uint64_t generation = 0, frames = 0, eventSequence = 0;
std::uint64_t attempts = 0, births = 0, deaths = 0, deathNotices = 0;
std::uint64_t retireAttempts = 0, retired = 0, aborts = 0, gearRemoved = 0;
std::uint64_t missing = 0, spawnFailed = 0, descriptorFailed = 0, refused = 0;
std::uint64_t acceptedDamage = 0, acceptedCredit = 0, attacks = 0, frameGateWait = 0;
std::uint64_t xpDispatches = 0, predeathDispatches = 0, deathDispatches = 0, dropAllCalls = 0, observerOverflow = 0;
double frameMsTotal = 0, frameMsMax = 0;
P::Admission lastAdmission;

P::Vec3 Position(const Vector& v) { return {v.x, v.y, v.z}; }
P::ControllerKey Key(CBaseEntity* entity)
{
    return entity && entity->edict() ? P::ControllerKey{
        static_cast<std::uint32_t>(entity->entindex()),
        static_cast<std::uint32_t>(entity->edict()->serialnumber)} : P::ControllerKey{};
}
CBaseEntity* Resolve(EHANDLE& handle, P::ControllerKey key)
{
    edict_t* ent = handle.Get();
    if (!ent || ent->free || !ent->pvPrivateData ||
        ENTINDEX(ent) != static_cast<int>(key.index) ||
        static_cast<std::uint32_t>(ent->serialnumber) != key.serial) return nullptr;
    return CBaseEntity::Instance(ent);
}
CAreaMonsterSpawn* Owner(Child& child)
{
    CBaseEntity* entity = Resolve(child.owner, child.ownerKey);
    if (!entity || (!FClassnameIs(entity->pev, "msarea_monsterspawn") &&
        !FClassnameIs(entity->pev, "ms_monsterspawn"))) return nullptr;
    auto* controller = static_cast<CAreaMonsterSpawn*>(entity);
    return controller->m_EncounterRegistered && child.slot >= 0 &&
        child.slot < static_cast<int>(controller->iMonstersToSpawn) &&
        controller->m_EncounterLedger[child.slot] == child.ledger ? controller : nullptr;
}
CMSMonster* Actor(Child& child)
{
    CBaseEntity* entity = Resolve(child.actor, child.actorKey);
    return entity && reinterpret_cast<long>(entity) == child.actorAddress &&
        entity->IsMSMonster() && !entity->IsPlayer() ?
        static_cast<CMSMonster*>(entity) : nullptr;
}
bool SameTicket(const P::Ticket& a, const P::Ticket& b)
{
    return a.epoch == b.epoch && a.sequence == b.sequence && a.cell == b.cell;
}
bool Current(int cell, P::Ticket ticket, std::uint64_t map)
{
    return enabled && generation == map && cell >= 0 && cell < P::MaxActors &&
        children[cell].used && SameTicket(children[cell].ticket, ticket);
}
Child* Find(CMSMonster* actor)
{
    if (!enabled || !actor) return nullptr;
    for (auto& child : children)
        if (child.used && Actor(child) == actor) return &child;
    return nullptr;
}
void Record(const char* kind, const Child* child = nullptr, int detail = 0)
{
    Event& event = events[eventSequence % events.size()];
    event = Event{};
    event.sequence = ++eventSequence; event.frame = frames; event.generation = generation;
    event.time = gpGlobals->time; event.kind = kind; event.detail = detail;
    if (child) { event.owner = child->ownerKey; event.actor = child->actorKey; event.slot = child->slot; }
}
std::vector<P::Player> Players()
{
    std::vector<P::Player> result;
    result.reserve(gpGlobals->maxClients);
    for (int i = 1; i <= gpGlobals->maxClients; ++i)
    {
        CBaseEntity* entity = UTIL_PlayerByIndex(i);
        if (!entity || !entity->IsPlayer()) continue;
        auto* player = static_cast<CBasePlayer*>(entity);
        P::Player observation;
        observation.connected = UTIL_IsConnectedPlayer(player);
        observation.loaded = player->m_CharacterState == CHARSTATE_LOADED;
        // Character-loaded precedes Spawn. The normal gameplay movement/solid
        // state excludes selection ghosts; mounted/AFK players remain eligible.
        observation.placed = player->pev->movetype == MOVETYPE_WALK &&
            player->pev->solid != SOLID_NOT && !FBitSet(player->pev->flags, FL_SPECTATOR);
        observation.alive = player->IsAlive() && player->pev->deadflag == DEAD_NO;
        observation.position = Position(player->pev->origin);
        result.push_back(observation);
    }
    return result;
}
P::Presence Presence(CAreaMonsterSpawn* owner, const std::vector<P::Player>& players,
    const P::Vec3* actor = nullptr)
{
    std::array<P::Vec3, P::MaxSlots> pads{};
    for (unsigned int i = 0; i < owner->iMonstersToSpawn && i < pads.size(); ++i)
        pads[i] = Position(owner->mdSpawnMonster[i].origin);
    return P::Observe(owner->m_EncounterConfig, players.data(), players.size(),
        pads.data(), owner->iMonstersToSpawn, actor);
}
bool Shape(CMSMonster* actor, const Ledger& logical)
{
    return actor && actor->m_ScriptName == logical.script.c_str() &&
        FClassnameIs(actor->pev, logical.classname.c_str()) &&
        actor->pev->solid == SOLID_BBOX && actor->pev->movetype == MOVETYPE_STEP &&
        (actor->pev->flags & (FL_MONSTER | FL_MONSTERCLIP)) == (FL_MONSTER | FL_MONSTERCLIP) &&
        P::ActorBoundsMatch(logical.script.c_str(), logical.descriptor,
            {actor->m_Width, actor->m_Height},
            {Position(actor->pev->mins), Position(actor->pev->maxs)}, Position(actor->pev->origin));
}
bool SimpleGear(CMSMonster* actor)
{
    // Containers and wearables need a separate transactional adapter. Hold them
    // conservatively rather than recursively removing callback-mutated contents.
    if (actor->Gear.size() > 64) return false;
    for (unsigned int i = 0; i < actor->Gear.size(); ++i)
    {
        const auto found = liveItems.find(actor->Gear[i]);
        if (found == liveItems.end()) return false;
        CBaseEntity* entity = Resolve(found->second.first, found->second.second);
        if (!entity || entity != found->first || !entity->IsMSItem()) return false;
        auto* item = static_cast<CGenericItem*>(entity);
        if (item->m_pOwner != actor ||
            item->m_pPlayer || item->m_pParentContainer || item->PackData || item->ArmorData ||
            item->m_WearPositions.size() || item->CurrentAttack) return false;
    }
    return true;
}
P::ActorFacts Facts(Child& child)
{
    P::ActorFacts facts;
    CMSMonster* actor = Actor(child);
    CAreaMonsterSpawn* owner = Owner(child);
    if (!actor || child.ledger < 0 || child.ledger >= static_cast<int>(ledger.size())) return facts;
    const Ledger& logical = ledger[child.ledger];
    facts.exactOwned = owner && (child.retiring ?
        (actor->pev->owner == nullptr && !owner->mdSpawnMonster[child.slot].spawned &&
            owner->mdSpawnMonster[child.slot].lPrivData == 0) :
        (actor->pev->owner == owner->edict() && owner->mdSpawnMonster[child.slot].spawned &&
            owner->mdSpawnMonster[child.slot].lPrivData == reinterpret_cast<long>(actor)));
    facts.alive = actor->IsAlive() && actor->pev->deadflag == DEAD_NO;
    facts.ordinaryAmbient = !child.uncertain && Shape(actor, logical) && SimpleGear(actor);
    facts.infiniteLife = logical.lives == -1;
    // Do not resolve orphaned script strings to arbitrary pointers. Presence of
    // ownership declarations is sufficient protection, even after disconnection.
    facts.playerOwned = actor->m_iRegionMaster > 0 || actor->RetrieveEntity(ENT_OWNER) ||
        actor->RetrieveEntity(ENT_EXPOWNER) || actor->RetrieveEntity(ENT_CREATIONOWNER);
    for (const char* name : {"SUMMON_MASTER", "MY_OWNER"})
    {
        const char* value = actor->GetFirstScriptVar(name);
        if (value && *value && !FStrEq(value, name) && !FStrEq(value, "0") && !FStrEq(value, "none"))
            facts.playerOwned = true;
    }
    facts.horse = FClassnameIs(actor->pev, "ms_horse") || MSRMounts::HasRider(actor);
    facts.storeOrMenu = actor->OpenStore || actor->m_Menu_Autoopen || actor->m_MenuCurrentOptions ||
        actor->HasConditions(MONSTER_TRADING) || actor->HasConditions(MONSTER_OPENCONTAINER);
    for (unsigned int i = 0; i < MAXPLAYERS; ++i)
        if (actor->m_MenuOptionsProtected[i] || actor->m_MenuOptions[i].size()) facts.storeOrMenu = true;
    facts.boss = actor->m_BossId.len() != 0 || actor->m_BossOpen.len() != 0;
    facts.quest = actor->m_iszKillTarget.len() != 0 || actor->m_iszPerishTarget.len() != 0 || actor->pev->target;
    facts.combatTouched = child.touched; facts.rewardCredit = child.credit;
    // Inspect only numeric reward counters. Identity strings are neither read nor logged.
    for (unsigned int i = 0; i < actor->m_PlayerDamage.size(); ++i)
    {
        const auto& damage = actor->m_PlayerDamage[i];
        if (!std::isfinite(damage.dmgInTotal) || damage.dmgInTotal != 0) facts.rewardCredit = true;
        for (int stat = 0; stat < SKILL_MAX_ATTACK; ++stat)
            for (int prop = 0; prop < STAT_PROP_ALL_TOTAL; ++prop)
                if (!std::isfinite(damage.dmg[stat][prop]) || damage.dmg[stat][prop] != 0)
                    facts.rewardCredit = true;
    }
    facts.observedAttack = FBitSet(actor->m_StatusFlags, PLAYER_MOVE_ATTACKING) != 0;
    edict_t* referenceEdict = actor->m_hEnemy.Get();
    CBaseEntity* reference = referenceEdict && !referenceEdict->free && referenceEdict->pvPrivateData ?
        CBaseEntity::Instance(referenceEdict) : nullptr;
    if (reference && reference->edict() && !reference->edict()->free && reference->IsAlive())
    {
        facts.conservativeReferenceHold = true;
        facts.nonWanderingChase = actor->HasConditions(MONSTER_HASMOVEDEST) && !actor->m_Wandering &&
            actor->IRelationship(reference) <= -3; // DISLIKE/HATE/NEMESIS; friendly follower is a separate hold.
    }
    // Nonwandering script destinations cannot be discarded merely to free capacity.
    if (actor->HasConditions(MONSTER_HASMOVEDEST) && !actor->m_Wandering)
        facts.conservativeReferenceHold = true;
    facts.hasActivity = child.hasActivity; facts.lastActivity = child.lastActivity;
    facts.health = actor->m_HP; facts.maxHealth = actor->MaxHP();
    return facts;
}
bool WorldClear(CBaseEntity* query, const Vector& at, edict_t* ignore)
{
    if (!query || !query->edict() || query->edict()->free) return false;
    TraceResult trace{};
    // Engine selects hull0/1/2/3 and clip offset using this real edict's
    // actual mins/maxs. A stack fake-edict or generic human hull is unsuitable.
    // Include ordinary monsters and every other linked solid too. The explicit
    // player/horse boxes supplement this trace, particularly SOLID_NOT horses.
    TRACE_MONSTER_HULL(query->edict(), at, at, dont_ignore_monsters, ignore, &trace);
    return !trace.fStartSolid && !trace.fAllSolid && std::isfinite(trace.flFraction) && trace.flFraction == 1;
}
P::PadReason Occupied(const P::Bounds& selected, edict_t* ignore = nullptr)
{
    std::array<P::Occupant, MAXPLAYERS> players{};
    std::vector<P::Occupant> mounts;
    bool invalid = false;
    for (int i = 1; i < gpGlobals->maxEntities; ++i)
    {
        edict_t* ent = INDEXENT(i);
        if (!ent || ent == ignore || ent->free || !ent->pvPrivateData) continue;
        CBaseEntity* entity = CBaseEntity::Instance(ent);
        if (!entity) continue;
        const bool horse = FClassnameIs(ent, "ms_horse");
        const bool player = entity->IsPlayer() && i <= gpGlobals->maxClients;
        if (!horse && !player) continue;
        if (player && (!UTIL_IsConnectedPlayer(static_cast<CBasePlayer*>(entity)) ||
            ent->v.solid == SOLID_NOT)) continue;
        P::Bounds actual;
        const auto origin = Position(ent->v.origin);
        const auto min = Position(ent->v.mins), max = Position(ent->v.maxs);
        actual.min = {origin.x + min.x, origin.y + min.y, origin.z + min.z};
        actual.max = {origin.x + max.x, origin.y + max.y, origin.z + max.z};
        if (!P::ValidBounds(actual)) invalid = true;
        if (horse) mounts.push_back({true, actual}); // Includes SOLID_NOT unridden horses.
        else if (i <= static_cast<int>(players.size())) players[i - 1] = {true, actual};
        else invalid = true;
    }
    return invalid ? P::PadReason::InvalidObservation :
        P::CheckOccupants(selected, players.data(), players.size(), mounts.data(), mounts.size());
}
int AllocatorReady()
{
    // INDEXENT(i) hides free entries. The engine's world edict is the base of
    // the same contiguous maxEntities array already used by MSRegions.
    return MSREncounterAllocator::ReadyCount(INDEXENT(0), gpGlobals->maxClients,
        gpGlobals->maxEntities, gpGlobals->time);
}
bool EnsureProbes()
{
    for (std::size_t i = 0; i < probes.size(); ++i)
    {
        edict_t* existing = probes[i].Get();
        if (existing && !existing->free && existing->pvPrivateData) continue;
        if (AllocatorReady() - 1 - budget.Inflight() < P::EdictReserve)
            return false;
        CBaseEntity* probe = CREATE_ENT("info_target");
        if (!probe) return false;
        probes[i] = probe;
        probe->pev->solid = SOLID_NOT; probe->pev->movetype = MOVETYPE_NONE;
        probe->pev->effects = EF_NODRAW; probe->pev->flags = FL_MONSTER | FL_MONSTERCLIP;
        probe->pev->nextthink = 0; probe->SetThink(nullptr);
        const auto d = P::InitialScripts[i].bounds;
        UTIL_SetSize(probe->pev, Vector(-d.width / 2, -d.width / 2, 0),
            Vector(d.width / 2, d.width / 2, d.height));
    }
    return true;
}
P::PadReason Gate(P::ControllerKey key, int slot, void*)
{
    // No entity allocation, script callback or budget mutation in this gate.
    CAreaMonsterSpawn* owner = nullptr;
    for (auto& controller : controllers)
        if (controller.used && controller.key == key)
            owner = static_cast<CAreaMonsterSpawn*>(Resolve(controller.handle, key));
    if (!owner || slot < 0 || slot >= static_cast<int>(owner->iMonstersToSpawn))
        return P::PadReason::InvalidObservation;
    const auto& md = owner->mdSpawnMonster[slot];
    const P::Vec3 pad = Position(md.origin);
    const auto players = Players(); // Fresh positions at the selected candidate.
    const auto presence = P::Observe(owner->m_EncounterConfig, players.data(), players.size(), &pad, 1);
    P::Bounds bounds;
    if (!P::ExpectedBounds(owner->m_EncounterDescriptors[slot], pad, bounds))
        return P::PadReason::InvalidObservation;
    CBaseEntity* probe = nullptr;
    for (std::size_t i = 0; i < P::InitialScripts.size(); ++i)
        if (FStrEq(STRING(md.scriptfile), P::InitialScripts[i].name))
            probe = probes[i];
    const auto occupied = Occupied(bounds);
    P::HullSafety hulls;
    hulls.valid = probe && occupied != P::PadReason::InvalidObservation;
    hulls.worldClear = WorldClear(probe, md.origin, probe ? probe->edict() : nullptr);
    hulls.playersClear = occupied != P::PadReason::PlayerHull;
    hulls.mountsClear = occupied != P::PadReason::MountHull;
    return P::SelectedPadDecision(owner->m_EncounterConfig, presence, hulls);
}
void Store(CAreaMonsterSpawn* owner, int slot)
{
    const int index = owner->m_EncounterLedger[slot];
    if (index < 0 || index >= static_cast<int>(ledger.size())) return;
    auto& logical = ledger[index];
    const auto& md = owner->mdSpawnMonster[slot];
    logical.left = md.livesleft; logical.death = md.deathtime; logical.delay = md.delayvalue;
}
void Release(int cell, const char* kind, bool suspended)
{
    Child& child = children[cell];
    if (!child.used) return;
    Record(kind, &child);
    if (CAreaMonsterSpawn* owner = Owner(child))
    {
        auto& md = owner->mdSpawnMonster[child.slot];
        // Never clear a callback-authored new incarnation.
        if (md.lPrivData == child.actorAddress || md.lPrivData == 0)
        { md.spawned = false; md.lPrivData = 0; Store(owner, child.slot); }
        else owner->m_EncounterBad = true;
    }
    if (child.ledger >= 0 && child.ledger < static_cast<int>(ledger.size()))
    {
        ledger[child.ledger].suspended = suspended;
        ledger[child.ledger].retry = gpGlobals->time + 0.2;
    }
    if (!budget.Release(child.ticket)) { child.uncertain = true; Record("release_rejected", &child); return; }
    child = Child{};
}
bool ValidateRetirement(int cell, P::Ticket ticket, std::uint64_t map)
{
    if (!Current(cell, ticket, map)) return false;
    Child& child = children[cell];
    CMSMonster* actor = Actor(child);
    CAreaMonsterSpawn* owner = Owner(child);
    if (!actor || !owner || !child.retiring) return false;
    const auto players = Players();
    const auto position = Position(actor->pev->origin);
    auto idle = child.idle;
    return P::Retirement(child.config, gpGlobals->time, Presence(owner, players, &position),
        Facts(child), idle) == P::RetentionReason::RetirePristine;
}
void Retire(int cell)
{
    Child& child = children[cell];
    CMSMonster* actor = Actor(child);
    CAreaMonsterSpawn* owner = Owner(child);
    if (!actor || !owner || !SimpleGear(actor)) return;
    const auto ticket = child.ticket; const auto map = generation;
    std::vector<std::pair<EHANDLE, P::ControllerKey>> carried;
    for (unsigned int i = 0; i < actor->Gear.size(); ++i)
    {
        EHANDLE handle{}; handle = actor->Gear[i];
        carried.push_back({handle, Key(actor->Gear[i])});
    }
    ++retireAttempts; Record("retire_attempt", &child);
    child.retiring = true;
    actor->pev->owner = nullptr;
    owner->mdSpawnMonster[child.slot].spawned = false;
    owner->mdSpawnMonster[child.slot].lPrivData = 0;
    // Charge and hook membership stay armed while physical ownership is detached.
    for (auto& itemIdentity : carried)
    {
        if (!ValidateRetirement(cell, ticket, map)) break;
        CBaseEntity* entity = Resolve(itemIdentity.first, itemIdentity.second);
        if (!entity || !entity->IsMSItem()) { children[cell].uncertain = true; break; }
        auto* item = static_cast<CGenericItem*>(entity);
        actor = Actor(children[cell]);
        if (!actor || item->m_pOwner != actor || item->m_pParentContainer || item->PackData ||
            item->m_pPlayer || item->ArmorData || item->m_WearPositions.size() || item->CurrentAttack)
        { children[cell].uncertain = true; break; }
        // Split the stock removal callbacks from physical cleanup so every
        // callback gets serial/generation/protection/ownership revalidation.
        item->CallScriptEvent("game_removefromowner");
        if (!ValidateRetirement(cell, ticket, map)) break;
        entity = Resolve(itemIdentity.first, itemIdentity.second);
        actor = Actor(children[cell]);
        if (!entity || !entity->IsMSItem()) { children[cell].uncertain = true; break; }
        item = static_cast<CGenericItem*>(entity);
        if (item->m_pOwner != actor || item->m_pParentContainer || item->PackData || item->CurrentAttack)
        { children[cell].uncertain = true; break; }
        actor->Gear.RemoveItem(item);
        item->m_pOwner = nullptr; item->m_pPlayer = nullptr; item->Wielded = false;
        ClearBits(item->pev->flags, FL_SKIPLOCALHOST);
        item->CallScriptEvent("game_deleted");
        if (!ValidateRetirement(cell, ticket, map)) break;
        entity = Resolve(itemIdentity.first, itemIdentity.second);
        if (!entity || !entity->IsMSItem()) { children[cell].uncertain = true; break; }
        item = static_cast<CGenericItem*>(entity);
        if (item->m_pOwner || item->m_pParentContainer || item->PackData || item->CurrentAttack)
        { children[cell].uncertain = true; break; }
        edict_t* ent = item->edict();
        item->UpdateOnRemove(); item->Deactivate(); REMOVE_ENTITY(ent);
        ++gearRemoved;
    }
    if (!Current(cell, ticket, map)) return; // Callback reset the map or ordinary death released the charge.
    actor = Actor(children[cell]); owner = Owner(children[cell]);
    if (!actor) { ++missing; Release(cell, "retire_callback_missing", false); return; }
    if (!ValidateRetirement(cell, ticket, map) || actor->Gear.size() != 0)
    {
        ++aborts; children[cell].uncertain = true; Record("retire_abort_partial_gear", &children[cell]);
        // Restore only the exact association left by this transaction. Preserve
        // callback-authored owners/slots; an inconsistency stays charged/protected.
        if (owner && actor->pev->owner == nullptr && !owner->mdSpawnMonster[children[cell].slot].spawned &&
            owner->mdSpawnMonster[children[cell].slot].lPrivData == 0)
        {
            actor->pev->owner = owner->edict();
            owner->mdSpawnMonster[children[cell].slot].spawned = true;
            owner->mdSpawnMonster[children[cell].slot].lPrivData = reinterpret_cast<long>(actor);
        }
        children[cell].retiring = false; return;
    }
    edict_t* ent = actor->edict();
    // Region-style nondeath cleanup: no SUB_Remove/game_deleted, Killed,
    // DeathNotice, game_death/predeath, XP, drops or target dispatch for the actor.
    actor->UpdateOnRemove(); actor->Deactivate(); REMOVE_ENTITY(ent);
    if (!Current(cell, ticket, map)) return;
    if (Actor(children[cell]))
    { ++aborts; children[cell].uncertain = true; Record("retire_remove_unconfirmed", &children[cell]); return; }
    ++retired; Release(cell, "retired_pristine", true);
}
void Birth(const P::Admission& admission)
{
    CAreaMonsterSpawn* owner = nullptr;
    for (auto& controller : controllers)
        if (controller.used && controller.key == admission.controller)
            owner = static_cast<CAreaMonsterSpawn*>(Resolve(controller.handle, controller.key));
    if (!owner || admission.slot < 0 || admission.slot >= static_cast<int>(owner->iMonstersToSpawn))
    { budget.Release(admission.ticket); ++spawnFailed; Record("birth_owner_missing"); return; }
    const int slot = admission.slot, index = owner->m_EncounterLedger[slot];
    // Reserve includes this pending primary. Recheck actual allocator-ready
    // capacity immediately before birth, rather than counting recently freed
    // holes as reusable. No scripts or allocations intervene before CREATE.
    const int readyEdicts = AllocatorReady();
    if (readyEdicts - budget.Inflight() < P::EdictReserve)
    {
        budget.Release(admission.ticket);
        lastAdmission.reason = P::AdmissionReason::EdictMargin;
        Record("birth_allocator_wait", nullptr, readyEdicts); return;
    }
    // The read-only availability check precedes Reserve; no callbacks intervened.
    if (owner->Region() != REGION_NONE && !MSRegions::TakeSpawnSlot())
    { budget.Release(admission.ticket); ++frameGateWait; Record("frame_gate_race"); return; }
    ++attempts;
    auto& md = owner->mdSpawnMonster[slot];
    CBaseEntity* created = CREATE_ENT(STRING(md.classname));
    if (!created || !created->IsMSMonster() || created->IsPlayer())
    { budget.Release(admission.ticket); ++spawnFailed; Record("create_failed"); return; }
    auto* actor = static_cast<CMSMonster*>(created);
    const int cell = admission.ticket.cell;
    Child& child = children[cell]; child = Child{};
    child.used = true; child.actor = actor; child.owner = owner;
    child.actorKey = Key(actor); child.ownerKey = Key(owner); child.ticket = admission.ticket;
    child.actorAddress = reinterpret_cast<long>(actor);
    child.slot = slot; child.ledger = index; child.region = owner->Region();
    child.config = owner->m_EncounterConfig; child.descriptor = owner->m_EncounterDescriptors[slot];
    child.born = gpGlobals->time;
    const auto map = generation;
    actor->m_title = STRING(md.title); actor->m_addparams = STRING(md.addparams);
    actor->m_spawnedby = EntToString(owner);
    actor->m_DMGMulti = md.dmgmulti; actor->m_HPMulti = md.hpmulti;
    actor->pev->target = md.target; actor->pev->targetname = md.targetname;
    actor->m_iszKillTarget = STRING(md.killtarget); actor->m_iszPerishTarget = STRING(md.perishtarget);
    actor->m_ScriptName = STRING(md.scriptfile); actor->pev->owner = owner->edict();
    actor->pev->origin = md.origin; actor->pev->angles = md.angles;
    md.lPrivData = reinterpret_cast<long>(actor); md.spawned = true; md.triggered = false;
    if (md.lives > 0 && md.livesleft > 0) --md.livesleft;
    Store(owner, slot); ledger[index].suspended = false;
    UTIL_SetOrigin(actor->pev, actor->pev->origin);
    const int home = MSRegions::At(actor->pev->origin);
    actor->m_iHomeRegion = home != REGION_NONE ? home : child.region;
    Record("birth_attempt", &child);
    // Membership exists before scripts so early damage/credit/death is observed.
    actor->Spawn();
    if (!Current(cell, admission.ticket, map)) return;
    actor = Actor(children[cell]); owner = Owner(children[cell]);
    if (!actor)
    {
        // A removed failed Spawn without a genuine death refunds its finite life.
        if (owner && !children[cell].deathSeen && owner->mdSpawnMonster[slot].lives > 0)
            ++owner->mdSpawnMonster[slot].livesleft;
        ++spawnFailed; Release(cell, "spawn_removed", false); return;
    }
    if (children[cell].deathNotified && !actor->IsAlive())
    { Release(cell, "ordinary_death_during_spawn", false); return; }
    budget.Commit(admission.ticket); ++births; Record("born", &children[cell]);
    P::Bounds bounds;
    const auto actualPosition = Position(actor->pev->origin);
    const auto freshPlayers = Players(); // Scripts can move actors or players.
    const auto actualPresence = P::Observe(children[cell].config,
        freshPlayers.data(), freshPlayers.size(), &actualPosition, 1);
    P::PadReason postPadReason = P::PadReason::Allowed;
    if (!Shape(actor, ledger[index]) || !actualPresence.valid ||
        !P::ExpectedBounds(children[cell].descriptor, actualPosition, bounds))
        postPadReason = P::PadReason::InvalidObservation;
    else if (actualPresence.eligiblePlayers && actualPresence.minPadDistanceSquared <=
        children[cell].config.minDistance * children[cell].config.minDistance)
        postPadReason = P::PadReason::TooClose;
    else if (!WorldClear(actor, actor->pev->origin, actor->edict()))
        postPadReason = P::PadReason::WorldHull;
    else postPadReason = Occupied(bounds, actor->edict());
    // A disconnect/death during Spawn leaves a geometrically valid actor
    // charged, eligible for the ordinary later idle retirement checks.
    const bool geometry = postPadReason == P::PadReason::Allowed;
    if (!owner || actor->pev->owner != owner->edict() || !geometry)
    {
        ++descriptorFailed; children[cell].uncertain = true;
        if (owner) owner->m_EncounterBad = true;
        Record("postspawn_mismatch_live_charged", &children[cell], static_cast<int>(postPadReason));
    }
}
void Report()
{
    const auto players = Players();
    double cap = 0, interval = 0.2;
    P::ParseNumber(capCvar.string, cap); P::ParseNumber(intervalCvar.string, interval);
    const auto limits = P::RuntimeLimits(cap, interval);
    ALERT(at_console, "MS_ENCOUNTERS {\"type\":\"summary\",\"generation\":%llu,\"frame\":%llu,\"time\":%.9g,\"event_highwater\":%llu,\"cap\":%d,\"interval\":%.9g,\"live\":%d,\"inflight\":%d,\"ledger\":%u,\"edicts\":%d,\"free_edicts\":%d,\"allocator_ready_lower_bound\":%d,\"allocator_highwater\":null,\"attempts\":%llu,\"births\":%llu,\"ordinary_deaths\":%llu,\"death_notices\":%llu,\"accepted_damage\":%llu,\"accepted_credit\":%llu,\"attacks\":%llu,\"retire_attempts\":%llu,\"retired\":%llu,\"retire_aborts\":%llu,\"gear_removed\":%llu,\"missing\":%llu,\"spawn_failed\":%llu,\"descriptor_failed\":%llu,\"refused\":%llu,\"frame_gate_wait\":%llu,\"admission_reason\":%d,\"pad_reason\":%d,\"frame_ms_total\":%.9g,\"frame_ms_max\":%.9g,\"resource_model_count\":null,\"resource_sound_count\":null,\"native_acceptance\":false}\n",
        generation, frames, gpGlobals->time, eventSequence, limits.globalCap, limits.interval,
        budget.Live(), budget.Inflight(), static_cast<unsigned int>(ledger.size()), NUMBER_OF_ENTITIES(),
        gpGlobals->maxEntities - NUMBER_OF_ENTITIES(), AllocatorReady(), attempts, births, deaths, deathNotices,
        acceptedDamage, acceptedCredit, attacks, retireAttempts, retired, aborts, gearRemoved,
        missing, spawnFailed, descriptorFailed, refused, frameGateWait,
        static_cast<int>(lastAdmission.reason), static_cast<int>(lastAdmission.padReason), frameMsTotal, frameMsMax);
    ALERT(at_console, "MS_ENCOUNTERS {\"type\":\"lifecycle_coverage\",\"native_xp_dispatches\":%llu,\"predeath_dispatches\":%llu,\"death_dispatches\":%llu,\"drop_all_calls\":%llu,\"observer_overflow\":%llu,\"script_direct_xp_coverage\":false,\"actual_dropped_item_count\":null}\n",
        xpDispatches, predeathDispatches, deathDispatches, dropAllCalls, observerOverflow);
    for (auto& controller : controllers)
    {
        if (!controller.used) continue;
        auto* owner = static_cast<CAreaMonsterSpawn*>(Resolve(controller.handle, controller.key));
        if (!owner) continue;
        const auto presence = Presence(owner, players);
        ALERT(at_console, "MS_ENCOUNTERS {\"type\":\"controller\",\"index\":%u,\"serial\":%u,\"region\":%d,\"active\":%d,\"bad\":%d,\"slots\":%u,\"local_cap\":%d,\"charged\":%d,\"eligible_players\":%u,\"pad_distance_squared\":%.9g}\n",
            controller.key.index, controller.key.serial, owner->Region(), owner->m_EncounterActive,
            owner->m_EncounterBad, owner->iMonstersToSpawn, owner->m_EncounterConfig.localCap,
            budget.LocalCharged(controller.key), static_cast<unsigned int>(presence.eligiblePlayers),
            std::isfinite(presence.minPadDistanceSquared) ? presence.minPadDistanceSquared : -1);
        for (unsigned int slot = 0; slot < owner->iMonstersToSpawn; ++slot)
        {
            const auto& md = owner->mdSpawnMonster[slot];
            const int index = owner->m_EncounterLedger[slot];
            const bool suspended = index >= 0 && ledger[index].suspended;
            const auto pad = Position(md.origin);
            const auto selected = P::Observe(owner->m_EncounterConfig, players.data(), players.size(), &pad, 1);
            ALERT(at_console, "MS_ENCOUNTERS {\"type\":\"slot\",\"owner_index\":%u,\"owner_serial\":%u,\"slot\":%u,\"ledger\":%d,\"spawned\":%d,\"lives\":%d,\"lives_left\":%d,\"death_time\":%.9g,\"delay\":%.9g,\"deadline\":%.9g,\"suspended\":%d,\"pad_distance_squared\":%.9g,\"pad_reason\":%d}\n",
                controller.key.index, controller.key.serial, slot, index, md.spawned, md.lives, md.livesleft,
                md.deathtime, md.delayvalue, static_cast<double>(md.deathtime) + md.delayvalue, suspended,
                std::isfinite(selected.minPadDistanceSquared) ? selected.minPadDistanceSquared : -1,
                static_cast<int>(Gate(controller.key, slot, nullptr)));
        }
    }
    for (auto& child : children)
    {
        if (!child.used) continue;
        CMSMonster* actor = Actor(child); CAreaMonsterSpawn* owner = Owner(child);
        P::Presence presence;
        if (actor && owner) { const auto at = Position(actor->pev->origin); presence = Presence(owner, players, &at); }
        ALERT(at_console, "MS_ENCOUNTERS {\"type\":\"actor\",\"index\":%u,\"serial\":%u,\"owner_index\":%u,\"owner_serial\":%u,\"slot\":%d,\"region\":%d,\"alive_identity\":%d,\"touched\":%d,\"credit\":%d,\"uncertain\":%d,\"retiring\":%d,\"hold\":%d,\"age\":%.9g,\"far_since\":%.9g,\"actor_distance_squared\":%.9g,\"pins_owner_region\":true}\n",
            child.actorKey.index, child.actorKey.serial, child.ownerKey.index, child.ownerKey.serial,
            child.slot, child.region, actor != nullptr, child.touched, child.credit, child.uncertain,
            child.retiring, static_cast<int>(child.hold), gpGlobals->time - child.born,
            child.idle.timing ? child.idle.farSince : -1,
            std::isfinite(presence.minActorDistanceSquared) ? presence.minActorDistanceSquared : -1);
        edict_t* reference = actor ? actor->m_hEnemy.Get() : nullptr;
        if (reference && (reference->free || !reference->pvPrivateData)) reference = nullptr;
        ALERT(at_console, "MS_ENCOUNTERS {\"type\":\"actor_activity\",\"index\":%u,\"serial\":%u,\"touched_time\":%.9g,\"credit_time\":%.9g,\"last_attack_time\":%.9g,\"reference_index\":%d,\"reference_serial\":%d,\"reference_alive\":%d}\n",
            child.actorKey.index, child.actorKey.serial, child.touchedTime, child.creditTime,
            child.hasActivity ? child.lastActivity : -1, reference ? ENTINDEX(reference) : 0,
            reference ? reference->serialnumber : 0,
            reference ? CBaseEntity::Instance(reference)->IsAlive() : false);
    }
    const std::uint64_t first = eventSequence > events.size() ? eventSequence - events.size() + 1 : 1;
    for (std::uint64_t seq = first; seq <= eventSequence; ++seq)
    {
        const auto& event = events[(seq - 1) % events.size()];
        ALERT(at_console, "MS_ENCOUNTERS {\"type\":\"event\",\"sequence\":%llu,\"generation\":%llu,\"frame\":%llu,\"time\":%.9g,\"event\":\"%s\",\"owner_index\":%u,\"owner_serial\":%u,\"actor_index\":%u,\"actor_serial\":%u,\"slot\":%d,\"detail\":%d}\n",
            event.sequence, event.generation, event.frame, event.time, event.kind,
            event.owner.index, event.owner.serial, event.actor.index, event.actor.serial, event.slot, event.detail);
    }
}
} // namespace

void Init()
{
    CVAR_REGISTER(&capCvar); CVAR_REGISTER(&intervalCvar);
    g_engfuncs.pfnAddServerCommand((char*)"ms_encounters", Report);
    ledger.reserve(MaxLedger);
}
void ResetMap()
{
    budget.ResetMap(); ++generation; enabled = true; requested = false; insideFrame = false;
    templates = {}; controllers = {}; children = {}; deadObservers = {}; probes = {}; events = {};
    ledger.clear(); liveItems.clear();
    frames = eventSequence = attempts = births = deaths = deathNotices = 0;
    retireAttempts = retired = aborts = gearRemoved = missing = spawnFailed = 0;
    descriptorFailed = refused = acceptedDamage = acceptedCredit = attacks = frameGateWait = 0;
    xpDispatches = predeathDispatches = deathDispatches = dropAllCalls = observerOverflow = 0;
    frameMsTotal = frameMsMax = 0; lastAdmission = {};
}
void MapEnd()
{
    enabled = false;
    for (auto& handle : probes)
    {
        edict_t* ent = handle.Get();
        if (ent && !ent->free) REMOVE_ENTITY(ent);
        handle = static_cast<CBaseEntity*>(nullptr);
    }
}
bool TemplateKeyValue(CMSMonster* actor, KeyValueData* data)
{
    const bool width = FStrEq(data->szKeyName, "encounter_width");
    const bool height = FStrEq(data->szKeyName, "encounter_height");
    if (!width && !height) return false;
    data->fHandled = true;
    Template* record = nullptr;
    for (auto& candidate : templates)
        if (candidate.handle.Get() == actor->edict()) { record = &candidate; break; }
    if (!record)
        for (auto& candidate : templates)
            if (!candidate.handle.Get()) { candidate = Template{}; candidate.handle = actor; record = &candidate; break; }
    if (!record) { ++refused; Record("template_capacity"); return true; }
    bool& seen = width ? record->width : record->height;
    if (seen) record->bad = true;
    seen = true;
    if (!P::ParseNumber(data->szValue, width ? record->bounds.width : record->bounds.height)) record->bad = true;
    return true;
}
void Request() { requested = true; }
bool ConsumeDescriptor(CMSMonster* actor, P::Descriptor& descriptor)
{
    for (auto& record : templates)
        if (record.handle.Get() == actor->edict())
        {
            const bool valid = !record.bad && record.width && record.height && P::ValidDescriptor(record.bounds);
            descriptor = record.bounds; record = Template{}; return valid;
        }
    return false;
}
void AcceptedDamage(CMSMonster* actor, double amount)
{
    if (auto* child = Find(actor))
        if (!std::isfinite(amount) || amount > 0)
        {
            if (!child->touched) child->touchedTime = gpGlobals->time;
            child->touched = true; if (!std::isfinite(amount)) child->uncertain = true;
            ++acceptedDamage; Record("accepted_hp_loss", child);
        }
}
void AcceptedCredit(CMSMonster* actor, double amount)
{
    if (auto* child = Find(actor))
        if (!std::isfinite(amount) || amount > 0)
        {
            if (!child->credit) child->creditTime = gpGlobals->time;
            child->credit = true; if (!std::isfinite(amount)) child->uncertain = true;
            ++acceptedCredit; Record("accepted_reward_credit", child);
        }
}
void InitializeStatsLedger(CMSMonster* actor)
{
    // mslist::reserve_once uses default-initialized new playerdamage_t[]. Its
    // plain numeric members have no constructor. Initialize this NEW allocation
    // before managed scripts run; never clear an existing player's credit.
    if (!Find(actor)) return;
    for (unsigned int i = 0; i < actor->m_PlayerDamage.size(); ++i) actor->m_PlayerDamage[i].Clear();
}
void ObservedAttack(CMSMonster* actor)
{
    if (auto* child = Find(actor))
    { child->hasActivity = true; child->lastActivity = gpGlobals->time; ++attacks; Record("attack_start", child); }
}
void OrdinaryDeath(CMSMonster* actor)
{
    if (auto* child = Find(actor))
    {
        if (!child->deathSeen) { child->deathSeen = true; ++deaths; Record("ordinary_killed_enter", child); }
        if (child->retiring)
        {
            // A gear callback caused a real death. Restore only our exact
            // detached association so stock Killed can send its true notice.
            CAreaMonsterSpawn* owner = Owner(*child);
            if (owner && actor->pev->owner == nullptr &&
                owner->mdSpawnMonster[child->slot].lPrivData == 0 &&
                !owner->mdSpawnMonster[child->slot].spawned)
            {
                actor->pev->owner = owner->edict();
                owner->mdSpawnMonster[child->slot].lPrivData = child->actorAddress;
                owner->mdSpawnMonster[child->slot].spawned = true;
            }
            child->retiring = false; child->uncertain = true;
        }
    }
}
void ObserveLifecycle(CMSMonster* actor, Lifecycle event)
{
    Child* child = Find(actor);
    if (!child && enabled && actor)
        for (auto& observer : deadObservers)
            if (observer.used && Actor(observer) == actor) { child = &observer; break; }
    if (!child) return;
    switch (event)
    {
    case Lifecycle::NativeXPDispatch: ++xpDispatches; Record("native_xp_dispatch", child); break;
    case Lifecycle::PredeathDispatch: ++predeathDispatches; Record("predeath_dispatch", child); break;
    case Lifecycle::DeathDispatch: ++deathDispatches; Record("death_dispatch", child); break;
    case Lifecycle::DropAllCall: ++dropAllCalls; Record("drop_all_call", child); break;
    }
}
bool RetainRegion(int region)
{
    if (!enabled || region == REGION_NONE) return false;
    for (auto& child : children)
        if (child.used && child.region == region) return true; // Missing identities reconcile only in Frame.
    return false;
}
void Frame()
{
    if (!enabled || !requested || insideFrame || !gpGlobals || !std::isfinite(gpGlobals->time) || gpGlobals->time < 0) return;
    insideFrame = true; ++frames;
    const auto map = generation;
    const auto started = std::chrono::steady_clock::now();
    bool retirementUsed = false;
    const auto players = Players();
    liveItems.clear();
    for (int index = gpGlobals->maxClients + 1; index < gpGlobals->maxEntities; ++index)
    {
        edict_t* ent = INDEXENT(index);
        if (!ent || ent->free || !ent->pvPrivateData) continue;
        CBaseEntity* entity = CBaseEntity::Instance(ent);
        if (entity && entity->IsMSItem())
        { EHANDLE handle{}; handle = entity; liveItems.emplace(entity, std::make_pair(handle, Key(entity))); }
    }
    for (auto& observer : deadObservers)
        if (observer.used && !Actor(observer)) observer = Child{};
    // Reconcile globally: an owner removed by script cannot hide its live charge.
    for (int cell = 0; cell < P::MaxActors; ++cell)
    {
        Child& child = children[cell]; if (!child.used) continue;
        CMSMonster* actor = Actor(child); CAreaMonsterSpawn* owner = Owner(child);
        if (!actor)
        {
            edict_t* ent = child.actor.Get();
            if (ent && !ent->free) { child.uncertain = true; child.hold = P::RetentionReason::Unsupported; continue; }
            ++missing; Release(cell, "missing_identity", false); continue;
        }
        if (child.deathNotified)
        {
            if (!actor->IsAlive()) { Release(cell, "ordinary_death_confirmed", false); continue; }
            if (owner && actor->pev->owner == owner->edict() &&
                owner->mdSpawnMonster[child.slot].lPrivData == child.actorAddress)
            {
                // Stock skeleton fake death calls setalive1, then restores HP
                // after a delay. Keep this exact incarnation and charge. Rearm
                // the next real Killed/notice so it records its OWN death delay.
                owner->mdSpawnMonster[child.slot].spawned = true;
                child.deathNotified = false; child.deathSeen = false;
                child.idle = P::IdleState{};
                Record("revived_same_incarnation_charge", &child);
                // Sticky accepted damage/credit and all script state are retained.
            }
            else { child.uncertain = true; child.hold = P::RetentionReason::Unsupported; }
            continue;
        }
        if (!owner) { child.uncertain = true; child.hold = P::RetentionReason::NotOwnedOrAlive; continue; }
        const auto at = Position(actor->pev->origin);
        const auto presence = Presence(owner, players, &at);
        child.hold = P::Retirement(child.config, gpGlobals->time, presence, Facts(child), child.idle);
        if (child.hold == P::RetentionReason::RetirePristine && !retirementUsed)
        { retirementUsed = true; Retire(cell); }
        if (!enabled || generation != map) return;
    }
    for (auto& controller : controllers)
        if (controller.used && !Resolve(controller.handle, controller.key))
        {
            budget.SetReady(controller.key, 0);
            if (budget.Unregister(controller.key)) controller = Controller{};
        }
    MSR_ForEachSpawner([](CAreaMonsterSpawn* owner, void*) {
        if (owner->m_EncounterRequested && !owner->m_EncounterAttempted)
            owner->InitEncounter();
    }, nullptr);
    bool ready = false, usesFrameGate = false;
    for (auto& controller : controllers)
    {
        if (!controller.used) continue;
        auto* owner = static_cast<CAreaMonsterSpawn*>(Resolve(controller.handle, controller.key));
        if (!owner) continue;
        owner->m_EncounterActive = P::ZoneActive(owner->m_EncounterActive, Presence(owner, players));
        std::uint32_t mask = 0;
        if (!owner->m_EncounterBad && owner->m_fActive && owner->m_EncounterActive &&
            !owner->SpawnLimitReached() && MSRegions::IsLoaded(owner->Region()))
            for (unsigned int slot = 0; slot < owner->iMonstersToSpawn; ++slot)
            {
                const auto& md = owner->mdSpawnMonster[slot];
                const auto& logical = ledger[owner->m_EncounterLedger[slot]];
                if (!md.spawned && (md.lives == -1 || md.livesleft > 0) &&
                    gpGlobals->time >= logical.death + logical.delay && gpGlobals->time >= logical.retry)
                    mask |= std::uint32_t{1} << slot;
            }
        budget.SetReady(controller.key, mask);
        if (mask) { ready = true; if (owner->Region() != REGION_NONE) usesFrameGate = true; }
    }
    if (ready)
    {
        double cap = 0, interval = 0.2;
        P::ParseNumber(capCvar.string, cap); P::ParseNumber(intervalCvar.string, interval);
        const auto limits = P::RuntimeLimits(cap, interval);
        if (usesFrameGate && !MSRegions::SpawnSlotAvailable()) { ++frameGateWait; }
        else if (limits.globalCap > 0 && EnsureProbes())
        {
            // Policy receives effective unavailable slots; its arithmetic is
            // unchanged, but recently freed allocator holes no longer inflate
            // the available reserve. Active-count telemetry remains separate.
            lastAdmission = budget.Reserve(gpGlobals->time, limits, gpGlobals->maxEntities - AllocatorReady(),
                gpGlobals->maxEntities, Gate);
            if (lastAdmission.reason == P::AdmissionReason::Granted) Birth(lastAdmission);
        }
    }
    if (!enabled || generation != map) return;
    const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - started).count();
    frameMsTotal += ms; if (ms > frameMsMax) frameMsMax = ms;
    insideFrame = false;
}
} // namespace MSREncounters

bool CAreaMonsterSpawn::InitEncounter()
{
    using namespace MSREncounters;
    m_EncounterAttempted = true;
    auto reject = [this](const char* why) {
        m_EncounterBad = true; ++refused; Record(why);
        ALERT(at_console, "MSR optional encounter rejected (%s), controller %d:%d\n", why, entindex(), edict()->serialnumber);
        return false;
    };
    m_EncounterLedger.fill(-1);
    if (m_EncounterBad) return reject("malformed_keys_or_descriptor");
    if (!P::ValidConfig(m_EncounterConfig) || iMonstersToSpawn < 1 || iMonstersToSpawn > P::MaxSlots ||
        m_SpawnLoc != SPAWNLOC_FIXED || m_fSpawnOnTrigger || resetwhen || iPlayerReq || iHPReq_min ||
        iHPReq_max || m_sTargetAllPerish || !pev->targetname || !*STRING(pev->targetname))
        return reject("unsupported_controller");
    const auto key = Key(this);
    for (auto& current : controllers)
    {
        if (!current.used) continue;
        auto* other = static_cast<CAreaMonsterSpawn*>(Resolve(current.handle, current.key));
        if (other && other != this && other->Region() == Region() &&
            FStrEq(STRING(other->pev->targetname), STRING(pev->targetname))) return reject("duplicate_controller");
    }
    std::array<int, P::MaxSlots> indices{};
    std::vector<Ledger> additions;
    for (unsigned int slot = 0; slot < iMonstersToSpawn; ++slot)
    {
        auto& md = mdSpawnMonster[slot];
        if (!P::KnownDescriptor(STRING(md.scriptfile), m_EncounterDescriptors[slot]) ||
            !md.targetname || !*STRING(md.targetname) || md.spawnchance != 100 || md.spawnontrigger ||
            md.nplayers || md.hpreq_min || md.hpreq_max || md.m_nRndMobs || md.bossConfigured ||
            md.bossOpen || md.target || md.killtarget || md.perishtarget ||
            (md.lives != -1 && md.lives < 1) || !std::isfinite(md.delaylow) || !std::isfinite(md.delayhigh) ||
            md.delaylow < 0 || md.delayhigh < md.delaylow || !P::ValidPosition(Position(md.origin)))
            return reject("unsupported_template");
        for (unsigned int prior = 0; prior < slot; ++prior)
            if (FStrEq(STRING(md.targetname), STRING(mdSpawnMonster[prior].targetname))) return reject("duplicate_slot");
        Ledger logical;
        logical.controller = STRING(pev->targetname); logical.name = STRING(md.targetname);
        logical.script = STRING(md.scriptfile); logical.classname = STRING(md.classname);
        logical.region = Region(); logical.pad = Position(md.origin); logical.angles = Position(md.angles);
        logical.descriptor = m_EncounterDescriptors[slot]; logical.lives = md.lives; logical.left = md.livesleft;
        logical.death = md.deathtime; logical.delay = md.delayvalue;
        int index = -1;
        for (std::size_t i = 0; i < ledger.size(); ++i)
            if (ledger[i].region == logical.region && ledger[i].controller == logical.controller && ledger[i].name == logical.name)
            {
                const auto& old = ledger[i];
                if (old.script != logical.script || old.classname != logical.classname || old.lives != logical.lives ||
                    old.descriptor.width != logical.descriptor.width || old.descriptor.height != logical.descriptor.height ||
                    P::DistanceSquared(old.pad, logical.pad) != 0 || P::DistanceSquared(old.angles, logical.angles) != 0)
                    return reject("replay_identity_changed");
                for (auto& child : children)
                    if (child.used && child.ledger == static_cast<int>(i)) return reject("replay_live_incarnation");
                index = static_cast<int>(i); break;
            }
        if (index < 0)
        {
            if (ledger.size() + additions.size() >= MaxLedger) return reject("ledger_capacity");
            index = static_cast<int>(ledger.size() + additions.size()); additions.push_back(logical);
        }
        indices[slot] = index;
    }
    Controller* available = nullptr;
    for (auto& current : controllers) if (!current.used) { available = &current; break; }
    if (!available || !budget.Register(key, iMonstersToSpawn, m_EncounterConfig.localCap))
        return reject("controller_capacity_or_stale_index");
    for (auto& addition : additions) ledger.push_back(addition);
    available->used = true; available->handle = this; available->key = key;
    for (unsigned int slot = 0; slot < iMonstersToSpawn; ++slot)
    {
        m_EncounterLedger[slot] = indices[slot];
        const auto& logical = ledger[indices[slot]];
        mdSpawnMonster[slot].livesleft = logical.left;
        mdSpawnMonster[slot].deathtime = static_cast<float>(logical.death);
        mdSpawnMonster[slot].delayvalue = static_cast<float>(logical.delay);
        mdSpawnMonster[slot].spawned = false; mdSpawnMonster[slot].lPrivData = 0;
    }
    m_EncounterRegistered = true; Record("controller_registered"); return true;
}
bool CAreaMonsterSpawn::EncounterDeathNotice(entvars_t* vars)
{
    using namespace MSREncounters;
    CBaseEntity* entity = CBaseEntity::Instance(vars);
    if (!entity || !entity->IsMSMonster()) return false;
    auto* actor = static_cast<CMSMonster*>(entity);
    Child* child = Find(actor);
    if (!child || child->ownerKey == P::ControllerKey{} || Owner(*child) != this ||
        actor->pev->owner != edict() || child->slot < 0 ||
        mdSpawnMonster[child->slot].lPrivData != reinterpret_cast<long>(actor)) return false;
    if (child->deathNotified) return true;
    ++deathNotices; Record("ordinary_death_notice", child);
    const int slot = child->slot;
    mdSpawnMonster[slot].spawned = false;
    RespawnMonster(&mdSpawnMonster[slot]); // Genuine stock delay, even while GM cap is full.
    Store(this, slot);
    child->deathNotified = true;
    bool observerStored = false;
    for (auto& observer : deadObservers)
        if (observer.used && observer.actorKey == child->actorKey && Actor(observer) == actor)
        { observer = *child; observerStored = true; break; }
    for (auto& observer : deadObservers)
    {
        if (observerStored) break;
        if (!observer.used || !Actor(observer))
        { observer = *child; observerStored = true; break; }
    }
    if (!observerStored) { ++observerOverflow; Record("corpse_observer_capacity", child); }
    // Killed calls this BEFORE game_predeath/game_death. Frame confirms a dead
    // incarnation before releasing; revival scripts remain charged/protected.
    return true;
}
