# MSR PrimeXT graphics integration

The stable package currently uses MSR's original client renderer. PrimeXT's
source, shaders, and tools are present, but its render callback is not yet
linked into the MSR client DLL. The integration is intentionally incremental
so character saves, attachments, HUD menus, mirrors, and multiplayer remain
testable after every step.

## Active Enhanced artwork — 2026-09-12

`stage_hd_materials.py` installs external diffuse textures through Xash's
existing `materials/models/.../*.tga` loader. Enhanced enables
`host_allow_materials 1`; log verification confirms replacements on the actual
player `human/reference.mdl`, guard armor and orc face. The legacy male1 body
also has a matching replacement. Model files, rigs and animations are
unchanged. `Stable-Base` retains the original assets.

## Stage 1: stable high-quality profile

- Load the existing `masterpiece.cfg` from every local and Internet launcher.
- Use 16x anisotropic filtering, 4x MSAA, extended light sampling, lit sprites,
  detailed textures, high model selection, and MSR reflections by default.
- Keep the current known-good client and server DLLs.

## Stage 2: PrimeXT renderer runtime

- Merge `HUD_GetRenderInterface`, renderer initialization, world rendering,
  and post-processing into the MSR client target.
- Retain MSR's HUD, input, view calculation, attachment-aware studio path,
  MScript, and AngelScript entry points.
- Stage PrimeXT GLSL, material definitions, renderer lookup textures, and
  particle definitions in the MSR game directory.
- First acceptance map: Edana. Required checks are character selection,
  inventory, held weapons, bags, sheaths, mirrors, combat, map transition,
  and reconnecting to both FN realms.

## Stage 3: materials and lighting

- Apply generated studio-model material bindings for metal, wood, glass,
  cloth, skin, vegetation, and stone.
- Author normal, gloss/ORM, emissive, and height maps for a small reviewed set
  of Edana surfaces and frequently seen equipment.
- Add map-owned cubemaps, shadowed dynamic lights, bloom, tone mapping, SSAO,
  and color correction with conservative defaults and a low-spec preset.

## Stage 4: model upgrades

- Upgrade one complete vertical slice first: player body, starter shortsword,
  sack, sheath, one town NPC, and the rat.
- Preserve skeleton names, animation sequences, bodygroups, hitboxes,
  attachment indices, and MScript model paths so upgraded assets remain
  plug-compatible with existing gameplay.
- Add LODs and PrimeXT external texture maps before expanding to other armor,
  weapons, monsters, and props.

## Stage 5: gameplay-facing PrimeXT features

- Add Aurora particles for magic, impacts, weather, fires, and ambience.
- Introduce PhysX only for non-authoritative props and effects first; combat,
  inventory, movement, and persistence remain server-authoritative.
- Use ropes, portals, projected lights, terrain layers, and parented entities
  in new or rebuilt maps after the original campaign maps pass regression.
