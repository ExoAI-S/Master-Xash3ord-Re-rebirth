# Five-region Big World release

This snapshot accompanies `v2026.09.27-bigworld5`. It adds the latest Big World game and FN source to `Full-Source` and `Portable-Package/FN`. The full-game release archive starts with the complete `v2026.09.24-erratic-gauss` game and adds the tested `MSR-BigWorld-20260927-1032` installer. Players must run `Install-BigWorld.cmd` after extracting the archive; this creates a machine-local rollback backup and enables the new map. The separate 50 MB patch archive is for existing September 24 installations.

`source-overlay.json` records the source files copied from Claude Code's `MSR-BigWorld` project and their SHA-256 hashes after normalizing line endings to LF. `edana_bigworld5.json` and `edana_bigworld5-report.json` describe the five-region layout and map validation. The `tools` directory is preserved from that standalone project. Its build and packaging commands expect the standalone project's `src`, `build`, `sandbox`, and `bigworld-runtime` directory layout; use `assemble_full_release.py` here to combine a verified base game ZIP and a tested Big World package into the full distributable.

The release package deliberately excludes local FN databases, character profiles, logs, and the install marker. Its installer builds a fresh marker and backup on each player's PC. The September 24 release remains available as the downgrade base.

Validation before release: latest Debug DLL build succeeded, the map report recorded zero hull/extent/PVS mismatches, 21 FN tests passed with one skipped, and installing then uninstalling the final patch in a scratch MSR directory restored all baseline files byte-for-byte.
