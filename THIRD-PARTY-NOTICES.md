# Component licenses and attribution

This repository preserves the notices included in the supplied game package.
It does not grant a new blanket license over the combined game, engine,
libraries, tools or assets. Copyright remains with each component's owners.

| Component | Existing notice or source |
| --- | --- |
| Master Sword: Rebirth and Valve Half-Life SDK-derived code | [Full-Source/msr_source/LICENSE](Full-Source/msr_source/LICENSE); also [MSR-LICENSE.txt](Portable-Package/source/MSR-LICENSE.txt) |
| Xash3D FWGS | [Bundled GPL-3.0 text](Portable-Package/source/Xash3D-GPL-3.0.txt), source-file notices and [engine source](Engine-Source/Xash3D) |
| PrimeXT SDK | Original copyright/license notices in [Full-Source](Full-Source), including individual source headers and dependencies |
| Newly written private FN service and host scripts | [Portable-Package/FN/LICENSE](Portable-Package/FN/LICENSE), whose final paragraph defines its scope |
| Tracy | [Full-Source/external/tracy/LICENSE](Full-Source/external/tracy/LICENSE) and its dependency notices |
| vcpkg | [Full-Source/external/vcpkg/LICENSE.txt](Full-Source/external/vcpkg/LICENSE.txt) and individual port notices |
| Other engine, SDK and launcher dependencies | Their retained license files, source headers and runtime notices in the full release |
| Models, textures, maps, music, sounds and other game data | Their respective original authors and applicable notices; not relicensed by the SDK, engine or private FN license |

The Valve SDK license permits free distribution subject to its terms; it is
not an MIT license for the whole project. The private FN MIT notice expressly
excludes game, engine, SDK, asset and runtime files from its coverage.

Recorded upstream baselines from the supplied package:

- Master Sword: Rebirth: `2c28f72ec916a2c5d449bc94628c0fb9436a1c6a`
- PrimeXT integration base: `46fb05b41e58ed887718649e1720313baaac9a35`
- Xash3D FWGS runtime base: `21aab6ca1e4e780f91c1e6d43095a41b4541588c`

The source trees also contain this integration's later changes. Their original
Git histories are not embedded in the source snapshot. See
[Portable-Package/source/BUILD.md](Portable-Package/source/BUILD.md) and
[Full-Source/PORTING_STATUS.md](Full-Source/PORTING_STATUS.md) for provenance.

Upstream contribution policies remain attached to their respective projects.
For example, the vendored gl4es contribution documents describe submissions to
gl4es; this publication imports its dependency snapshot and does not submit a
change or pull request to that upstream project.
