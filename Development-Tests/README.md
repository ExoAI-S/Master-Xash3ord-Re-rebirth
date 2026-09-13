# Development regression sources

These sources preserve the candidate-08 progression, equipment, initialization, and atlas regression harnesses and add candidate-09's FN listen-server regression. All six C++ harness files are byte-for-byte copies from their frozen review bundles. Python extraction logic, arithmetic adapters, assertions, and compiler flags are preserved. Path adaptations use the adjacent packaged source/reference directories; generated FN provenance is written into its build directory. The top-level runner appends the FN suite after the two existing suites.

The portable ZIP uses the adjacent `Source/msr_source/src` tree; the Git repository uses `Full-Source/msr_source/src`. Atlas decoding reads `Portable-Package/game/msr/gfx/vgui/msr_world_atlas_*.tga`. All 16 tiles are included in the complete ZIP. The Git repository intentionally excludes the compiled atlas art: before running its equipment/atlas suite or the top-level runner, extract the matching complete candidate-09 UI release (its atlas tiles are unchanged from candidate-08) and copy only its 16 `msr_world_atlas_*.tga` files into that repository directory. The unified and FN suites do not need atlas art. These runners do not search an installed game or read player profiles.

## Run on Windows

Install Python 3 (available as `python`) and Visual Studio with the MSVC C++ workload, Windows SDK, and x86 build tools. The existing runners locate Visual Studio through its installed `vswhere.exe`, then initialize the x86 compiler environment. Run from a writable checkout/extraction:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Development-Tests\Run-Tests.ps1
```

Individual suites can be run through `unified/Run-Tests.ps1`, `equipment/Run-Tests.ps1`, and `fn-listen/Run-Tests.ps1`. Runners generate extraction includes, provenance JSON, and executables under each suite's `build` directory. The unified harness also writes two synthetic 19-byte skill records into `unified/fixtures`; these are generated test data, not character saves. No old binaries, build outputs, logs, or player fixtures are shipped here.

## What is exercised

- `unified`: XP migration and conservation, threshold and cap behavior, aliases, save-record roundtrips, and real `CStat` code. The entrypoint harness extracts actual current and baseline learning/getter/setter bodies, compares magic/Parry behavior, and adapts two script arithmetic slices for ratio compatibility checks.
- `equipment`: drag state and capacity checks, authoritative guarded use, dispatch order, input handling, and initialization/wear metadata extraction. The initialization harness reproduces the baseline missing-client-event behavior before checking the current path.
- `atlas_tests.cpp`: atlas helper self-test and decoding of all tiles named by the packaged chart header.
- `fn-listen`: unchanged extracted request-manager and character-load/rollback bodies, with inert curl/HTTP/engine boundaries. It reproduces candidate-08 listen rejection, checks candidate-09 listen/dedicated acceptance and preserved legacy restrictions, and covers duplicate loading, zero identity, queue failure, allocation failure, completion, ownership, clear, shutdown and reinitialization. The frozen build passed 198 assertions; these are not fresh packaging results.

Engine I/O is stubbed. These suites do not launch the game, render UI, execute the script VM, validate multiplayer sessions, or prove complete character-file compatibility.

## Frozen reference inputs

`reference/baseline-game` contains only the four original baseline C++ source files needed for differential extraction. `reference/scripts` contains only the four authored game scripts consumed by the existing arithmetic/wear adapters. They are test reference inputs, not a second installable game. Each is copied intact from candidate-08 and checked against its frozen manifest. `INPUT-PROVENANCE.json` records the relative original locations and hashes. Their original source hashes also match the baseline/script entries recorded by the frozen extraction provenance.

`reference/candidate08-game/server/fn/RequestManager.cpp` is the single additional frozen source needed for the FN failure control. The current manager declaration and FN load/rollback bodies come from the adjacent candidate-09 source. `fn-listen/INPUT-PROVENANCE.json` records these additions. No historical DLLs, HTTP responses, accounts, profiles, saves or runtime fixtures are required by this suite.

## Optional historical integrity checks

`equipment/source_checks.py` retains its original source assertions and both historical archive integrity checks. It is not called by `Run-Tests.ps1`. It is **not self-contained**: to run all its checks, supply the complete original `unified-v1` (candidate06) and `review-candidate-07` archives, including their `bundle-manifest.json` and every referenced payload. Set `MSR_CANDIDATE06_REVIEW` and `MSR_CANDIDATE07_REVIEW` to those directories, then run:

```powershell
python .\Development-Tests\equipment\source_checks.py
```

Missing archives cause an error; their checks are never skipped or reported as passing. Those rollback archives and their private/runtime evidence are not included in this regression-source folder.

## Packaging verification scope

Initial packaging checked frozen-source hashes, reference provenance, Python/PowerShell syntax and path availability. Final validation then ran this packaged top-level runner in a separate clean directory: 1,019,028 progression, 1,487 entrypoint, 59 equipment, 312 initialization and 198 FN assertions passed, plus the atlas self-test and all 16 tile decodes. All 668 copied inputs matched the staged package and remained unchanged; generated outputs stayed outside the distribution. Run the commands above to establish results for a recipient's compiler and extracted package.
