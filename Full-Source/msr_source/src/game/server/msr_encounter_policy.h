#pragma once

// Isolated policy prototype: no engine headers, entity operations, scripts or FN.
// An engine adapter must provide validated observations and exact child ownership.
#include <array>
#include <cerrno>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <limits>

namespace MSREncounterPolicy
{
constexpr int MaxSlots = 32;
constexpr int MaxActors = 128;
constexpr int DefaultGlobalCap = 16;
constexpr int MaxControllers = 256; // Bounded prototype registry; freeze before integration.
constexpr int EdictReserve = 64;
constexpr int MaxPadChecksPerCall = 8;
constexpr double MinInterval = 0.05;
constexpr double MaxInterval = 2.0;

struct Config
{
    double radius = 1600;
    double keepRadius = 2400;
    double idleSeconds = 30;
    double minDistance = 320;
    int localCap = 6;
};

inline bool ValidConfig(const Config& c)
{
    // Native Vector components are floats; square in double to avoid float overflow.
    const double largestRadius = std::numeric_limits<float>::max();
    return std::isfinite(c.radius) && c.radius > 0 && c.radius <= largestRadius &&
        std::isfinite(c.keepRadius) && c.keepRadius > c.radius &&
        c.keepRadius <= largestRadius && std::isfinite(c.idleSeconds) &&
        c.idleSeconds > 0 && std::isfinite(c.minDistance) && c.minDistance > 0 &&
        c.minDistance < c.radius && c.localCap >= 1 && c.localCap <= MaxSlots;
}

inline bool ParseNumber(const char* text, double& value)
{
    if (!text || !*text) return false;
    char* end = nullptr;
    errno = 0;
    const double parsed = std::strtod(text, &end);
    if (end == text || errno == ERANGE || !std::isfinite(parsed)) return false;
    while (*end == ' ' || *end == '\t' || *end == '\r' || *end == '\n') ++end;
    if (*end) return false;
    value = parsed;
    return true;
}

inline bool ParseSlotCap(const char* text, int& value)
{
    double parsed;
    if (!ParseNumber(text, parsed) || parsed < 1 || parsed > MaxSlots ||
        std::floor(parsed) != parsed) return false;
    value = static_cast<int>(parsed);
    return true;
}

struct Limits
{
    int globalCap = DefaultGlobalCap;
    double interval = 0.2;
};

inline Limits RuntimeLimits(double cap, double interval)
{
    Limits result;
    // An invalid cap blocks births. Invalid interval uses the conservative default.
    if (!std::isfinite(cap) || cap <= 0) result.globalCap = 0;
    else if (cap >= MaxActors) result.globalCap = MaxActors;
    else result.globalCap = static_cast<int>(cap);
    if (std::isfinite(interval))
        result.interval = interval < MinInterval ? MinInterval :
            (interval > MaxInterval ? MaxInterval : interval);
    return result;
}

struct Vec3 { double x = 0, y = 0, z = 0; };

struct Descriptor { double width = 0, height = 0; };
inline bool ValidDescriptor(const Descriptor& d)
{
    return std::isfinite(d.width) && std::isfinite(d.height) &&
        d.width > 0 && d.height > 0 && d.width <= 128 && d.height <= 160;
}

struct KnownScript { const char* name; Descriptor bounds; };
inline constexpr std::array<KnownScript, 10> InitialScripts = {{
    {"monsters/orc_warrior", {32, 72}}, {"monsters/orc_archer", {32, 60}},
    {"monsters/troll", {100, 125}}, {"monsters/goblin", {32, 60}},
    {"monsters/skeleton", {32, 80}}, {"monsters/wolf", {36, 48}},
    {"monsters/wolf_alpha", {36, 48}}, {"monsters/spider_mini", {16, 20}},
    {"monsters/boar", {50, 40}}, {"monsters/bear_black", {64, 95}}
}};

inline bool KnownDescriptor(const char* script, const Descriptor& d)
{
    if (!script || !*script || !ValidDescriptor(d)) return false;
    for (const auto& known : InitialScripts)
        if (std::strcmp(script, known.name) == 0)
            return d.width == known.bounds.width && d.height == known.bounds.height;
    return false;
}

inline bool ValidPosition(const Vec3& p)
{
    const double bound = std::numeric_limits<float>::max();
    return std::isfinite(p.x) && std::isfinite(p.y) && std::isfinite(p.z) &&
        std::fabs(p.x) <= bound && std::fabs(p.y) <= bound && std::fabs(p.z) <= bound;
}

inline double DistanceSquared(const Vec3& a, const Vec3& b)
{
    const double x = a.x - b.x, y = a.y - b.y, z = a.z - b.z;
    return x * x + y * y + z * z;
}

struct Bounds { Vec3 min, max; };
inline bool ValidBounds(const Bounds& b)
{
    return ValidPosition(b.min) && ValidPosition(b.max) &&
        b.min.x <= b.max.x && b.min.y <= b.max.y && b.min.z <= b.max.z;
}
inline bool ExpectedBounds(const Descriptor& d, const Vec3& origin, Bounds& result)
{
    if (!ValidDescriptor(d) || !ValidPosition(origin)) return false;
    const Bounds calculated{{origin.x - d.width / 2, origin.y - d.width / 2, origin.z},
        {origin.x + d.width / 2, origin.y + d.width / 2, origin.z + d.height}};
    if (!ValidBounds(calculated)) return false;
    result = calculated;
    return true;
}
inline bool ActorBoundsMatch(const char* script, const Descriptor& expected,
    const Descriptor& observed, const Bounds& relative, const Vec3& origin)
{
    if (!KnownDescriptor(script, expected) || !ValidDescriptor(observed) ||
        !ValidBounds(relative) || !ValidPosition(origin)) return false;
    return observed.width == expected.width && observed.height == expected.height &&
        relative.min.x == -expected.width / 2 && relative.min.y == -expected.width / 2 &&
        relative.min.z == 0 && relative.max.x == expected.width / 2 &&
        relative.max.y == expected.width / 2 && relative.max.z == expected.height;
}
inline bool Overlaps(const Bounds& a, const Bounds& b)
{
    // Inclusive contact is conservatively occupied; validity is checked by callers.
    return a.min.x <= b.max.x && a.max.x >= b.min.x &&
        a.min.y <= b.max.y && a.max.y >= b.min.y &&
        a.min.z <= b.max.z && a.max.z >= b.min.z;
}

struct Player
{
    bool connected = false, loaded = false, placed = false, alive = false;
    Vec3 position;
};

struct Presence
{
    bool valid = false;
    std::size_t eligiblePlayers = 0;
    bool nearPad = false, keepPad = false, keepActor = false;
    double minPadDistanceSquared = std::numeric_limits<double>::infinity();
    double minActorDistanceSquared = std::numeric_limits<double>::infinity();
};

inline Presence Observe(const Config& c, const Player* players, std::size_t playerCount,
    const Vec3* pads, std::size_t padCount, const Vec3* actor = nullptr)
{
    Presence result;
    if (!ValidConfig(c) || !pads || padCount == 0 || padCount > MaxSlots ||
        (!players && playerCount) || (actor && !ValidPosition(*actor))) return result;
    for (std::size_t pad = 0; pad < padCount; ++pad)
        if (!ValidPosition(pads[pad])) return result;
    result.valid = true;
    for (std::size_t i = 0; i < playerCount; ++i)
    {
        const Player& p = players[i];
        if (!p.connected || !p.loaded || !p.placed || !p.alive) continue;
        if (!ValidPosition(p.position)) { result.valid = false; continue; }
        ++result.eligiblePlayers;
        for (std::size_t pad = 0; pad < padCount; ++pad)
        {
            const double distance = DistanceSquared(p.position, pads[pad]);
            if (distance < result.minPadDistanceSquared)
                result.minPadDistanceSquared = distance;
        }
        if (actor)
        {
            const double distance = DistanceSquared(p.position, *actor);
            if (distance < result.minActorDistanceSquared)
                result.minActorDistanceSquared = distance;
        }
    }
    if (result.valid)
    {
        result.nearPad = result.minPadDistanceSquared <= c.radius * c.radius;
        result.keepPad = result.minPadDistanceSquared <= c.keepRadius * c.keepRadius;
        result.keepActor = result.minActorDistanceSquared <= c.keepRadius * c.keepRadius;
    }
    return result;
}

inline bool ZoneActive(bool wasActive, const Presence& p)
{
    return p.valid && (wasActive ? p.keepPad : p.nearPad);
}

enum class PadReason { Allowed, InvalidObservation, NoLivingPlayers, TooClose,
    WorldHull, PlayerHull, MountHull };
struct HullSafety { bool valid = false, worldClear = false, playersClear = false, mountsClear = false; };

struct Occupant { bool blocks = false; Bounds actual; };
inline PadReason CheckOccupants(const Bounds& selected,
    const Occupant* players, std::size_t playerCount,
    const Occupant* mounts, std::size_t mountCount)
{
    if (!ValidBounds(selected) || (!players && playerCount) || (!mounts && mountCount))
        return PadReason::InvalidObservation;
    for (std::size_t i = 0; i < playerCount; ++i)
        if (players[i].blocks)
        {
            if (!ValidBounds(players[i].actual)) return PadReason::InvalidObservation;
            if (Overlaps(selected, players[i].actual)) return PadReason::PlayerHull;
        }
    for (std::size_t i = 0; i < mountCount; ++i)
        if (mounts[i].blocks)
        {
            if (!ValidBounds(mounts[i].actual)) return PadReason::InvalidObservation;
            if (Overlaps(selected, mounts[i].actual)) return PadReason::MountHull;
        }
    return PadReason::Allowed;
}

inline PadReason SelectedPadDecision(const Config& c, const Presence& selectedPad,
    const HullSafety& hulls)
{
    if (!ValidConfig(c) || !selectedPad.valid || !hulls.valid) return PadReason::InvalidObservation;
    if (!selectedPad.eligiblePlayers) return PadReason::NoLivingPlayers;
    if (!std::isfinite(selectedPad.minPadDistanceSquared) || selectedPad.minPadDistanceSquared < 0)
        return PadReason::InvalidObservation;
    if (selectedPad.minPadDistanceSquared <= c.minDistance * c.minDistance) return PadReason::TooClose;
    if (!hulls.worldClear) return PadReason::WorldHull;
    if (!hulls.playersClear) return PadReason::PlayerHull;
    if (!hulls.mountsClear) return PadReason::MountHull;
    return PadReason::Allowed;
}

struct ActorFacts
{
    bool exactOwned = false, alive = false, ordinaryAmbient = false, infiniteLife = false;
    bool playerOwned = false, horse = false, storeOrMenu = false, boss = false, quest = false;
    bool combatTouched = false, rewardCredit = false;
    bool observedAttack = false, nonWanderingChase = false;
    // This is adapter-validated protection, NOT evidence of a real attack.
    // The adapter must revalidate live handle/association on each decision.
    // Do not erase or time out arbitrary script state merely to retire an actor.
    bool conservativeReferenceHold = false;
    bool hasActivity = false;
    double lastActivity = 0, activityHoldSeconds = 30;
    double health = 0, maxHealth = 0;
};

enum class RetentionReason
{
    InvalidObservation, InvalidClock, NotOwnedOrAlive, Unsupported, FiniteLife,
    PlayerOwned, Horse, StoreOrMenu, Boss, Quest, CombatTouched, RewardCredit,
    Health, ObservedAttack, Chase, RecentActivity, ConservativeReference,
    NearPad, NearActor, FarGrace, RetirePristine
};

struct IdleState { bool timing = false; double farSince = 0, lastCheck = 0; };

inline RetentionReason Retirement(const Config& c, double now, const Presence& p,
    const ActorFacts& a, IdleState& idle)
{
    RetentionReason reason = RetentionReason::FarGrace;
    if (!ValidConfig(c) || !p.valid) reason = RetentionReason::InvalidObservation;
    else if (!std::isfinite(now) || now < 0 || (idle.timing && now < idle.lastCheck))
        reason = RetentionReason::InvalidClock;
    else if (!a.exactOwned || !a.alive) reason = RetentionReason::NotOwnedOrAlive;
    else if (!a.ordinaryAmbient) reason = RetentionReason::Unsupported;
    else if (!a.infiniteLife) reason = RetentionReason::FiniteLife;
    else if (a.playerOwned) reason = RetentionReason::PlayerOwned;
    else if (a.horse) reason = RetentionReason::Horse;
    else if (a.storeOrMenu) reason = RetentionReason::StoreOrMenu;
    else if (a.boss) reason = RetentionReason::Boss;
    else if (a.quest) reason = RetentionReason::Quest;
    else if (a.combatTouched) reason = RetentionReason::CombatTouched;
    else if (a.rewardCredit) reason = RetentionReason::RewardCredit;
    else if (!std::isfinite(a.health) || !std::isfinite(a.maxHealth) || a.maxHealth <= 0 ||
        a.health <= 0 || a.health != a.maxHealth) reason = RetentionReason::Health;
    else if (a.observedAttack) reason = RetentionReason::ObservedAttack;
    else if (a.nonWanderingChase) reason = RetentionReason::Chase;
    else if (a.hasActivity && (!std::isfinite(a.lastActivity) || a.lastActivity < 0 ||
        !std::isfinite(a.activityHoldSeconds) || a.activityHoldSeconds <= 0 ||
        a.lastActivity > now || now - a.lastActivity < a.activityHoldSeconds))
        reason = RetentionReason::RecentActivity;
    else if (a.conservativeReferenceHold) reason = RetentionReason::ConservativeReference;
    else if (p.keepPad) reason = RetentionReason::NearPad;
    else if (p.keepActor) reason = RetentionReason::NearActor;
    if (reason != RetentionReason::FarGrace)
    {
        idle = IdleState{};
        return reason;
    }
    if (!idle.timing) { idle.timing = true; idle.farSince = now; }
    idle.lastCheck = now;
    return now - idle.farSince >= c.idleSeconds ?
        RetentionReason::RetirePristine : RetentionReason::FarGrace;
}

struct ControllerKey
{
    std::uint32_t index = 0, serial = 0;
    bool operator==(const ControllerKey& other) const
    { return index == other.index && serial == other.serial; }
};

struct Ticket
{
    std::uint64_t epoch = 0, sequence = 0;
    int cell = -1;
};

enum class AdmissionReason
{
    Granted, InvalidInput, ClockRewind, Disabled, GlobalFull, Interval,
    EdictMargin, NoReadyController, LocalFull, SlotsCharged, PadBlocked, IdentityExhausted
};

struct Admission
{
    AdmissionReason reason = AdmissionReason::NoReadyController;
    Ticket ticket;
    ControllerKey controller;
    int slot = -1;
    int padChecks = 0;
    PadReason padReason = PadReason::Allowed;
};

// Mandatory adapter callback, invoked before charging EACH candidate birth.
// Runtime must freshly observe selected hull/world/player/mount occupancy here.
// It is a read-only query: it must not reenter or mutate the budget/registrations.
using PadGate = PadReason (*)(ControllerKey, int, void*);

class AdmissionBudget
{
    enum class ChargeState { Empty, Inflight, Live };
    struct Controller
    {
        bool registered = false;
        ControllerKey key;
        int slotCount = 0, localCap = 0, cursor = 0;
        std::uint32_t readyMask = 0;
    };
    struct Charge
    {
        ChargeState state = ChargeState::Empty;
        std::uint64_t sequence = 0;
        int controller = -1, slot = -1;
    };
    std::array<Controller, MaxControllers> controllers_{};
    std::array<Charge, MaxActors> charges_{};
    std::uint64_t epoch_ = 1, sequence_ = 0;
    bool exhausted_ = false, hasClock_ = false;
    int cursor_ = 0;
    double nextGrant_ = 0, lastCheck_ = 0;

    int Find(const ControllerKey& key) const
    {
        for (int i = 0; i < MaxControllers; ++i)
            if (controllers_[i].registered && controllers_[i].key == key) return i;
        return -1;
    }
    int Charged(int controller) const
    {
        int count = 0;
        for (const auto& charge : charges_)
            if (charge.state != ChargeState::Empty && charge.controller == controller) ++count;
        return count;
    }
    bool SlotCharged(int controller, int slot) const
    {
        for (const auto& charge : charges_)
            if (charge.state != ChargeState::Empty && charge.controller == controller &&
                charge.slot == slot) return true;
        return false;
    }
    Charge* Resolve(const Ticket& ticket)
    {
        if (ticket.epoch != epoch_ || ticket.cell < 0 || ticket.cell >= MaxActors ||
            ticket.sequence == 0) return nullptr;
        Charge& charge = charges_[ticket.cell];
        return charge.state != ChargeState::Empty && charge.sequence == ticket.sequence ?
            &charge : nullptr;
    }
public:
    bool Register(ControllerKey key, int slots, int localCap)
    {
        if (exhausted_ || key.index == 0 || slots < 1 || slots > MaxSlots ||
            localCap < 1 || localCap > MaxSlots || Find(key) >= 0) return false;
        // A different serial at the same index must not displace a charged old owner.
        for (const auto& c : controllers_)
            if (c.registered && c.key.index == key.index) return false;
        for (auto& c : controllers_)
            if (!c.registered)
            {
                c = Controller{}; c.registered = true; c.key = key;
                c.slotCount = slots; c.localCap = localCap;
                return true;
            }
        return false;
    }
    bool Unregister(ControllerKey key)
    {
        const int i = Find(key);
        if (i < 0 || Charged(i)) return false;
        controllers_[i] = Controller{};
        return true;
    }
    bool SetReady(ControllerKey key, std::uint32_t mask)
    {
        const int i = Find(key);
        if (i < 0) return false;
        Controller& c = controllers_[i];
        const std::uint32_t valid = c.slotCount == MaxSlots ? UINT32_MAX :
            ((std::uint32_t{1} << c.slotCount) - 1);
        if (mask & ~valid) { c.readyMask = 0; return false; }
        c.readyMask = mask;
        return true;
    }
    bool SetLocalCap(ControllerKey key, int cap)
    {
        const int i = Find(key);
        if (i < 0 || cap < 1 || cap > MaxSlots) return false;
        controllers_[i].localCap = cap;
        return true;
    }
    int Live() const
    {
        int count = 0;
        for (const auto& c : charges_) if (c.state == ChargeState::Live) ++count;
        return count;
    }
    int Inflight() const
    {
        int count = 0;
        for (const auto& c : charges_) if (c.state == ChargeState::Inflight) ++count;
        return count;
    }
    int LocalCharged(ControllerKey key) const
    {
        const int i = Find(key);
        return i < 0 ? 0 : Charged(i);
    }
    double NextGrant() const { return nextGrant_; }
    Admission Reserve(double now, const Limits& limits, int entities, int maxEntities,
        PadGate checkPad, void* context = nullptr)
    {
        Admission result;
        if (!std::isfinite(now) || now < 0 || limits.globalCap < 0 ||
            limits.globalCap > MaxActors || !std::isfinite(limits.interval) ||
            limits.interval < MinInterval || limits.interval > MaxInterval ||
            entities < 0 || maxEntities < entities || !checkPad)
        { result.reason = AdmissionReason::InvalidInput; return result; }
        if (hasClock_ && now < lastCheck_)
        { result.reason = AdmissionReason::ClockRewind; return result; }
        hasClock_ = true; lastCheck_ = now;
        if (exhausted_ || sequence_ == UINT64_MAX)
        { result.reason = AdmissionReason::IdentityExhausted; return result; }
        if (limits.globalCap == 0)
        { result.reason = AdmissionReason::Disabled; return result; }
        const int inflight = Inflight();
        if (Live() + inflight >= limits.globalCap)
        { result.reason = AdmissionReason::GlobalFull; return result; }
        if (now < nextGrant_)
        { result.reason = AdmissionReason::Interval; return result; }
        // Keep at least 64 edicts AFTER allocating this primary actor. Gear/helpers
        // still require an engine-side resource check; this is not a total entity cap.
        if (maxEntities - entities - inflight <= EdictReserve)
        { result.reason = AdmissionReason::EdictMargin; return result; }
        bool localFull = false, slotsCharged = false, padBlocked = false;
        const int startController = cursor_;
        for (int offset = 0; offset < MaxControllers; ++offset)
        {
            const int i = (startController + offset) % MaxControllers;
            Controller& c = controllers_[i];
            if (!c.registered || c.readyMask == 0) continue;
            if (Charged(i) >= c.localCap) { localFull = true; continue; }
            const int startSlot = c.cursor;
            for (int offsetSlot = 0; offsetSlot < c.slotCount; ++offsetSlot)
            {
                const int slot = (startSlot + offsetSlot) % c.slotCount;
                if (!(c.readyMask & (std::uint32_t{1} << slot))) continue;
                if (SlotCharged(i, slot)) { slotsCharged = true; continue; }
                if (result.padChecks == MaxPadChecksPerCall)
                { result.reason = AdmissionReason::PadBlocked; return result; }
                ++result.padChecks;
                const PadReason pad = checkPad(c.key, slot, context);
                if (pad != PadReason::Allowed)
                {
                    padBlocked = true; result.padReason = pad;
                    // WAIT changes only selection cursors, never lives/death timers
                    // or charges. Rotation prevents occupied early pads starving others.
                    c.cursor = (slot + 1) % c.slotCount;
                    cursor_ = (i + 1) % MaxControllers;
                    continue;
                }
                for (int cell = 0; cell < MaxActors; ++cell)
                {
                    Charge& charge = charges_[cell];
                    if (charge.state != ChargeState::Empty) continue;
                    charge.state = ChargeState::Inflight;
                    charge.sequence = ++sequence_; charge.controller = i; charge.slot = slot;
                    result.reason = AdmissionReason::Granted;
                    result.padReason = PadReason::Allowed;
                    result.ticket = Ticket{epoch_, sequence_, cell};
                    result.controller = c.key; result.slot = slot;
                    cursor_ = (i + 1) % MaxControllers;
                    c.cursor = (slot + 1) % c.slotCount;
                    nextGrant_ = now + limits.interval;
                    return result;
                }
                result.reason = AdmissionReason::GlobalFull;
                return result;
            }
        }
        result.reason = padBlocked ? AdmissionReason::PadBlocked : (localFull ? AdmissionReason::LocalFull :
            (slotsCharged ? AdmissionReason::SlotsCharged : AdmissionReason::NoReadyController));
        return result;
    }
    bool Commit(const Ticket& ticket)
    {
        Charge* charge = Resolve(ticket);
        if (!charge || charge->state != ChargeState::Inflight) return false;
        charge->state = ChargeState::Live;
        return true;
    }
    bool Release(const Ticket& ticket)
    {
        Charge* charge = Resolve(ticket);
        if (!charge) return false;
        *charge = Charge{};
        return true;
    }
    void ResetMap()
    {
        controllers_ = {}; charges_ = {}; cursor_ = 0;
        nextGrant_ = 0; lastCheck_ = 0; hasClock_ = false; sequence_ = 0;
        if (epoch_ == UINT64_MAX) exhausted_ = true;
        else ++epoch_;
    }
};
}
