"""Build the Big World package that players and hosts install into their MSR folder.

  python make_bigworld_package.py [--base <MSR folder>]   (default base: C:\\MSR, read only)

Takes the current builds (build\\edana_bigworld5.bsp and its detail list and neighbour patches,
the ms.dll/client.dll in src\\build-bw, bigworld-runtime\\msr\\delta.lst, the sandbox FN service)
and writes dist\\<package>\\ plus dist\\<package>.zip:
  Install-BigWorld.cmd / Uninstall-BigWorld.cmd / Check-BigWorld.cmd, README.txt,
  installer\\bigworld_setup.py, payload\\ (paths relative to Portable-Package), package.json.
package.json records every payload file's hash and the base MSR release's scripts.pak and engine
hashes, which the installer requires on the target so host and players run the same game.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import shutil
import sys
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGIONS = ["edana", "thornlands", "edanasewers", "thornlands_north", "helena"]  # their own .ent patches go
BASE_FILES = ["game/msr/scripts.pak", "game/xash.dll", "game/xash3d.exe", "game/ref_gl.dll"]
EDICTS = 4096


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


INSTALL_CMD = r"""@echo off
setlocal
rem MSR Big World: install into the MSR folder this package folder sits in (or C:\MSR).
rem Close MSR first (and stop your realms with Stop-Host.cmd if you host).
set "HERE=%~dp0"
if exist "%HERE%..\Portable-Package\runtime\python.exe" (
  "%HERE%..\Portable-Package\runtime\python.exe" "%HERE%installer\bigworld_setup.py" {action} %*
  goto done
)
if exist "C:\MSR\Portable-Package\runtime\python.exe" (
  "C:\MSR\Portable-Package\runtime\python.exe" "%HERE%installer\bigworld_setup.py" {action} %*
  goto done
)
where py >nul 2>nul && ( py -3 "%HERE%installer\bigworld_setup.py" {action} %* & goto done )
where python >nul 2>nul && ( python "%HERE%installer\bigworld_setup.py" {action} %* & goto done )
echo Could not find Python. Put this folder inside your MSR folder (next to MSR-Launcher.exe) and run it again.
:done
echo.
pause
"""

README = """MSR Big World ({package})
=================================================

One seamless world: Edana, the Thornlands, the Sewers of Edana, Northern Thornlands and
the Town of Helena are walked between without loading screens. The world remembers boss
kills (bosses come back after a while), you log back in exactly where you logged out, and
empty areas reset on their own after about 10 minutes.

Everyone playing together (the host and every player who joins) needs this same package.


TO PLAY (joining a friend's realm)
----------------------------------
1. Close MSR completely.
2. Put this whole folder ({package}) inside your MSR folder - the folder that has
   MSR-Launcher.exe in it. (If your MSR folder is C:\\MSR, it may also stay anywhere else.)
3. Double-click Install-BigWorld.cmd and wait for "Installed".
4. Start MSR as usual and join the realm (Join server / Realm One or Realm Two).

The installer refuses to install into a different MSR release than the host's, and changes
nothing if it refuses. Your own characters and saves are not touched.


TO HOST (running the realms)
----------------------------
1. Stop your realms first (Stop-Host.cmd), and close the game.
2. Install exactly as above.
3. Start your realms again (Start-Host.cmd or the launcher's host controls). They start in
   Big World mode by themselves (the installer adds game\\msr\\bigworld.enable).
Your FN character service is updated too (it gains the world-state store; its database is
upgraded in place on the first start, and the installer keeps a copy from before).


TO REMOVE
---------
Close MSR (stop realms), then double-click Uninstall-BigWorld.cmd. Every replaced file comes
back from the backup the installer made next to your MSR folder
(<MSR folder>-BigWorld5-Backup-<date>). Check-BigWorld.cmd shows what is installed.


What it installs (paths inside Portable-Package)
------------------------------------------------
game\\msr\\maps\\edana.bsp          the merged world (installed as Edana)
game\\msr\\maps\\edana_detail.txt   its detail textures
game\\msr\\maps\\*.ent              neighbouring maps lead into the world
game\\msr\\dlls\\ms.dll, cl_dlls\\client.dll (+ .pdb)  game code with regions, world state,
                                  exact logout spot and boss respawn timers
game\\msr\\delta.lst                wider network fields the big world needs
game\\msr\\liblist.gam              edicts {edicts}
game\\msr\\bigworld.enable          servers start in Big World mode
FN\\fn_server.py, FN\\test_fn.py     character service with world state
It also removes the separate patches of the maps that are now part of the world, and approves
the new world map in FN\\content-manifest.json.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default=r"C:\MSR", help="the MSR release the package is for (read only)")
    args = parser.parse_args()
    base = Path(args.base) / "Portable-Package"

    files = {  # payload path (relative to Portable-Package) -> source
        "game/msr/maps/edana.bsp": ROOT / "build" / "edana_bigworld5.bsp",
        "game/msr/maps/edana_detail.txt": ROOT / "build" / "edana_bigworld5_detail.txt",
        "game/msr/dlls/ms.dll": ROOT / "src" / "build-bw" / "Debug" / "msr" / "bin" / "ms.dll",
        "game/msr/dlls/ms.pdb": ROOT / "src" / "build-bw" / "Debug" / "msr" / "bin" / "ms.pdb",
        "game/msr/cl_dlls/client.dll": ROOT / "src" / "build-bw" / "Debug" / "msr" / "bin" / "client.dll",
        "game/msr/cl_dlls/client.pdb": ROOT / "src" / "build-bw" / "Debug" / "msr" / "bin" / "client.pdb",
        "game/msr/delta.lst": ROOT / "bigworld-runtime" / "msr" / "delta.lst",
        "FN/fn_server.py": ROOT / "sandbox" / "FN" / "fn_server.py",
        "FN/test_fn.py": ROOT / "sandbox" / "FN" / "test_fn.py",
    }
    for ent in sorted((ROOT / "build" / "ent-patches-bigworld5").glob("*.ent")):
        files[f"game/msr/maps/{ent.name}"] = ent
    for rel, src in files.items():
        if not src.is_file():
            print(f"missing build output for {rel}: {src}")
            return 1
    for m in REGIONS:
        if f"game/msr/maps/{m}.ent" in files:
            print(f"the patch set contains {m}.ent, but {m} is a region of the world")
            return 1

    world_crc = crc32(files["game/msr/maps/edana.bsp"])
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    package = f"MSR-BigWorld-{stamp}"
    dist = ROOT / "dist"
    out = dist / package
    if out.exists():
        shutil.rmtree(out)
    (out / "installer").mkdir(parents=True)
    meta = {"package": package, "built": stamp, "world_crc32": world_crc, "edicts": EDICTS, "regions": REGIONS,
            "base": {}, "files": {}}
    for rel in BASE_FILES:
        p = base / rel
        if not p.is_file():
            print(f"base MSR release is missing {p}")
            return 1
        meta["base"][rel] = sha256(p)

    for rel, src in files.items():
        dst = out / "payload" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        meta["files"][rel] = {"bytes": dst.stat().st_size, "sha256": sha256(dst)}
    enable = out / "payload" / "game" / "msr" / "bigworld.enable"
    enable.write_text("MSR Big World: servers started from this game folder run in Big World mode "
                      "(large coordinates). Removed by Uninstall-BigWorld.cmd.\n", encoding="ascii")
    meta["files"]["game/msr/bigworld.enable"] = {"bytes": enable.stat().st_size, "sha256": sha256(enable)}

    shutil.copy2(ROOT / "tools" / "bigworld_setup.py", out / "installer" / "bigworld_setup.py")
    (out / "package.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    for name, action in (("Install-BigWorld.cmd", "install"), ("Uninstall-BigWorld.cmd", "uninstall"),
                         ("Check-BigWorld.cmd", "status")):
        (out / name).write_text(INSTALL_CMD.replace("{action}", action).replace("\n", "\r\n"), encoding="ascii")
    (out / "README.txt").write_text(README.format(package=package, edicts=EDICTS).replace("\n", "\r\n"), encoding="utf-8")

    zpath = dist / f"{package}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(out.rglob("*")):
            if p.is_file():
                z.write(p, Path(package) / p.relative_to(out))
    print(f"{out}\n{zpath} ({zpath.stat().st_size / 1e6:.1f} MB), world crc {world_crc}, {len(meta['files'])} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
