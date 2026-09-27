"""MSR Big World setup: install, remove or check the 5-region Big World in an MSR folder.

Ships inside the Big World package (installer\\bigworld_setup.py next to payload\\ and
package.json) and runs with the Python that MSR itself bundles. What it does, in an MSR folder
(the one with MSR-Launcher.exe and Portable-Package):

install    - refuses while the game, a realm or FN runs from that folder, and refuses an MSR
             release other than the one the package was built for (scripts.pak and the engine
             must match);
           - takes an older Big World install (the 3-region one) back to stock first;
           - backs up every file it replaces or removes into <MSR folder>-BigWorld5-Backup-<time>,
             plus a copy of the FN database;
           - installs the world map and its detail list, the neighbour-map patches (removing the
             patches of maps that are now regions), ms.dll and client.dll, the widened delta.lst,
             edicts 4096 in liblist.gam, bigworld.enable (servers the launcher starts then run in
             Big World mode), the FN service with world state, and the new map's checksum in the
             FN content manifest.
install --portable
           - the same, but keeps the backup inside the MSR folder (<MSR folder>\\BigWorld-Backup,
             recorded relative to it) instead of next to it: for a complete game shipped with Big
             World already installed, which then still uninstalls wherever a player extracts or
             moves it. Refuses if that BigWorld-Backup folder already exists.
uninstall  - puts every backed-up file back and removes what the install added (after a portable
             install also the BigWorld-Backup folder, once every file is back).
status     - says what is installed.

Usage: python bigworld_setup.py install|uninstall|status [--root <MSR folder>] [--force] [--portable]
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import zlib
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent  # the unpacked package: installer\, payload\, package.json
MARKER = "bigworld-install.json"                    # in game\msr\maps, as the 3-region installer wrote it
PORTABLE_BACKUP = "BigWorld-Backup"                 # install --portable: the backup inside the MSR folder


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


def say(text: str = "") -> None:
    print(text, flush=True)


class SetupError(Exception):
    pass


# ---------------------------------------------------------------------------
# where things are
# ---------------------------------------------------------------------------
class Install:
    def __init__(self, root: Path):
        self.root = root
        self.pkg = root / "Portable-Package"
        self.game = self.pkg / "game"
        self.msr = self.game / "msr"
        self.maps = self.msr / "maps"
        self.fn = self.pkg / "FN"
        self.manifest = self.fn / "content-manifest.json"
        self.marker = self.maps / MARKER
        if not (self.game / "xash3d.exe").is_file() or not (self.msr / "liblist.gam").is_file():
            raise SetupError(f"{root} is not an MSR folder (no Portable-Package\\game\\xash3d.exe).")

    def rel(self, path: Path) -> str:
        return str(path.relative_to(self.root))


def find_root(given: str | None) -> Path:
    candidates = [Path(given)] if given else [PACKAGE.parent, Path(r"C:\MSR")]
    for c in candidates:
        if (c / "Portable-Package" / "game" / "xash3d.exe").is_file():
            return c.resolve()
    if given:
        raise SetupError(f"{given} is not an MSR folder (it needs Portable-Package\\game\\xash3d.exe).")
    raise SetupError("Could not find your MSR folder. Put this package folder inside your MSR folder "
                     "(the one with MSR-Launcher.exe) and run it again, or pass --root <MSR folder>.")


def running_under(root: Path) -> list[str]:
    """Game, realm and FN processes started from this MSR folder."""
    script = ("Get-CimInstance Win32_Process | Select-Object ProcessId,Name,ExecutablePath,CommandLine "
              "| ConvertTo-Json -Compress")
    result = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True)
    if result.returncode != 0:
        raise SetupError("Could not check whether MSR is running; no files were changed.")
    processes = json.loads(result.stdout) if result.stdout.strip() else []
    if isinstance(processes, dict):
        processes = [processes]
    root_prefix = str(root).rstrip("\\/").lower() + "\\"
    fn_script = str(root / "Portable-Package" / "FN" / "fn_server.py").lower()
    hits = []
    for process in processes:
        if process.get("ProcessId") == os.getpid():
            continue
        exe = (process.get("ExecutablePath") or "").lower()
        cmd = (process.get("CommandLine") or "").lower()
        name = (process.get("Name") or "").lower()
        if name in ("xash3d.exe", "msr-launcher.exe") and exe.startswith(root_prefix):
            hits.append(exe)
        elif name in ("python.exe", "pythonw.exe") and fn_script in cmd:
            hits.append(exe or name)
    return hits


# ---------------------------------------------------------------------------
# the older (3-region) install
# ---------------------------------------------------------------------------
def undo_three_region(ins: Install) -> None:
    """The first Big World installer: restore its backup and drop its entity patches."""
    record = json.loads(ins.marker.read_text(encoding="utf-8"))
    backup = Path(record.get("backup", ""))
    if not backup.is_dir():
        raise SetupError(f"An older Big World install is here, but its backup ({backup}) is missing. "
                         "Nothing was changed.")
    say(f"Removing the older Big World install first (backup {backup}) ...")
    for name in ("edana.bsp", "edana_detail.txt"):
        if (backup / name).is_file():
            shutil.copy2(backup / name, ins.maps / name)
    if (backup / "content-manifest.json").is_file():
        shutil.copy2(backup / "content-manifest.json", ins.manifest)
    replaced = set(record.get("replaced_ent_patches", []))
    for name in record.get("ent_patches", []):
        if name in replaced and (backup / name).is_file():
            shutil.copy2(backup / name, ins.maps / name)
        elif (ins.maps / name).is_file():
            (ins.maps / name).unlink()
    ins.marker.unlink()


# ---------------------------------------------------------------------------
# install / uninstall
# ---------------------------------------------------------------------------
def load_package() -> dict:
    meta = json.loads((PACKAGE / "package.json").read_text(encoding="utf-8"))
    for rel, info in meta["files"].items():
        p = PACKAGE / "payload" / rel
        if not p.is_file() or p.stat().st_size != info["bytes"]:
            raise SetupError(f"The package is incomplete ({rel}). Extract the whole ZIP again.")
    return meta


def check_release(ins: Install, meta: dict, force: bool) -> None:
    """Our DLLs and map are built for one MSR release: its scripts and engine must match."""
    wrong = []
    for rel, expected in meta["base"].items():
        p = ins.pkg / rel
        if not p.is_file() or sha256(p) != expected:
            wrong.append(rel)
    if wrong and not force:
        raise SetupError("This MSR folder is a different MSR release than the Big World package was made for "
                         f"({', '.join(wrong)} differ). Install the same MSR release as the host first. "
                         "Nothing was changed.")
    if wrong:
        say(f"WARNING: different MSR release ({', '.join(wrong)}); installing anyway (--force).")


def patch_liblist(path: Path, edicts: int) -> None:
    text = path.read_text(encoding="latin-1")
    new, n = re.subn(r'(?im)^(\s*edicts\s+)"?\d+"?', lambda m: f'{m.group(1)}"{edicts}"', text)
    if n == 0:
        new = text.rstrip("\r\n") + f'\r\nedicts "{edicts}"\r\n'
    path.write_text(new, encoding="latin-1")


def backup_dir(ins: Install, record: dict) -> Path:
    """The install's backup; a portable install records it relative to the MSR folder, wherever that now is."""
    if not record.get("backup_relative"):
        return Path(record["backup"])
    name = record["backup"]
    if name in ("", ".", "..") or Path(name).name != name:
        raise SetupError(f"The Big World marker names an unexpected backup folder ({name}). Nothing was changed.")
    return ins.root / name


def remove_tree(path: Path) -> None:
    """shutil.rmtree that also takes read-only files (copy2 keeps the read-only flag of what it backed up)."""
    for p in path.rglob("*"):
        if p.is_file() and not os.access(p, os.W_OK):
            os.chmod(p, stat.S_IREAD | stat.S_IWRITE)
    shutil.rmtree(path)


def install(ins: Install, force: bool, portable: bool = False) -> None:
    meta = load_package()
    if ins.marker.is_file():
        record = json.loads(ins.marker.read_text(encoding="utf-8"))
        if record.get("package") == meta["package"]:
            say(f"This Big World ({meta['package']}) is already installed. Run uninstall first to reinstall.")
            return
        if record.get("package"):
            raise SetupError(f"Another Big World package ({record['package']}) is installed. Uninstall it first "
                             "with that package's Uninstall-BigWorld.cmd.")
    check_release(ins, meta, force)
    if portable and (ins.root / PORTABLE_BACKUP).exists():
        raise SetupError(f"{ins.root / PORTABLE_BACKUP} already exists (the backup of an earlier portable install?). "
                         "Move or delete it first. Nothing was changed.")
    if ins.marker.is_file():
        undo_three_region(ins)

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = ins.root.parent / f"{ins.root.name}-BigWorld5-Backup-{stamp}"
    if portable:
        backup = ins.root / PORTABLE_BACKUP  # travels with the MSR folder; the marker records it relative
    backup.mkdir(parents=True)
    say(f"Backup: {backup}")

    # What the install replaces or removes, each backed up first
    targets = {rel: ins.pkg / rel for rel in meta["files"]}
    targets["game/msr/liblist.gam"] = ins.msr / "liblist.gam"
    targets["FN/content-manifest.json"] = ins.manifest
    removed = [f"game/msr/maps/{m}.ent" for m in meta["regions"] if (ins.maps / f"{m}.ent").is_file()]
    for rel in removed:
        targets[rel] = ins.pkg / rel
    existed = {}
    for rel, path in targets.items():
        existed[rel] = path.is_file()
        if path.is_file():
            dst = backup / "files" / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dst)
    db = ins.fn / "data" / "FN.sqlite3"
    if db.is_file():
        (backup / "fn-database").mkdir()
        for suffix in ("", "-wal", "-shm"):
            p = db.with_name(db.name + suffix)
            if p.is_file():
                shutil.copy2(p, backup / "fn-database" / p.name)
    record = {"package": meta["package"], "installed": stamp, "backup": str(backup),
              "existed": existed, "removed": removed, "world_crc32": meta["world_crc32"]}
    if portable:
        record["backup"], record["backup_relative"] = PORTABLE_BACKUP, True
    (backup / MARKER).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    # Marked before anything changes, so an install that stops halfway can still be undone
    ins.marker.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    # Install
    for rel in meta["files"]:
        src, dst = PACKAGE / "payload" / rel, ins.pkg / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        if dst.suffix.lower() == ".ent":
            now = time.time()
            os.utime(dst, (now, now))  # the engine uses a .ent only if it is newer than the .bsp
        if sha256(dst) != meta["files"][rel]["sha256"]:
            raise SetupError(f"{rel} did not copy correctly. Run uninstall to go back to the backup.")
    for rel in removed:
        (ins.pkg / rel).unlink()
    patch_liblist(ins.msr / "liblist.gam", meta["edicts"])
    if ins.manifest.is_file():
        manifest = json.loads(ins.manifest.read_text(encoding="utf-8-sig"))
        manifest.setdefault("maps", {})["edana"] = meta["world_crc32"]
        tmp = ins.manifest.with_suffix(".tmp")
        tmp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, ins.manifest)
    say(f"Installed {meta['package']}: {len(meta['files'])} files, {len(removed)} old region patches removed.")
    say("Start the game (or your host) as usual. Everyone who joins needs this same package installed.")


def uninstall(ins: Install) -> None:
    if not ins.marker.is_file():
        say("No Big World install found here.")
        return
    record = json.loads(ins.marker.read_text(encoding="utf-8"))
    if not record.get("package"):
        say("This is the older 3-region Big World install. Removing it ...")
        undo_three_region(ins)
        say("Removed.")
        return
    backup = backup_dir(ins, record)
    portable = bool(record.get("backup_relative"))
    if not (backup / "files").is_dir() and any(record["existed"].values()):
        raise SetupError(f"The backup {backup} is missing; nothing was changed.")
    for rel, was in record["existed"].items():
        path = ins.pkg / rel
        if was:
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup / "files" / rel, path)
        elif path.is_file():
            path.unlink()
    if portable:
        # A portable install's backup is deleted below, so every file must really be back first
        bad = [rel for rel, was in record["existed"].items() if (ins.pkg / rel).is_file() != was
               or (was and sha256(ins.pkg / rel) != sha256(backup / "files" / rel))]
        if bad:
            raise SetupError(f"{', '.join(bad)} did not come back from {backup}. The backup and the install "
                             "record are kept; run uninstall again.")
    ins.marker.unlink()
    say(f"Big World removed; files restored from {backup}.")
    if not portable:
        say("Your FN saves are kept as they are (a copy from before the install is in that backup).")
        return
    try:
        remove_tree(backup)
        say(f"The backup folder {backup} is removed.")
    except OSError as exc:
        say(f"Could not remove the backup folder {backup} ({exc}); delete it yourself.")
    say("Your FN saves are kept as they are.")


def status(ins: Install) -> None:
    if not ins.marker.is_file():
        say("Big World: not installed.")
        return
    record = json.loads(ins.marker.read_text(encoding="utf-8"))
    if not record.get("package"):
        say(f"Big World: the older 3-region install (installed {record.get('installed')}).")
        return
    world = ins.maps / "edana.bsp"
    ok = world.is_file() and crc32(world) == record.get("world_crc32")
    say(f"Big World: {record['package']} installed {record['installed']}; world map {'OK' if ok else 'CHANGED since install'}.")
    if record.get("backup_relative"):
        backup = backup_dir(ins, record)
        say(f"Backup: {backup} (portable, inside the MSR folder{'' if backup.is_dir() else '; MISSING'})")
    else:
        say(f"Backup: {record['backup']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["install", "uninstall", "status"])
    parser.add_argument("--root", help="the MSR folder (default: the folder this package is in, or C:\\MSR)")
    parser.add_argument("--force", action="store_true", help="install on a different MSR release anyway")
    parser.add_argument("--portable", action="store_true",
                        help="install: keep the backup inside the MSR folder (BigWorld-Backup), so a game shipped "
                             "with Big World installed still uninstalls after it is extracted or moved anywhere")
    args = parser.parse_args()
    try:
        ins = Install(find_root(args.root))
        say(f"MSR folder: {ins.root}")
        if args.action != "status":
            busy = running_under(ins.root)
            if busy:
                raise SetupError("Close MSR first: the game, a realm or FN is still running from this folder "
                                 f"({len(busy)} processes). Use Stop-Host.cmd for realms. Nothing was changed.")
        {"install": lambda: install(ins, args.force, args.portable), "uninstall": lambda: uninstall(ins), "status": lambda: status(ins)}[args.action]()
        return 0
    except SetupError as exc:
        say(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
