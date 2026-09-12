# MSR on PrimeXT port

This tree is a PrimeXT-base staging copy of the Master Sword: Rebirth source.
The original archive, extracted MSR source, and PrimeXT checkout are left
unchanged.

## Integration decision

PrimeXT is the target Xash3D game SDK. MSR's proprietary MScript runtime and
the existing `scripts.pak` remain the source of gameplay behavior during the
first port phase. AngelScript is kept as a separate optional subsystem; it is
not used as an automatic MScript translator.

## Option 1 implementation state

The PrimeXT root now has an explicit `BUILD_MSR_PORT` option and an
`msr_port/` CMake target. When enabled, it imports the MSR client, server,
shared, proprietary MScript, and AngelScript source sets as separate
`msr_client` and `msr_server` DLL targets. The supplied `scripts.pak` is staged
under `game_dir/msr/`.

The targets remain separate from PrimeXT's own `client` and `server` targets,
so the first compile pass can identify ABI and header differences without
overwriting the PrimeXT sample game.

The staging tree is based on PrimeXT commit `46fb05b41e58ed887718649e1720313baaac9a35`.

## MScript runtime facts

- The handoff `scripts.pak` is a PACK container with 2,923 entries. The two
  added entries implement Edana's guard-triggered Orc raid.
- Normal script loads read from the pack through `CGameGroupFile`.
- With `ms_dev_mode 1`, scripts under `test_scripts/` can override packed
  content.
- Script events cross server/client scope, so the initial port must preserve
  script IDs and `CallScriptEvent` behavior before visual or physics changes.

## Current integration boundary

The two MSR targets currently compile MSR's own game code and engine headers
inside the PrimeXT CMake project. They do not yet incorporate PrimeXT's client
renderer, materials implementation, entity extensions, or PhysX integration.
Building these targets is a baseline for further port work, not a completed
full-feature PrimeXT port.

PrimeXT is a game SDK/toolkit for Xash3D FWGS. The `engine/` directory here
contains SDK headers, not the engine implementation. The separate Xash3D
runtime supplied in the user's archive is staged under `runtime/` for testing.
Its game DLLs are replaced with the new outputs only after a successful build.

## Build recovery, September 12, 2026

Visual Studio 2026 x86 Build Tools, local CMake/Ninja, and vcpkg are available.
The earlier environment/toolchain statements above are superseded by this
verified local setup.

The port target now uses the original MSR compile definitions, static CRT,
Windows libraries, and server exports file. It excludes the commented-out
SteamServerHelper/entities sources and includes the client weapons source.
The extra CLIENT_DLL/GAME_DLL definitions from the initial staging pass have
been removed to match the original build configuration.

The next integration work is to merge and validate PrimeXT's renderer and
server features against MSR's entity, animation, HUD, networking, and MScript
interfaces. That work remains separate from proving that the baseline DLLs
build and launch.

## Edana event checkpoint, September 12, 2026

The packaged runtime adds `edana/game_master.script` and
`edana/raid_guard.script`. Captain Brenn is dynamically created near Edana's
arrival area. His dialogue menu requests a small Orc raid with randomized
approach angles, party-size scaling, completion tracking, timeout cleanup, and
a three-minute cooldown.

Both dedicated realms loaded Edana, verified the new FN content checksum, and
preloaded the guard and Orc model. The dialogue trigger and combat sequence
still require an interactive play test. Existing Edana scripts also report
several legacy parser/conflict messages. Development was paused for handoff
before those unrelated messages or the full PrimeXT renderer/physics merge
were addressed.

## Local continuation, September 12, 2026

The copied handoff now has a relocatable Windows build entry point at
`msr_port/Build-MSR-Port.cmd`. A clean x86 Release cache on the new PC built
all 347 MSR client/server steps successfully instead of reusing the previous
machine's absolute CMake paths.

The stable portable launch path now executes `masterpiece.cfg` by default.
That profile enables supported 16x anisotropic filtering, 4x MSAA, extended
lighting, lit sprites, detailed textures, high model selection, and MSR
reflections. A live client launched from the handoff, connected to Realm One,
completed HUD video initialization, and spawned in Edana.

`Stage-Renderer-Assets.ps1` staged PrimeXT's 64 GLSL files, renderer lookup
textures, particles, and material definitions without overwriting MSR art. A
generated `msr_models.mat` contains 5,885 conservative bindings extracted from
703 shipped studio models. The first higher-resolution equipment asset is a
1,254-square shortsword diffuse plus normal and gloss/ORM maps for both the
floor and first-person model names.

These resources are ready for the hybrid renderer but do not imply that the
renderer callback is complete. The next code milestone remains merging
PrimeXT's `HUD_GetRenderInterface` and initialization path while retaining
MSR's HUD, view logic, attachment renderer, and scripting entry points. See
`msr_port/GRAPHICS_ROADMAP.md`.
