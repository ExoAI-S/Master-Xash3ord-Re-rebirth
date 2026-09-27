"""Install or remove the combined Edana + Thornlands world in an MSR installation.

install:   backs up the files it replaces, installs the world as maps/edana.bsp,
           its merged detail-texture list, the neighbour-map entity patches, and
           approves the new edana.bsp checksum in the FN content manifest.
uninstall: restores the most recent backup and removes the entity patches.

The game, realms and FN must be stopped. The original edana.bsp/thornlands.bsp
must match the ones the world was built from, so an unexpected install is
refused rather than overwritten.

Usage: python install_bigworld.py install|uninstall|status [--root C:\\MSR]
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
BUILD = HERE / "build"
REFERENCE = HERE / "reference"
MARKER = "bigworld-install.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def crc32(path: Path) -> int:
    crc = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            crc = zlib.crc32(chunk, crc)
    return crc & 0xFFFFFFFF


def running_under(root: Path) -> list[str]:
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "Get-CimInstance Win32_Process | ForEach-Object { $_.ExecutablePath + '|' + $_.CommandLine }"],
                         capture_output=True, text=True).stdout
    hits = []
    needle = str(root).lower()
    for line in out.splitlines():
        exe, _, cmd = line.partition("|")
        if needle in exe.lower() or (needle in cmd.lower() and ("xash" in cmd.lower() or "fn_server" in cmd.lower())):
            hits.append(line.strip())
    return hits


def paths(root: Path):
    pkg = root / "Portable-Package"
    msr = pkg / "game" / "msr"
    return pkg, msr, msr / "maps", pkg / "FN" / "content-manifest.json"


def install(root: Path) -> None:
    pkg, msr, maps, manifest_path = paths(root)
    world = BUILD / "edana_world.bsp"
    detail = BUILD / "edana_world_detail.txt"
    patches = sorted((BUILD / "ent-patches").glob("*.ent"))
    for p in (maps / "edana.bsp", maps / "thornlands.bsp", maps / "edanasewers.bsp", manifest_path, world, detail):
        if not p.exists():
            raise SystemExit(f"missing: {p}")
    if (maps / MARKER).exists():
        raise SystemExit("The combined world is already installed. Run uninstall first to reinstall.")
    busy = running_under(root)
    if busy:
        raise SystemExit("Stop the game, realms and FN first:\n  " + "\n  ".join(busy))
    for name in ("edana.bsp", "thornlands.bsp", "edanasewers.bsp"):
        if sha256(maps / name) != sha256(REFERENCE / name):
            raise SystemExit(f"{name} in this install is not the original the world was built from; refusing.")

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = root.parent / f"{root.name}-BigWorld-Backup-{stamp}"
    backup.mkdir(parents=True)
    shutil.copy2(maps / "edana.bsp", backup / "edana.bsp")
    if (maps / "edana_detail.txt").exists():
        shutil.copy2(maps / "edana_detail.txt", backup / "edana_detail.txt")
    shutil.copy2(manifest_path, backup / "content-manifest.json")
    existing_ent = [p.name for p in patches if (maps / p.name).exists()]
    for name in existing_ent:
        shutil.copy2(maps / name, backup / name)

    shutil.copy2(world, maps / "edana.bsp")
    shutil.copy2(detail, maps / "edana_detail.txt")
    now = time.time()
    for p in patches:
        shutil.copy2(p, maps / p.name)
        os.utime(maps / p.name, (now, now))   # the engine only reads patches newer than the BSP

    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    manifest["maps"]["edana"] = crc32(maps / "edana.bsp")
    tmp = manifest_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, manifest_path)

    record = {"installed": stamp, "backup": str(backup), "world_sha256": sha256(world),
              "ent_patches": [p.name for p in patches], "replaced_ent_patches": existing_ent}
    (maps / MARKER).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    (backup / MARKER).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    check = pkg / "FN" / "check_content.py"
    if check.exists():
        python = pkg / "runtime" / "python.exe"
        subprocess.run([str(python if python.exists() else sys.executable), str(check)], check=True, cwd=pkg)
    print(f"Installed. Backup: {backup}")


def uninstall(root: Path) -> None:
    pkg, msr, maps, manifest_path = paths(root)
    marker = maps / MARKER
    if not marker.exists():
        raise SystemExit("The combined world is not installed here.")
    busy = running_under(root)
    if busy:
        raise SystemExit("Stop the game, realms and FN first:\n  " + "\n  ".join(busy))
    record = json.loads(marker.read_text(encoding="utf-8"))
    backup = Path(record["backup"])
    shutil.copy2(backup / "edana.bsp", maps / "edana.bsp")
    if (backup / "edana_detail.txt").exists():
        shutil.copy2(backup / "edana_detail.txt", maps / "edana_detail.txt")
    for name in record["ent_patches"]:
        if name in record["replaced_ent_patches"]:
            shutil.copy2(backup / name, maps / name)
        elif (maps / name).exists():
            (maps / name).unlink()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    manifest["maps"]["edana"] = crc32(maps / "edana.bsp")
    tmp = manifest_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, manifest_path)
    marker.unlink()
    print("Original Edana restored; neighbour patches removed.")


def status(root: Path) -> None:
    _, _, maps, _ = paths(root)
    marker = maps / MARKER
    print(marker.read_text(encoding="utf-8") if marker.exists() else "Combined world: not installed")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["install", "uninstall", "status"])
    ap.add_argument("--root", type=Path, default=Path(r"C:\MSR"))
    args = ap.parse_args()
    {"install": install, "uninstall": uninstall, "status": status}[args.command](args.root.resolve())


if __name__ == "__main__":
    main()
