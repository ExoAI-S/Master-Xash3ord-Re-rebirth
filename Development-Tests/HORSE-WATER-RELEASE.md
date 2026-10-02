# Horse water release and preview controls

Entering waist-deep water previously called the general forced mount release.
That returned the visual horse to its stable or spawn point while leaving the
player at the water entry. A visible horse left underwater also cannot be
remounted because `TryMount` requires dry ground.

The water-only release now keeps the player in place and returns the horse to
its most recent grounded, dry position and orientation. Successful mounting
initializes that position after `GroundSpot` validates it. `Follow` updates it
only while the rider is grounded and the horse's feet are dry. Water release
uses the existing rider, effect and camera cleanup; death, disconnect, disabled
mounts and other forced release reasons retain their previous policy.

The separate preview control report was reproduced as absent engine bindings:
Q and physical 3 were both null. MSR's shipped `gfx/shell/kb_def.lst` defaults
are `q -> use` (sheath/store/wear) and `3 -> inventory`. They are distinct from
`e -> +use` (world/horse Use) and `g -> menu main`. No generic effect or menu
state reset is part of this change.

The preview's `valve.rc` calls `stuffcmds`, which only marks the command line
as pending. The engine executes the startup script, fallback `config.cfg` and
`userconfig.d` before processing the pending command-line arguments. The
absence of Q/3 bindings does not establish a mount or startup-order defect.

The earlier two-key launcher proposal is superseded by the human-requested
original Master Sword controls: the final launcher executes
`msr_original_controls.cfg` after `plains_play.cfg`. This preset contains only
57 bindings, the original Mouse4 press/release aliases and `unbindall`.
Q is `use`, 3/I is `inventory`, P is `playerinfo`, and E is `+use`.
PAUSE uses the shipped keyboard definition's `snapshot` rather than a saved
`kill` command. No graphics, network, profile or other cvar resets are included.
The installation did not rewrite existing saved configurations; when the player
later exits normally, the engine may naturally save the new bindings.

## Verification status

The isolated x86 Debug server compiles with the reviewed rotating-door Use fix.
The 2,002 production geometry checks pass. The door bundle and first water
proposal are preserved, including a hashed snapshot of all 330 build inputs;
the dry-bank successor also has a complete snapshot of those tracked inputs.

Native acceptance passed for natural creek entry, release at the water-entry
position, the same horse returned to its latest dry bank position, return to
shore and remount/dismount, and three ordinary mount/dismount cycles. Repeated
house-door Use and a fresh inn regression passed with the final server.

The reviewed SDL event integration fixture exercised normal engine key routing
for Q sheath/store and 3 inventory open/close, with independent logical outcome
checks. This is engine event integration, not physical OS keyboard verification.
All 57 original bindings passed source/static review; runtime functionality of
all 57 keys, full mouse inventory interaction and rendered inventory pixels
remain unverified. Gamepad START is an inherited, unverified binding.

The final Debug server and matched PDB were installed in both private runtimes
on October 2, 2026, with reviewed map and controls components, verified backups,
and a Daragoth-only FN manifest refresh. No-client postflight confirmed exact
loaded core/map identities, current local FN validation and enabled FN flags.
The stopped-session preservation comparison passed for 84 existing settings,
profile and ordinary-installation files and semantic FN users, characters and
revisions (seven character rows); it does not claim world-state preservation.
The one private player client was opened afterward at the human's request.
No public release or ordinary-installation update has been made.
