# UI update validation

The release uses the frozen candidate09 client/server Debug build. Its native
MScript event prototype is OFF. The original player model is retained.

## Completed build and source checks

- Both game DLLs built with the Debug configuration; matching PDBs are included.
  The existing SDK retains its static /MT runtime. Conditional _DEBUG FN log
  markers are consequently absent; engine validation uses HTTP and item state.
- All 544 recorded build-source inputs match the source in the full game ZIP.
  The Git source checkout preserves existing line endings on 29 files; their
  source text is identical after newline normalization.
- Progression tests: 1,019,028 assertions; actual extracted entrypoint tests:
  1,487 assertions, including 90 Torch/Demon Claws ratio comparisons.
- Equipment tests: 59 assertions. Initialization/metadata tests: 312 assertions,
  reproducing the old zero-slot failure and checking all 21 authored positions.
- Atlas helper checks and decoding of all 16 packaged tiles passed.
- FN manager tests: 198 assertions across the frozen candidate08 control,
  corrected standalone build and legacy build. These reproduce the local-host
  queue failure and check initialization, request ownership, allocation errors,
  character-load status rollback, teardown and reinitialization.
- Two independent read-only advisers each hashed 1,210 frozen review payloads
  and found no established actionable equipment regression. They did not run
  the game or certify release readiness.

## Completed isolated engine observations

The menu and cross-realm observations below were recorded against candidate08.
Candidate09 carries that UI forward and fixes the standalone listen-host FN
worker initialization. Its separate engine verification is recorded below.

- All 21 equipment positions appear with authored capacities and actual item
  requirements. An incompatible vest-to-head drop sends no equip command.
- A hand-to-chest drag equips the vest; a Heavy Backpack-to-chest drag transfers
  and equips it. Subsequent server updates confirm worn state and chest/arms
  occupancy. The Small Sack correctly refuses an item too large for it.
- The P binding was queried as inventory. Inventory, Character and World Map
  render in the engine with the fantasy decoration. Atlas fit, zoom, centering,
  route view and the current-region glow were exercised.
- Bounded selection/lifecycle callbacks passed. The closed menu's refresh
  counter remained unchanged during waiting and a fullscreen resolution change;
  reopening worked. These tests invoke game callbacks, not physical OS input.
- A complete synthetic character was saved, the game restarted, and the 750-byte
  character reloaded with its equipped vest and backpack intact.
- Separate isolated dedicated realm A loaded the synthetic FN character and
  saved its vest inside the backpack. Realm B loaded that stored state, equipped
  the vest through the real bag drag path, and saved it. After restarting the
  isolated FN service, a new realm A process loaded the worn vest again. Engine
  state, FN GET/PUT responses, persisted blob changes and revisions were checked.

All character and FN tests used disposable profiles and a separate database.
They did not edit the public host's character records. Failed initial listen
and profile-configuration attempts were retained as test history; a console
setinfo value is overridden by the client's durable player-profile.json.

## Candidate09 local FN correction

The standalone listen host loaded the existing synthetic FN character through
an actual GET, selected it and saved a changed vest/backpack state with a PUT.
A fresh listen process retrieved that saved state. Dragging the vest from the
backpack to its chest slot produced one transfer/equip batch, followed by a
server update confirming the worn item and chest/arms occupancy. All seven
menu callback checks passed. A separate dedicated process retrieved the state
saved by the listen host, changed the item and saved it through FN again.

The isolated test processes were stopped and their ports released afterward.
These tests used HTTP results, item state and persisted database revisions;
conditional FN diagnostic markers were unavailable in this build.

## Limits

Physical mouse/keyboard capture, extended combat, all shops/storage interactions
and every character/item combination were not exhaustively tested. The atlas
has 19 approximate named-region pins; unplaced interiors remain in the route
view. Its 76-node/112-edge public route graph is authored topology, including
arrival warnings, rather than a playthrough of every transition.

Legacy weapon subskills normalize into one base skill when loaded and saved.
Synthetic migration tests do not establish preservation of every historical
save. Keep raw pre-update saves and the matching previous release for recovery;
reverting DLLs alone cannot reconstruct the former unequal subskill values.

Development-Tests contains the harness sources and portable runners. The final
packaged top-level runner was executed once in a separate clean directory:
1,019,028 progression, 1,487 entrypoint, 59 equipment, 312 initialization and
198 FN assertions passed, as did the atlas self-test and all 16 tile decodes.
All 668 copied inputs matched the staged files and remained unchanged. This
validates the new packaged paths without adding generated files to the ZIP.
The repository version needs the matching release's atlas assets for decoding;
the full game ZIP contains those assets.

## Frozen runtime hashes

| File | SHA-256 |
| --- | --- |
| client.dll | 690de2e8643dd6d5975b75ad1a3d17b24cbbe1b5477b80dd8dd2d243f64bf70d |
| ms.dll | b31598eadaa033eef83127f26bb007477979f9ed0c0dabad58a0a52ef0fd2097 |
| scripts.pak | 5168d4d04a6207bf48769f69eca9ddfb26209adbfe4a2366f6be93bcd7079d9b |

The complete package's final files and hashes are recorded in
PACKAGE-MANIFEST.json, FINAL-MERGE.json and DEBUG-BUILD.json.
