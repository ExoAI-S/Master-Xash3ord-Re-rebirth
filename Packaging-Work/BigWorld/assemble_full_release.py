"""Add a tested Big World installer and updated source to a complete MSR ZIP.

Requires 7-Zip on Windows. This never packages a live game directory or private saves.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
PACKAGE_NAME = "MSR-BigWorld-20260927-1032"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True, help="verified September 24 full-game ZIP")
    parser.add_argument("--package", type=Path, required=True, help="tested Big World package directory")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sevenzip", type=Path, default=Path(r"C:\Program Files\7-Zip\7z.exe"))
    args = parser.parse_args()
    if args.package.name != PACKAGE_NAME or not (args.package / "package.json").is_file():
        parser.error("Expected the tested MSR-BigWorld-20260927-1032 package directory")
    for path in (args.base, args.sevenzip):
        if not path.is_file():
            parser.error(f"Missing {path}")
    with zipfile.ZipFile(args.base) as base:
        names = set(base.namelist())
        if "MSR/MSR-Launcher.exe" not in names or "MSR/Portable-Package/game/msr/scripts.pak" not in names:
            parser.error("Base ZIP is not a complete MSR archive")
    overlay = json.loads((HERE / "source-overlay.json").read_text(encoding="utf-8"))
    if overlay["base"] != "v2026.09.24-erratic-gauss":
        parser.error("Unexpected source overlay base")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        parser.error(f"Output already exists: {args.output}")
    with tempfile.TemporaryDirectory(prefix="msr-bigworld-release-") as tmp:
        root = Path(tmp) / "MSR"
        root.mkdir()
        shutil.copytree(args.package, root / PACKAGE_NAME)
        shutil.copytree(HERE, root / "Packaging-Work" / "BigWorld", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for entry in overlay["files"]:
            rel = Path(entry["path"])
            src = REPO / rel
            normalized = src.read_bytes().replace(b"\r\n", b"\n")
            if hashlib.sha256(normalized).hexdigest() != entry["sha256_lf"]:
                raise RuntimeError(f"Source overlay hash mismatch: {rel}")
            dst_rel = Path("Source", *rel.parts[1:]) if rel.parts[0] == "Full-Source" else rel
            dst = root / dst_rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        (root / "Install-BigWorld.cmd").write_text(
            "@echo off\r\ncall \"%~dp0" + PACKAGE_NAME + "\\Install-BigWorld.cmd\" %*\r\n",
            encoding="ascii",
        )
        (root / "Uninstall-BigWorld.cmd").write_text(
            "@echo off\r\ncall \"%~dp0" + PACKAGE_NAME + "\\Uninstall-BigWorld.cmd\" %*\r\n",
            encoding="ascii",
        )
        (root / "START-HERE.md").write_text(
            "# MSR Five-Region Big World\n\n"
            "Extract the **entire** ZIP into a writable folder. Run **Install-BigWorld.cmd** in the MSR folder once and wait for ‘Installed’. "
            "Then open **MSR-Launcher.exe** or **Play-MSR.cmd**. To join a friend, everyone must run this same update. "
            "If hosting, stop the realms before installing and restart them afterward.\n\n"
            "The installation keeps your character and FN database, creates a rollback backup, and can be reversed with **Uninstall-BigWorld.cmd**. "
            "Keep an older game folder or backup until you have verified your character. Run **Create-Desktop-Shortcuts.cmd** after moving the extracted folder.\n\n"
            "The five connected regions are Edana, Thornlands, Edana sewers, Northern Thornlands, and Helena. "
            "See **MSR-BigWorld-20260927-1032/README.txt** for play and hosting details.\n",
            encoding="utf-8",
        )
        # The archive's entries predate this update. Force all staged entries to be newer,
        # so 7-Zip replaces the base source files and START-HERE.md.
        for path in root.rglob("*"):
            if path.is_file():
                os.utime(path, None)
        shutil.copy2(args.base, args.output)
        subprocess.run([str(args.sevenzip), "u", "-tzip", "-y", str(args.output), "MSR"], cwd=tmp, check=True)
    with zipfile.ZipFile(args.output) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"Corrupt archive member: {bad}")
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise RuntimeError("Archive has duplicate entries")
        required = [
            "MSR/Install-BigWorld.cmd",
            "MSR/START-HERE.md",
            f"MSR/{PACKAGE_NAME}/package.json",
            f"MSR/{PACKAGE_NAME}/payload/game/msr/maps/edana.bsp",
            "MSR/Portable-Package/game/msr/scripts.pak",
        ]
        if any(name not in names for name in required):
            raise RuntimeError("Missing required release member")
        private = [name for name in names if name.lower().endswith(("player-profile.json", ".sqlite3", ".db"))]
        if private:
            raise RuntimeError(f"Private data found: {private[:3]}")
    print(f"Verified {len(names)} entries: {args.output} ({args.output.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
