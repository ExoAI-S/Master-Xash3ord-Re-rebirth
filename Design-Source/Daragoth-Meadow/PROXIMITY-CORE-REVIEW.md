# Optional proximity encounter core: review candidate

The new map's 30 encounter controllers can share a bounded population instead of
spawning all 163 authored reserve slots. This is a **source/build review candidate**.
Independent implementation review is complete, with no remaining confirmed source
blockers. Private native tests and installation remain pending. The existing human
playtest has not been replaced or restarted.

## Build and source provenance

The separate x86 Debug server and client targets compiled successfully with the
repository's `/Zi /Ob0 /Od /RTC1 -std:c++20 -MT /MP /utf-8` settings. The existing
static CRT setting is retained. PE CodeView GUID and age match each adjacent PDB.
This establishes compilation/symbol provenance, not native behavior or FPS safety.

Local frozen packet:
`work/daragoth-development/proximity-encounters/integration/candidate-9de2fb15c49b4506bf2a013085c15064/receipt.json`
SHA256 `f81af4b4b0c199719e0deac61bce0f529b0a7dd88f024132f0c0b51dd7d4b634`.
It archives 802 source, include, library, helper and model-test inputs, the tracked
patch, build metadata, allocator test evidence and both DLL/PDB/map pairs. This is a post-build snapshot with
current-copy hash verification; compilation consumed working-tree inputs.

Server DLL SHA256:
`56a68a750b2766198944d14e881ae994a7a70e9b5075aa3e48b8df43199f6222`.
Server PDB SHA256:
`172d7b9e54d12792aeb09cf8ed0541f9acef69dacfcd6f6cc518f6d3c6a7ca76`.
GUID `b1daac3c-9941-49c6-93e8-dd14ff1a37a5`, age4. Build log
`build-v2-attempt05.log` SHA256 `1ebb8a2deba480ffb4d989df9a1f0378923058538e6066ac1d631a548ee01f04`.

The original b4b579 packet is preserved and superseded. Its complete independent
source review (`independent-b4b-source-review.json`, SHA256
`6a87550e972ed652dd6ae0b7892d7e1869b25ffd51ecdf453d7be6df5f17c0a5`)
identified dynamic-solid exclusion, probe monsterclip flags, later skeleton
death rearming and allocator reuse pressure as blockers. It also required fresh
post-Spawn separation and centralized accepted GiveHP loss coverage. This successor
repairs those six paths. The independent focused re-review covers the complete
981-line adapter and new 39-line allocator helper, carrying forward only unchanged
prior findings. Its receipt `independent-9de2-source-review.json` has SHA256
`c7df3dd40064a09f98a9435b2eb59a043be95fc65bd82b349b42652c79e635aa`.
The root disposition `root-9de2-source-disposition.json`, SHA256
`a80e176631c47c7c2f4ebef9fecf999ebed3539221a4fbfedaae6b6bf80ea17c`,
accepts the core source for preparing a private fixture with a separately reviewed
harness. Neither review authorizes a launch or establishes native acceptance.
These later sidecars preserve the original frozen packet and its historical gates.

The allocator model compiled under x86 Debug and passed 6 groups/53745 assertions:
8000 independent scan/high-water/growth snapshots and 10000 lifecycle actions,
recent-hole exhaustion, aging, pending/probe margins, map reset and SDK clock
rounding. The copied receipt SHA256 is
`5ca03a029254008e74a225620801f190852585e9cd92599c443f7da85da4e0f8`.
These tests execute the production allocator helper and unchanged admission policy
against an independent allocator model. They do not execute native engine callbacks.

The production policy header is byte-identical to the independently reviewed
9d1958 descriptor extension (19 groups,126804 assertions including 5000 model
actions). Those engine-free results are reused only for that unchanged header.
They do not test the new engine adapter, callbacks, replay or rewards.

No client message, shared player layout or protocol change is introduced. New
shared calls are SERVER-only. The new client compile is validation; private native
fixtures should retain the accepted client7331/PDB2f3f57f, engine, renderer, scripts
and controls until an independently justified client update exists.

## Implemented source paths

- `server/msr_encounters.inc`, included once after the complete spawner definition
  in `msmapents.cpp`, owns the bounded registry, ledger, hull probes and telemetry.
- Only `encounter=1` controllers enter admission. Malformed/unsupported opt-in
  controllers fail closed. Maps without opt-in requests skip the adapter frame.
- Initial global cap16 and interval0.2seconds; configured caps include inflight
  reservations. Probe creation and primary birth require at least64 allocator-ready
  slots after their allocation, with outstanding reservations included. The128
  ceiling is validation capacity, not a safe setting.
- `msr_encounter_allocator.h` scans the contiguous world array excluding client
  slots using the engine's strict free-time reuse predicate. Recently freed holes
  are unavailable until their actual reuse deadline. Since the SDK lacks the
  allocation high-water and reports double engine time as float, this is a lower
  bound using the float predecessor. Future-time old-map leftovers are excluded;
  conservative waits can occur despite unused engine capacity. It does not reserve
  resources for arbitrary later script-created gear/helpers.
- Ten descriptor-specific real engine query edicts are allocated before admission.
  The gate performs no allocation, script callback or budget mutation. It queries
  the engine's selected hull/offset with FL_MONSTER|FL_MONSTERCLIP and all linked
  dynamic solids, plus current player/horse boxes at the actual pad.
- All connected, loaded, placed, living players participate, including AFK and
  mounted players. Full3D pad distance, activation hysteresis, separation and
  actual actor distance feed the unchanged policy.
- Full Spawn, including game_postspawn, is followed by serial/owner, script,
  actual bounds, collision flags, solid/movement and live collision validation,
  including fresh minimum distance to living players at the actual actor origin.
  A disconnect/death during Spawn with no remaining eligible players leaves a
  geometrically valid actor charged for later ordinary idle checks. A surviving
  mismatch remains charged/protected and blocks the pack; it is not guessed away.
- `CreateStats` initializes only a newly allocated managed NPC reward ledger.
  `reserve_once` allocates plain `playerdamage_t[]` without value initialization;
  this hook avoids reading untouched uninitialized entries. Legacy/player
  allocations and existing accepted-credit protection are unchanged.
- Accepted HP loss at the central Give(HP) write, including direct script/AngelScript
  GiveHP calls before Killed, and the central SERVER MarkDamage overload after
  writes set permanent lifetime protection. Attack starts set timed activity.
  Numeric credit checks never read or log authentication/profile strings.
- Genuine DeathNotice records the normal lives and chosen delay even when the
  legacy GM cap is full. Charge release waits for the next frame's dead-incarnation
  observation, allowing immediate revival scripts to remain protected/charged.
  The exact surviving incarnation/owner/slot association rearms its death episode;
  later genuine deaths select their own stock cooldown. Sticky damage/credit and
  script state remain intact; corpse telemetry reuses the exact observer.
- A map-generation ledger preserves real cooldown/lives through region replay.
  Exact controller/template name, script/class, descriptor, pad and angle identity
  are required. Live old incarnations prevent duplicate replay. Only worldspawn
  resets it; it does not change FN or persist across map/server restarts.
- Charged children retain their original owner region, including crossing,
  protected, finite and orphaned actors. Confirmed missing identities reconcile
  once; a live edict with uncertain private identity does not become spare cap.
- At most one pristine infinite-life retirement transaction starts per frame.
  Exact owner/slot detachment precedes gear callbacks, while internal membership
  and its charge remain armed. Each callback gets fresh serial, generation,
  ownership, proximity and protection validation. Changed ownership is preserved.
  Actor removal uses nondeath cleanup and does not invoke Killed, DeathNotice,
  actor script death/predeath, drops, XP or targets.

## Telemetry grammar and limits

`ms_encounters` is a read-only server command. Each machine-readable line begins
`MS_ENCOUNTERS ` followed by one JSON object. It does not authorize observer
commands, teleports, fixture creation or native launches.

| type | Meaning |
| --- | --- |
| summary | Map generation, adapter frame/time/event highwater, cap/interval, charged live/inflight counts, engine nonfree/free counts, allocator-ready lower bound, attempts/births/death notices/retirement/missing/failure counters, last admission and pad reason, total/max adapter frame duration |
| lifecycle_coverage | Actual native LearnSkill dispatch, script predeath/death dispatch and DropAllItems-entry counts; explicit coverage gaps |
| controller | Serial-valid controller/region, activity/bad state, slot/local-cap/charge counts, eligible-player count and nearest authored pad squared distance |
| slot | Owner/slot/ledger, actual lives, chosen death time/delay/deadline, suspension, selected pad squared distance and fresh collision gate reason |
| actor | Serial-valid registered identity/owner/slot, original pinned region, sticky damage/credit, uncertainty/retirement, last retention decision, age/grace and closest current actor squared distance |
| actor_activity | First accepted damage/credit times, actual attack-start time, current enemy-reference index/serial/liveness |
| event | Last512 source-scoped events with sequence, generation/frame/time and owner/actor/slot/detail |

Enum integer codebooks come directly from `msr_encounter_policy.h` in the frozen
packet. Unknown/infinite nearest distances and absent activity/grace use-1.
Boolean fields are emitted as0/1 except literal coverage flags. Event history is
bounded; older events may have rotated out. `live` means committed charges, not
an independently counted population of attacking/alive monsters.
`free_edicts` is only maxEntities minus the active count; it is not allocator-ready
capacity. `allocator_ready_lower_bound` feeds admission, and unsupported
`allocator_highwater` is null. A postspawn mismatch event's detail is the actual
PadReason; Allowed with a mismatch denotes an ownership failure instead of geometry.

Timing includes the whole adapter frame, its engine queries and synchronous
birth scripts; it is not exclusive pure-policy time or total engine AI tick time.
Model/sound resource counts are unsupported and emitted null. Native XP dispatch
does not establish actual skill progression; DropAllItems entry does not count
actual loose drops. Direct scripted XP is not comprehensively instrumented.
Absence of counter/log entries is not proof that no reward or drop occurred.

## Conservative limitations and open acceptance work

Containers, wearables, active gear attacks, special ownership, menus/stores, boss
or quest outputs, finite lives and uncertain transforms are protected. Retirement
currently supports simple carried gear only. A callback abort can leave partial
gear cleanup; this is reported and the actor remains uncertain/charged. It is not
a claim of complete script-state preservation or general container support.

Sticky damage/credit and validated references can occupy all16 charges and pin
regions indefinitely. Fair selection does not restore occupied capacity. Native
tests must characterize starvation and the wolf/alpha friendly-reference cohort.
Review repeated fake skeleton deaths followed by final death and the immediate
versus delayed revival/death-release behavior, direct negative GiveHP then healing,
recent-hole churn at capacity, post-Spawn relocation and
callback removal/reassignment, external deletion/edict reuse, exact replay and
postspawn collision behavior before accepting this candidate.

The new map67946ff3 is separate from the human playtest. Source review has passed;
private changed-core native tests remain required, including actual two-client
presence, separation/occupied pads, genuine death/rewards/cooldowns, finite/replay
cases, legacy/FN/controls/doors/horse/water regressions and source-timed resource
cost. Cap24 requires a separate measured decision. Prior306f native reports do not
accept this new DLL. No runtime installation, public release or GitHub push is
performed by this checkpoint.
