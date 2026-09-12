# MSR-on-PrimeXT build

This is the first explicit PrimeXT integration layer for Master Sword:
Rebirth. PrimeXT remains the parent CMake project; MSR is built as `msr_client`
and `msr_server` so it cannot replace PrimeXT's own sample targets by accident.

From a PrimeXT development environment, configure with:

```text
cmake -S . -B build-msr -G Ninja -DBUILD_GAME_LAUNCHER=OFF -DBUILD_UTILS=OFF -DBUILD_MSR_PORT=ON -DGAMEDIR=msr
cmake --build build-msr --parallel
```

The intended outputs are `build-msr/Release/msr/bin/client.dll` and
`build-msr/Release/msr/bin/ms.dll` (or the corresponding configuration
directory). Copy them into `game/msr/cl_dlls/` and `game/msr/dlls/`.

The existing `game_dir/msr/scripts.pak` must remain installed as
`game/msr/scripts.pak`. Do not merge it with PrimeXT's material files under
`scripts/`; those are a separate engine material system.

On Windows, `Build-MSR-Port.cmd` performs the same x86 Release build from any
checkout location. It discovers the local Visual Studio Build Tools, CMake,
and Ninja installations and creates a fresh `build-msr-local` cache, so a
handoff copied from another PC does not reuse absolute paths from that PC.

`Stage-Renderer-Assets.ps1` copies PrimeXT's renderer resources into the
portable MSR game directory without overwriting existing MSR artwork. It also
generates material response metadata from the model files already shipped by
the game. The stable renderer ignores these extra files; the hybrid renderer
will consume them as its integration lands.

The MSR x86 client and server targets now compile and run against the bundled
Xash runtime. Enhanced adds the encounter director, its VGUI control panel,
external model textures and the chat wrapping fix. Release function symbols
and linker maps are retained next to the build outputs for crash diagnosis.
PrimeXT's advanced rendering callback and physics remain unintegrated; the
working MSR targets do not by themselves establish compatibility with those
subsystems. See the project-root `START-HERE.md` for version switching and
`Packaging-Work/VALIDATION.md` for test evidence and limits.
