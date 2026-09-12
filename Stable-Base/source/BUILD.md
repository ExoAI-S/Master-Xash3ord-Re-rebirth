# Source and rebuild

Game base: https://github.com/MSRevive/MasterSwordRebirth/tree/2c28f72ec916a2c5d449bc94628c0fb9436a1c6a

`MasterSwordRebirth-standalone-source.zip` contains the complete game repository's tracked files with this port applied, plus StandaloneIdentity.h. `standalone.patch` records the changes against the base. The original MSR/Valve SDK license is retained in the source and in MSR-LICENSE.txt.

Changes:

- `MSR_STANDALONE=ON` removes the Steam client link dependency, callbacks, achievements, Steam presence, and Discord's Steam launch registration. Normal non-standalone builds keep their original behavior.
- A 32-character random lowercase hexadecimal profile key is passed as `_fnid` user info. Its stable FNV-1a 64-bit hash with the high bit set fills FN's existing decimal `steamid` field. Missing/invalid keys and duplicate simultaneous profiles are rejected; the public Steam auth-string conversion is not used by this build.
- Restrict the Win32 generator-platform setting to Visual Studio generators so Ninja can compile using the x86 developer environment.

From an x86 Visual Studio developer prompt, with CMake and Ninja on PATH:

```text
cmake -S MasterSwordRebirth -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DMSR_STANDALONE=ON
cmake --build build --parallel 6
```

The produced `bins/release/client.dll` goes in `game/msr/cl_dlls/`; `ms.dll` goes in `game/msr/dlls/`. The handoff `scripts.pak` uses MSR's PACK container and contains 2,923 script entries, including `edana/game_master.script` and `edana/raid_guard.script` for the guard-triggered Orc raid. `patch_scripts_pak.py` makes one source-level compatibility correction in `items/base_item_extras.script`: the delayed call to the server-only `vanish_item` event is now guarded by `game.serverside`. This prevents every client-side item spawn, including Rat Pelt pickup, from reporting `event vanish_item NOT FOUND`. The event implementation remains server-only and server behavior is unchanged.

The package starts from the official Xash3D engine build, with `ref_gl.dll` rebuilt from the same commit using the included `Xash3D-attachment.patch`. The patch lets client-created MSR equipment follow the HUD character and rejects MSR's negative transient entity number before Xash indexes its remap table.

- Source: https://github.com/FWGS/xash3d-fwgs/tree/21aab6ca1e4e780f91c1e6d43095a41b4541588c
- Original binary: https://github.com/FWGS/xash3d-fwgs/releases/download/continuous/xash3d-fwgs-win32-i386.7z
- SHA256 of the downloaded archive: `9ce06ae0e285b0721032f4b0aba2538463318f48b85b2a439303a5c3fe795f33` (matched GitHub's asset digest).
- Build number 4179; September 9, 2026 release. The moving `continuous` URL may later serve a different build; verify the hash.

For the engine source and all its submodules, clone the official repository, check out the exact commit above, run `git -c core.longpaths=true submodule update --init --recursive`, then apply `Xash3D-attachment.patch`. Configure a 32-bit MSVC release build with the official Waf instructions and build target `ref_gl`; copy `build/ref/gl/ref_gl.dll` to `game/ref_gl.dll`. GitHub's source ZIP alone omits engine submodules. This package retains engine notices and provides GPL-3.0 in this directory.

FN is an independent Python standard-library implementation in `FN/fn_server.py`; its tests and private-profile helper are included. The protocol sources and official FN background are linked in PROTOCOL.md. The runtime is the official Python 3.14.7 Windows AMD64 embeddable runtime, which retains its license.

This personal installation combines third-party engine code, game source, libraries, and the assets you supplied. Those components retain their original licenses and notices; this port does not relicense the game assets or imply official FN affiliation.
