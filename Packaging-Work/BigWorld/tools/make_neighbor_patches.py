"""Write engine entity patches (maps/<name>.ent) that route neighbour-map travel into the world map.

Xash3D FWGS reads maps/<name>.ent instead of the BSP entity lump when the
.ent file is newer than the .bsp, so the neighbour maps' BSP files (and their
FN checksums) stay untouched. Only transitions whose destination spawn cluster
exists in the world map are redirected.

Usage: python make_neighbor_patches.py <maps_dir> <world.bsp> <out_dir> old=new [old=new ...]
                                        [trans:wrong=right ...]

trans:wrong=right fixes a neighbour's arrival name while redirecting it, for
exits that name a spawn the destination never had (bloodrose sends players to
thornlands_north "from_bloodrose"; the spawn there is "from_blood").
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from bsp30 import CONTENTS_SOLID, BSP, format_entities, hull_point_contents, parse_entities
import struct

TRANSITION_CLASSES = {"msarea_transition", "mstrig_changelevel", "trigger_changelevel"}


def entity_text(path: Path) -> str:
    data = path.read_bytes()
    if len(data) < 128:
        return ""  # stub files such as edanasewers_old.bsp
    ofs, ln = struct.unpack_from("<ii", data, 4)
    return data[ofs:ofs + ln].rstrip(b"\0").decode("latin-1")


def transition_boxes(bsp_path: Path) -> list[tuple]:
    """World-space bounds of every msarea_transition brush in a map."""
    b = BSP.load(bsp_path)
    boxes = []
    for e in b.entities:
        m = e.get("model") or ""
        if e.classname == "msarea_transition" and m.startswith("*"):
            mod = b.models[int(m[1:])]
            o = [float(x) for x in (e.get("origin") or "0 0 0").split()]
            boxes.append(tuple(mod.mins[k] + o[k] for k in range(3)) + tuple(mod.maxs[k] + o[k] for k in range(3)))
    return boxes


def add_spectator_spot(bsp_path: Path, ents: list) -> str | None:
    """MSR parks not-yet-loaded players on a random ms_player_spawn when a map has
    no ms_player_spec. If that spawn is inside an exit trigger, the exit fires
    before the character loads and loading then wipes the pending destination
    (CAreaTransition::OnControls ignores character state). Give such maps a
    spectator spot outside every exit."""
    if any(e.classname == "ms_player_spec" for e in ents):
        return None
    b = BSP.load(bsp_path)
    boxes = transition_boxes(bsp_path)

    def inside(p, pad=48.0):
        return any(all(bx[k] - pad <= p[k] <= bx[k + 3] + pad for k in range(3)) for bx in boxes)

    candidates = [e for e in ents if e.classname == "info_player_start"] + \
                 [e for e in ents if e.classname in ("ms_player_spawn", "ms_player_begin")]
    for c in candidates:
        p = [float(x) for x in (c.get("origin") or "0 0 0").split()]
        if not inside(p):
            ents.append(parse_entities('{ "classname" "ms_player_spec" "origin" "%s" "angles" "%s" }'
                                       % (c.get("origin"), c.get("angles") or "0 0 0"))[0])
            return c.get("origin")
    # Every spawn is at an exit: step away from one to open floor space a standing
    # player hull fits in (hull 1), clear of every exit.
    head = b.models[0].headnode[1]
    for c in candidates:
        p = [float(x) for x in (c.get("origin") or "0 0 0").split()]
        for dist in (96, 160, 256, 384):
            for ang in range(0, 360, 45):
                q = [p[0] + dist * math.cos(math.radians(ang)), p[1] + dist * math.sin(math.radians(ang)), p[2]]
                if inside(q) or hull_point_contents(b, head, q, 1) == CONTENTS_SOLID:
                    continue
                origin = " ".join(f"{v:g}" for v in q)
                ents.append(parse_entities('{ "classname" "ms_player_spec" "origin" "%s" "angles" "%s" }'
                                           % (origin, c.get("angles") or "0 0 0"))[0])
                return origin + f" ({dist} from {c.get('message') or c.classname})"
    return "no safe spot"


def main():
    maps_dir, world_path, out_dir = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    redirect = dict(arg.split("=", 1) for arg in sys.argv[4:] if not arg.startswith("trans:"))
    aliases = dict(arg[6:].split("=", 1) for arg in sys.argv[4:] if arg.startswith("trans:"))
    world = BSP.load(world_path)
    world_spawns = {e.get("message") for e in world.entities if e.classname == "ms_player_spawn"}
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {}
    for bsp in sorted(maps_dir.glob("*.bsp")):
        if bsp.stem.lower() in redirect or bsp.stem.lower() in {v.lower() for v in redirect.values()}:
            continue
        ents = parse_entities(entity_text(bsp))
        changes = []
        for e in ents:
            if e.classname not in TRANSITION_CLASSES:
                continue
            dest = (e.get("destmap") or "").lower()
            if dest not in redirect:
                continue
            trans = e.get("desttrans") or ""
            fixed = aliases.get(trans, trans)
            if fixed not in world_spawns:
                changes.append({"transition": e.get("targetname"), "skipped": f"no spawn '{fixed}' in world"})
                continue
            e.set("destmap", redirect[dest])
            if fixed != trans:
                e.set("desttrans", fixed)
            changes.append({"transition": e.get("targetname"), "destmap": f"{dest} -> {redirect[dest]}",
                            "desttrans": trans if fixed == trans else f"{trans} -> {fixed}"})
        if any("destmap" in c for c in changes):
            spec = add_spectator_spot(bsp, ents)
            if spec:
                changes.append({"added_ms_player_spec": spec})
            (out_dir / (bsp.stem + ".ent")).write_bytes(format_entities(ents).rstrip(b"\0"))
        if changes:
            report[bsp.stem] = changes
    (out_dir / "neighbor-patches.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
