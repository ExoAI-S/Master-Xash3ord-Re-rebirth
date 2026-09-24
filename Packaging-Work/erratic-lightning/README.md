# Erratic Lightning: forward Gauss-style cast

Erratic Lightning still uses its original hit detection, damage, ramp, mana
cost, and target glow. Its cast event now sends a point beside the caster's
right hand and the hit point to the client. The shared lightning effect draws
a bright core and erratic arcs between those points, lights the muzzle and
impact, spawns impact sparks, and plays `magic/shock_noloop.wav`. The hand
charge stays between finger bones instead of reaching up into the sky.

The release's `scripts.pak` is not tracked as Git source. The three `.script`
files here are complete authored replacements for its entries. On a stopped
copy of the September 13 recovery package, run:

```powershell
python Packaging-Work\erratic-lightning\test_patch_pak.py C:\MSR\Portable-Package\game\msr\scripts.pak C:\MSR\Portable-Package\FN\content-manifest.json
python Packaging-Work\erratic-lightning\patch_pak.py C:\MSR\Portable-Package\game\msr\scripts.pak --manifest C:\MSR\Portable-Package\FN\content-manifest.json --backup C:\MSR-Erratic-Backup\scripts-before-erratic.pak
```

Create `C:\MSR-Erratic-Backup` first. The patcher accepts only the unmodified recovery PACK, preserves its 2,923
entries, updates the private FN script checksum, and can be rerun without
changing an already patched PACK. Keep the release ZIP and all private FN
profiles/data outside any distributable package.
