# Master Xash3ord Re-rebirth

An experimental Windows build of **Master Sword: Rebirth** using a PrimeXT SDK
integration and Xash3D FWGS, with a private FN character service, two-realm local
hosting, Dungeon Master controls, and a preserved Stable version for rollback.

The September 12, 2026 release contains the complete playable package. This
repository contains the corresponding source, build inputs, configuration,
documentation and regression checks extracted from that package.

## Download and play

Open the [DM Debug release](https://github.com/ExoAI-S/Master-Xash3ord-Re-rebirth/releases/tag/v2026.09.12-dm-debug).
Download both numbered ZIP parts and **Restore-Game-Zip.cmd** into the same
folder. Run the command file to join and verify the original ZIP, then extract
the entire ZIP into a writable folder before launching the game.

The parts are named:

- `MSR-PrimeXT-DM-Magic-Fix-Debug-Complete-2026-09-12.zip.001`
- `MSR-PrimeXT-DM-Magic-Fix-Debug-Complete-2026-09-12.zip.002`

Do not try to extract a numbered part on its own. The joined ZIP is
3,151,413,773 bytes, with SHA-256:

```text
8f62cafa56c06e1efaa907677b6bcb4b52ac53cc6c1b70130fdcd28c4d922b81
```

Inside the extracted `MSR-PrimeXT-DM` folder:

- **MSR-Launcher.exe** opens the launcher and server choices.
- **Play-Enhanced.cmd** starts local FN and two local realms, then joins the first.
- **Play-Realm-One.cmd** and **Play-Realm-Two.cmd** join the shared Internet realms.
- **Dungeon-Master.cmd** opens controls for your own Enhanced realms.
- **Create-Desktop-Shortcuts.cmd** creates the game, realm and DM shortcuts.
- **Play-Stable.cmd** switches local hosting to the preserved base version.

For local DM access, join your realm, open the DM controls, refresh players,
grant your player slot Dungeon Master, then press **G** in game and choose
**Dungeon Master**. See [START-HERE.md](START-HERE.md) for the complete player,
hosting, persistence and rollback guide. The shared realms require their host
PC and Internet tunnels to be online. Local FN and shared-realm FN store
characters separately.

GitHub's automatic **Source code** download is a developer snapshot. It does
not contain the executable game, sound, model and map payloads. Use the release
assets for the full game; both Enhanced and Stable are included there.

## What is included

Enhanced adds the encounter director and Dungeon Master panel, optional random
encounters, Captain Brenn's Edana entrance encounter, HD textures for existing
models, and fixes to chat wrapping, standalone player identities, local FN
setup and spell effects. Stable retains the original game files and provides a
rollback path through the launcher.

The Enhanced client and server are **Debug** builds with matching PDB symbols
and linker maps. The latest changes initialize magic sprites before submitting
them to the engine, check optional dynamic-light arguments, and retain script
getter return values so spell endpoints and positional sound coordinates stay
valid. [DEBUG-VALIDATION.md](DEBUG-VALIDATION.md) records the observed tests and
their limits, including the unresolved diagnosis of a friend's access violation.

The MSR game targets compile within the PrimeXT project. PrimeXT's advanced
renderer callbacks, PhysX, new meshes and new animations remain future work;
the presence of their SDK source or staged material resources does not mean
those features are active in this build. See
[PORTING_STATUS.md](Full-Source/PORTING_STATUS.md) and the
[graphics roadmap](Full-Source/msr_port/GRAPHICS_ROADMAP.md).

## Source layout

| Path | Purpose |
| --- | --- |
| `Full-Source/msr_source` | Modified MSR client, server, MScript runtime and build input libraries |
| `Full-Source/msr_port` | PrimeXT integration targets, encounter scripts, material tools and art inputs |
| `Full-Source` | Parent PrimeXT SDK and vendored dependency snapshots |
| `Engine-Source/Xash3D` | Xash3D FWGS source and dependency snapshots |
| `Launcher` | Native Windows launcher source and Python host/diagnostic helpers |
| `Portable-Package/FN` | Enhanced private FN service, protocol implementation and tests |
| `Stable-Base/FN` | Preserved Stable service implementation |
| `Portable-Package/source`, `Stable-Base/source` | Earlier standalone patches, source notes and notices |
| `Packaging-Work` | Regression checks and verified FN save-transfer support |
| `SOURCE-INVENTORY.json` | Byte hashes linking extracted source files to the original release ZIP |

The tree keeps release-relative paths so the source can be compared with an
extracted game package. Runtime configuration and shaders are retained, but
game binaries, maps, models, sounds, debug outputs and bundled language runtimes
are in the complete release. Imported third-party source retains its upstream
documentation; older upstream build instructions may describe a different
layout or the original project rather than this integration.

## Build the Enhanced game DLLs on Windows

Install Visual Studio Build Tools with the C++ desktop workload, CMake 3.24 or
newer, Ninja, Git and Python. Use an **x86 Native Tools Command Prompt** and run
the following from the repository root. The shipped game and its libraries are
32-bit; a 64-bit game DLL cannot replace them.

The vendored vcpkg directory is a source snapshot without its Git history.
Use a separate vcpkg checkout at the baseline recorded in the SDK manifest for
versioned dependency resolution:

```bat
git clone https://github.com/microsoft/vcpkg.git .dependencies\vcpkg
git -C .dependencies\vcpkg checkout 962e5e39f8a25f42522f51fffc574e05a3efd26b
call .dependencies\vcpkg\bootstrap-vcpkg.bat -disableMetrics
cmake -S Full-Source -B build\msr-debug -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_TOOLCHAIN_FILE="%CD%/.dependencies/vcpkg/scripts/buildsystems/vcpkg.cmake" -DVCPKG_TARGET_TRIPLET=x86-windows -DBUILD_CLIENT=OFF -DBUILD_SERVER=OFF -DBUILD_UTILS=OFF -DBUILD_GAME_LAUNCHER=OFF -DBUILD_MSR_PORT=ON -DENABLE_PHYSX=OFF -DGAMEDIR=msr
cmake --build build\msr-debug --target msr_client msr_server --parallel
```

The configure step downloads build dependencies. Outputs are in
`build/msr-debug/Debug/msr/bin`. With the game and its servers stopped, copy
`client.dll` and `client.pdb` to an extracted release's
`Portable-Package/game/msr/cl_dlls`, and `ms.dll` and `ms.pdb` to its
`Portable-Package/game/msr/dlls`. Keep the matching maps for crash diagnosis.
Preserve the Stable folder when testing changes.

The release's `scripts.pak` remains required for gameplay. It is supplied in
the full package, along with the authored Edana script additions in source.
To use the optional `msr_verify_scripts` build target, first copy that pack to
`Full-Source/game_dir/msr/scripts.pak`. Do not replace it with PrimeXT material
files from the separate `scripts` directory.

The package's original `Full-Source/msr_port/Build-MSR-Port.cmd` entry point is
also preserved. Its default configuration is Release; `-Configuration Debug`
selects Debug. It expects a usable vendored vcpkg installation or the original
dependency cache. The explicit commands above are intended for a fresh source
checkout.

## Launcher, FN and checks

`Launcher/Source/Build-Launcher.cmd` compiles the native Debug launcher using
Windows' .NET Framework C# compiler. Copy the resulting `MSR-Launcher.exe` and
PDB into an extracted release to run it with the included runtime files.
See [the launcher source notes](Launcher/Source/README.md).

FN uses Python's standard library and binds to loopback by default. Its
[protocol notes](Portable-Package/PROTOCOL.md) explain compatibility and the
separate private profile identities. The complete package's launcher creates
host settings and player identities on first use; existing users' profiles,
character databases, passwords and tunnel credentials are not included.

From the repository root, these isolated checks use temporary state or compile
small native fixtures instead of launching the public realms:

```bat
python Portable-Package\FN\test_fn.py
python Packaging-Work\test_transfer_fn_state.py
python Packaging-Work\run_script_effect_tests.py
python Packaging-Work\run_script_return_lifetime_tests.py
```

The last two commands require the x86 MSVC developer prompt. Other preserved
packaging tests may expect a complete extracted release or the original
`friend-support` staging layout; their source describes those requirements.
The repository extraction was verified against the release archive; a full
fresh-checkout game/engine rebuild is separate from the release's recorded
Debug build and playtest evidence.

For an engine rebuild, see the Windows Waf instructions in
[Engine-Source/Xash3D/README.md](Engine-Source/Xash3D/README.md) and the exact
engine revision/attachment patch details in
[Portable-Package/source/BUILD.md](Portable-Package/source/BUILD.md).
The engine is a separate build from the PrimeXT/MSR game DLLs.

## Credits and licensing

This is a community integration, with upstream work from
[MSRevive/MasterSwordRebirth](https://github.com/MSRevive/MasterSwordRebirth),
[SNMetamorph/PrimeXT](https://github.com/SNMetamorph/PrimeXT),
[FWGS/xash3d-fwgs](https://github.com/FWGS/xash3d-fwgs), Valve and their
respective contributors. It is not an official FN service or an official
release from those upstream projects.

There is no single license applied to the entire bundle. MSR/Valve SDK terms,
Xash3D GPL notices, the private FN service's scoped MIT license, and individual
dependency/asset notices remain separate. See
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md). Source availability does not
relicense game art, audio or other third-party content.
