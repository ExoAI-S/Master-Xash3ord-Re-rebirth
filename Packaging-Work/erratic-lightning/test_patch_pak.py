"""Verify the Erratic Lightning update only changes its three PACK scripts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import tempfile
import zlib

from patch_pak import ORIGINAL_SHA256, patch, read_entries


def main(pak: Path, manifest: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="msr-erratic-") as temporary:
        root = Path(temporary)
        original = pak.read_bytes()
        test_pak = root / "scripts.pak"
        test_manifest = root / "content-manifest.json"
        shutil.copy2(pak, test_pak)
        shutil.copy2(manifest, test_manifest)

        patch(test_pak, test_manifest, None)
        modified = test_pak.read_bytes()
        old_entries = {name: data for _, name, data in read_entries(original)}
        new_entries = {name: data for _, name, data in read_entries(modified)}
        changed = {name for name in old_entries if old_entries[name] != new_entries[name]}
        assert changed == set(ORIGINAL_SHA256), changed
        assert json.loads(test_manifest.read_text())["scripts_crc32"] == (
            zlib.crc32(modified) & 0xFFFFFFFF
        )
        assert b"vectoradd l.end $vec(0,0,4096)" not in new_entries[
            "items/magic_hand_lightning_weak.script"
        ]
        assert b"handmagic_createbeam_to_sky" not in new_entries[
            "items/magic_hand_lightning_weak_cl.script"
        ]
        assert b"beam_points sfx.start sfx.end GAUSS_CORE_SPRITE" in new_entries[
            "effects/sfx_lightning.script"
        ]
        assert b"svplaysound 0 0 SOUND_GAUSS" in new_entries[
            "items/magic_hand_lightning_weak.script"
        ]
        assert b"handmagic_createchargebeam 35 38" in new_entries[
            "items/magic_hand_lightning_weak_cl.script"
        ]
        patch(test_pak, test_manifest, None)
        assert test_pak.read_bytes() == modified
    print("Erratic Lightning PACK patch passed (three entries, CRC, idempotence)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pak", type=Path)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    main(args.pak, args.manifest)
