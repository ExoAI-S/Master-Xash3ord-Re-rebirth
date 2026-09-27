"""Build the Edana + Thornlands world map for Master Sword Rebirth.

Reads ../edana_world.json, merges the compiled maps with merge_world, turns
the Edana <-> Thornlands map transitions into walk-through teleports that
also re-tie the player's respawn point, verifies the result against the
source maps and writes the BSP, a merged detail-texture list and a report.

It also embeds a region table: one info_msr_region entity per region, right
after worldspawn, carrying the region's half-open cell of space (matching the
BSP join nodes), its tight world bounds and its per-map metadata, so the
server DLL can tell which region a point is in.

A "bosses" list in the config tags boss spawner templates with msr_boss,
msr_boss_cooldown and msr_boss_open for ms.dll's boss respawn timers (see
apply_bosses and msr_bosses.h).

Usage: python build_edana_world.py [config.json]
"""
from __future__ import annotations

import itertools
import json
import random
import re
import struct
import sys
import time
from pathlib import Path

from bsp30 import CONTENTS_SOLID, BSP, Entity, hull_point_contents
from merge_world import (RegionSource, WorldBuilder, f32, fmt_vec, process_entities, repair_extents,
                         verify)

ROOT = Path(__file__).resolve().parent.parent

REGION_CLASS = "info_msr_region"
REGION_LIMIT = 65536.0            # outer limit of the region cells
META_KEYS = ("title", "desc", "diff", "warnhp", "weather", "allownight", "skyname", "maxrange")
SCRIPT_KEYS = {("setvarg", "G_MAP_NAME"): "title", ("setvarg", "G_MAP_DESC"): "desc",
               ("setvarg", "G_MAP_DIFF"): "diff", ("setvarg", "G_WARN_HP"): "warnhp",
               ("const", "MAP_WEATHER"): "weather", ("const", "MAP_ALLOWNIGHT"): "allownight"}
WORLDSPAWN_META = {"maptitle": "title", "mapdesc": "desc", "hpwarn": "warnhp", "weather": "weather",
                   "skyname": "skyname", "MaxRange": "maxrange"}   # worldspawn keys are case-sensitive
META_DEFAULTS = {"warnhp": "0", "weather": "clear;clear;clear", "allownight": "1", "maxrange": "0"}
SCRIPT_LINE = re.compile(r"^\s*(setvarg|const)\s+(\w+)\s+(.*)$", re.IGNORECASE)


def rest_origin_z(world: BSP, x: float, y: float, z: float) -> float | None:
    """Lowest standing-player origin z at (x, y), searching down from z (hull 1)."""
    head = world.models[0].headnode[1]

    def solid(zz):
        return hull_point_contents(world, head, (x, y, zz), 1) == CONTENTS_SOLID

    climb = 0
    while solid(z) and climb < 72:
        z += 1
        climb += 1
    if solid(z):
        return None
    for _ in range(1024):
        if solid(z - 1):
            return z
        z -= 1
    return None


def convert_links(world: BSP, ents: list[Entity], cfg: dict, report: dict) -> list[Entity]:
    added = []
    for link in cfg["links"]:
        matches = [e for e in ents if getattr(e, "region", None) == link["from_region"]
                   and e.classname == "msarea_transition" and e.get("targetname") == link["transition"]]
        if len(matches) != 1:
            raise ValueError(f"expected one transition {link['transition']} in {link['from_region']}, "
                             f"found {len(matches)}")
        trans = matches[0]
        dest_before = {k: trans.get(k) for k in ("destmap", "desttrans", "destname")}
        keep = [[k, v] for k, v in trans.pairs if k in ("model", "origin", "targetname")]
        trans.pairs = [["classname", "trigger_teleport"]] + keep + [
            ["target", link["destination"]],
            ["scriptevent", "ext_setspawn;" + link["arrive"]],
            ["spawnflags", "0"],
        ]
        spawns = [e for e in ents if getattr(e, "region", None) == link["to_region"]
                  and e.classname == "ms_player_spawn" and e.get("message") == link["arrive"]]
        if not spawns:
            raise ValueError(f"no arrival spawns named {link['arrive']} in {link['to_region']}")
        dests = []
        for s in spawns:
            x, y, z = (float(c) for c in s.get("origin").split())
            rest = rest_origin_z(world, x, y, z)
            if rest is None:
                raise ValueError(f"arrival spawn {s.get('origin')} has no floor in the world hull")
            dest = Entity([["classname", "info_teleport_destination"],
                           ["targetname", link["destination"]],
                           ["origin", fmt_vec((x, y, rest - 36))],
                           ["angles", s.get("angles") or "0 0 0"]])
            dest.region = link["to_region"]
            dest.keep = True
            dests.append(dest)
        fade = Entity([["classname", "env_fade"], ["targetname", link["destination"]],
                       ["duration", cfg["fade"]["duration"]], ["holdtime", cfg["fade"]["holdtime"]],
                       ["renderamt", "255"], ["rendercolor", "0 0 0"], ["spawnflags", "5"]])
        fade.region = link["to_region"]
        fade.keep = True
        trans.keep = True  # the link teleports stay loaded: they bring their destination region back
        added += dests + [fade]
        report["links"].append({"from": link["from_region"], "trigger": link["transition"],
                                "replaced": dest_before, "arrivals": [d.get("origin") for d in dests]})
    return ents + added


def apply_edits(ents: list[Entity], cfg: dict, report: dict) -> None:
    """Config-driven entity edits; a match value of null means the key must be absent."""
    for edit in cfg.get("entity_edits", []):
        hits = 0
        for e in ents:
            if getattr(e, "region", None) != edit["region"]:
                continue
            if all((e.get(k) is None) if v is None else (e.get(k) == v) for k, v in edit["match"].items()):
                for k, v in edit["set"].items():
                    e.set(k, v)
                hits += 1
        if not hits:
            raise ValueError(f"entity edit matched nothing: {edit}")
        report.setdefault("entity_edits", []).append({"edit": edit, "matched": hits})


# Boss respawn timers (ms.dll msr_bosses.h): the timer key is boss.<region>.<id>, a world state key
# (lowercase [a-z0-9_.:-], at most 64 characters); ids carry no dots so the key splits cleanly
BOSS_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
BOSS_KEY_MAX = 64
MONSTER_CLASSES = ("ms_npc", "msnpc_human1", "msworlditem_treasure")   # plus msmonster_* (CMSMonster classes)


def is_spawner_template(e: Entity) -> bool:
    """A monster/NPC map entity that hands itself to a spawner; decoration placed on the same
    spot (the trollboss statues are env_models) never matches."""
    cls = e.classname or ""
    return bool(e.get("spawnarea")) and (cls.startswith("msmonster") or cls in MONSTER_CLASSES)


def entity_scripts(e: Entity) -> set:
    names = {e.get("scriptfile"), e.get("defscriptfile")}
    names |= {v for k, v in e.pairs if re.match(r"^random_\d+_scriptfile$", k)}
    return {n.lower() for n in names if n}


def apply_bosses(ents: list[Entity], regions: list[RegionSource], cfg: dict) -> list:
    """Config "bosses": tag each boss's spawner template with msr_boss (its id), msr_boss_cooldown
    (seconds) and msr_boss_open (the exits its death opens, fired instead while it is held; names
    after the region's target renames). A boss is named by its region and the template's origin
    in the original map (within 2 units). Returns [(entity, report entry)]."""
    by_name = {reg.name: reg for reg in regions}
    tagged, keys = [], set()
    for b in cfg.get("bosses", []):
        what = f"boss {b.get('region')}/{b.get('id')}"
        reg = by_name.get(b.get("region"))
        if reg is None:
            raise ValueError(f"{what}: unknown region")
        bid = str(b.get("id", ""))
        key = f"boss.{reg.name.lower()}.{bid}"
        if not BOSS_ID.match(bid) or len(key) > BOSS_KEY_MAX:
            raise ValueError(f"{what}: id must match {BOSS_ID.pattern} and make a key of at most {BOSS_KEY_MAX} characters")
        if key in keys:
            raise ValueError(f"{what}: duplicate id in its region")
        keys.add(key)
        origin = [float(c) for c in b.get("origin", [])]
        if len(origin) != 3:
            raise ValueError(f"{what}: origin must be [x, y, z] in the original map")
        found = []
        for e in ents:
            src = getattr(e, "source_origin", None)
            if getattr(e, "region", None) != reg.name or not src or not is_spawner_template(e):
                continue
            p = [float(c) for c in src.split()]
            if len(p) == 3 and sum((p[k] - origin[k]) ** 2 for k in range(3)) <= 4.0:
                found.append(e)
        if len(found) != 1:
            raise ValueError(f"{what}: {len(found)} spawner templates within 2 units of {origin} (need exactly one)")
        e = found[0]
        if e.get("msr_boss"):
            raise ValueError(f"{what}: its template is already boss {e.get('msr_boss')}")
        script = b.get("script")
        if script and script.lower() not in entity_scripts(e):
            raise ValueError(f"{what}: template runs {sorted(entity_scripts(e))}, not {script}")
        cooldown = b.get("cooldown")
        if cooldown is not None and not (isinstance(cooldown, (int, float)) and cooldown > 0):
            raise ValueError(f"{what}: cooldown must be seconds > 0 (leave it out for ms_boss_cooldown)")
        rename = reg.cfg.get("_rename", {})

        def region_name(n, kind):
            name = rename.get(n, n)
            here = [x for x in ents if getattr(x, "region", None) == reg.name and x.get("targetname") == name]
            elsewhere = sorted({x.region for x in ents if getattr(x, "region", None) not in (None, reg.name)
                                and x.get("targetname") == name})
            if ";" in name or name.startswith("-") or not here:
                raise ValueError(f"{what}: {kind} name {n} ({name}) names nothing in {reg.name}")
            if elsewhere:
                raise ValueError(f"{what}: {kind} name {name} is also used in {elsewhere} (it would fire there too)")
            return name

        # "remove": entities its death would have removed (a trigger that re-closes an exit the hold
        # opens); written first, as "-name", so the game removes them before firing the opens
        removes = [region_name(n, "remove") for n in b.get("remove", [])]
        opens = [region_name(n, "open") for n in b.get("open", [])]
        e.set("msr_boss", bid)
        if cooldown is not None:
            e.set("msr_boss_cooldown", f"{cooldown:g}")
        if removes or opens:
            e.set("msr_boss_open", ";".join(["-" + n for n in removes] + opens))
        tagged.append((e, {"region": reg.name, "id": bid, "key": key, "classname": e.classname,
                           "origin": e.get("origin"), "source_origin": e.source_origin,
                           "spawnarea": e.get("spawnarea"), "script": e.get("scriptfile") or e.get("defscriptfile"),
                           "cooldown": cooldown, "open": opens, "remove": removes}))
    return tagged


def merge_detail(regions, builder: WorldBuilder, out_path: Path) -> int:
    seen, lines = set(), []
    renamed = builder.report["renamed_textures"]
    for reg in regions:
        path = reg.cfg.get("detail")
        if not path:
            continue
        for line in (ROOT / path).read_text(encoding="latin-1").splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            name = renamed.get(f"{reg.name}:{parts[0]}", parts[0])
            if name.lower() in seen:
                continue
            seen.add(name.lower())
            lines.append(" ".join([name] + parts[1:]))
    out_path.write_text("\n".join(lines) + "\n", encoding="latin-1")
    return len(lines)


# ---------------------------------------------------------------------------
# region table
# ---------------------------------------------------------------------------
def split_planes(cfg: dict) -> list[tuple[int, float]]:
    """The join planes as (axis, dist), dist rounded to the float32 the BSP stores.

    cfg["split"] gives [axis, dist] pairs in "planes" or bare distances along
    cfg["split"]["axis"] (default z) in "planes"/"dists", exactly as main() feeds WorldBuilder.build.
    """
    split = cfg["split"]
    axis = int(split.get("axis", 2))
    return [(int(d[0]), f32(float(d[1]))) if isinstance(d, (list, tuple)) else (axis, f32(float(d)))
            for d in (split.get("planes") or split["dists"])]


def region_cells(cfg: dict) -> dict[str, tuple[list[float], list[float]]]:
    """{region name: (mins, maxs)} of the half-open box each region owns.

    Join node k sends p[axis_k] - dist_k >= 0 (its front child) to order[k] and
    everything else on down the chain, so order[k] owns the front of plane k
    behind every earlier plane, and the last region owns what is behind all of
    them. Each such set is an axis-aligned box: mins[a] <= p[a] < maxs[a].
    """
    planes = split_planes(cfg)
    order = cfg["split"]["order"]
    if len(planes) != len(order) - 1:
        raise ValueError("need one split plane between each pair of stacked regions")
    names = [rc["name"] for rc in cfg["regions"]]
    if sorted(order) != sorted(names):
        raise ValueError(f"split order {order} must list every region {names} exactly once")
    cells = {}
    for k, name in enumerate(order):
        mins, maxs = [-REGION_LIMIT] * 3, [REGION_LIMIT] * 3
        for a, d in planes[:k]:
            maxs[a] = min(maxs[a], d)
        if k < len(planes):
            a, d = planes[k]
            mins[a] = max(mins[a], d)
        cells[name] = (mins, maxs)
    return cells


def meta_text(value) -> str:
    """Entity-safe metadata string: no double quotes or line breaks."""
    if value is None:
        return ""
    if isinstance(value, bool):
        value = "1" if value else "0"
    elif isinstance(value, float):
        value = f"{value:g}"
    return " ".join(str(value).replace('"', "'").split())


def read_map_startup(name: str) -> tuple[dict, Path | None]:
    """Map metadata from reference/scripts/<name>/map_startup.script (first definition wins)."""
    path = ROOT / "reference" / "scripts" / name / "map_startup.script"
    if not path.is_file():
        return {}, None
    found = {}
    for line in path.read_text(encoding="latin-1").splitlines():
        m = SCRIPT_LINE.match(line)
        if not m:
            continue
        key = SCRIPT_KEYS.get((m.group(1).lower(), m.group(2).upper()))
        if not key or key in found:
            continue
        rest = m.group(3).strip()
        if rest[:1] in ("'", '"'):
            end = rest.find(rest[0], 1)
            value = rest[1:end] if end > 0 else rest[1:]
        else:
            value = rest.split("//", 1)[0]
        value = meta_text(value)
        if value:
            found[key] = value
    return found, path


def region_entities(regions: list[RegionSource], cfg: dict, report: dict) -> list[Entity]:
    """One info_msr_region per region, in cfg["regions"] order.

    Metadata priority: the region's "meta" object in the config (a key present
    there always wins; null or "" drops the key), then its map_startup script,
    then its source worldspawn, then META_DEFAULTS. Keys with empty values, and
    maxrange 0, are left out.
    """
    cells = region_cells(cfg)
    ents = []
    report["regions"] = []
    for i, reg in enumerate(regions):
        name = reg.name
        cell_mins, cell_maxs = cells[name]
        w = reg.bsp.models[0]
        tight_mins = [w.mins[k] + reg.offset[k] for k in range(3)]
        tight_maxs = [w.maxs[k] + reg.offset[k] for k in range(3)]

        meta = reg.cfg.get("meta") or {}
        unknown = set(meta) - set(META_KEYS)
        if unknown:
            raise ValueError(f"region {name}: unknown meta keys {sorted(unknown)}")
        script, script_path = read_map_startup(name)
        src_ws = reg.bsp.entities[0] if reg.bsp.entities and reg.bsp.entities[0].classname == "worldspawn" \
            else next((e for e in reg.bsp.entities if e.classname == "worldspawn"), Entity())
        from_ws = {}
        for ws_key, key in WORLDSPAWN_META.items():
            value = meta_text(src_ws.get(ws_key))
            if value:
                from_ws[key] = value

        values, sources = {}, {}
        for key in META_KEYS:
            if key in meta:
                values[key], sources[key] = meta_text(meta[key]), "meta"
            elif key in script:
                values[key], sources[key] = script[key], "script"
            elif key in from_ws:
                values[key], sources[key] = from_ws[key], "worldspawn"
            elif key in META_DEFAULTS:
                values[key], sources[key] = META_DEFAULTS[key], "default"
            else:
                values[key], sources[key] = "", "none"
        if values["maxrange"]:
            try:
                if float(values["maxrange"]) == 0:
                    values["maxrange"] = ""
            except ValueError:
                pass

        pairs = [["classname", REGION_CLASS], ["region", name.lower()], ["index", str(i)],
                 ["offset", fmt_vec(reg.offset)],
                 ["cell_mins", fmt_vec(cell_mins)], ["cell_maxs", fmt_vec(cell_maxs)],
                 # not "mins"/"maxs": the game DLL's DispatchKeyValue files those into pev
                 ["tight_mins", fmt_vec(tight_mins)], ["tight_maxs", fmt_vec(tight_maxs)]]
        pairs += [[key, values[key]] for key in META_KEYS if values[key]]
        pairs += no_logout_pairs(reg, cell_mins, cell_maxs)
        ents.append(Entity(pairs))
        report["regions"].append({
            "region": name.lower(), "index": i, "keys": {k: v for k, v in pairs},
            "sources": sources, "omitted": [key for key in META_KEYS if not values[key]],
            "script": str(script_path) if script_path else None,
        })
    return ents


def no_logout_pairs(reg: RegionSource, cell_mins: list[float], cell_maxs: list[float]) -> list[list[str]]:
    """The region's "no_logout" boxes (stock map coordinates in the config) as no_logout_<n> keys.

    Places sealed off in a fresh copy of the region (a pit behind an unbroken wall, caves behind
    a boss's web): the game never keeps a logout spot inside them, so a player who logs out there
    rejoins at their last spot outside instead of trapped.
    """
    pairs = []
    for n, box in enumerate(reg.cfg.get("no_logout") or []):
        mins = [float(box["mins"][k]) + reg.offset[k] for k in range(3)]
        maxs = [float(box["maxs"][k]) + reg.offset[k] for k in range(3)]
        if any(mins[k] >= maxs[k] for k in range(3)):
            raise ValueError(f"region {reg.name}: no_logout box {box.get('name', n)} has mins >= maxs")
        if any(mins[k] < cell_mins[k] or maxs[k] > cell_maxs[k] for k in range(3)):
            raise ValueError(f"region {reg.name}: no_logout box {box.get('name', n)} leaves the region's cell")
        pairs.append([f"no_logout_{n}", f"{fmt_vec(mins)} {fmt_vec(maxs)}"])
    return pairs


def f32_next(x: float, toward: float) -> float:
    """The float32 neighbour of x in the direction of toward."""
    x = f32(x)
    if x == toward:
        return x
    if x == 0.0:
        tiny = struct.unpack("<f", struct.pack("<I", 1))[0]
        return tiny if toward > 0 else -tiny
    bits = struct.unpack("<I", struct.pack("<f", x))[0]
    bits += 1 if (toward > x) == (x > 0) else -1
    return struct.unpack("<f", struct.pack("<I", bits))[0]


def check_regions(world: BSP, ents: list[Entity], cfg: dict, report: dict) -> list[str]:
    """Check the region table of the written map; returns the failures (also in report["region_check"]).

    world is the map reloaded from disk; ents the entity list it was written
    from (same order), which still carries each entity's .region.
    """
    errors = []
    check = report["region_check"] = {}
    n = len(cfg["regions"])
    names = [rc["name"].lower() for rc in cfg["regions"]]
    table = world.entities[1:1 + n]
    if (not world.entities or world.entities[0].classname != "worldspawn"
            or [e.classname for e in table] != [REGION_CLASS] * n
            or [e.get("region") for e in table] != names
            or [e.get("index") for e in table] != [str(i) for i in range(n)]
            or any(e.classname == REGION_CLASS for e in world.entities[1 + n:])):
        errors.append(f"region table is not entities[1..{n}] in config order")
        check["errors"] = errors
        return errors
    check["table"] = f"entities[1..{n}]"

    def vec(s):
        return [float(c) for c in s.split()]

    cells = [(e.get("region"), vec(e.get("cell_mins")), vec(e.get("cell_maxs"))) for e in table]

    def owners(p):
        return [name for name, mn, mx in cells if all(mn[a] <= p[a] < mx[a] for a in range(3))]

    # the join nodes/clipnodes the builder put in the first slots, walked like the engine does
    planes = split_planes(cfg)
    order = [o.lower() for o in cfg["split"]["order"]]
    n_joins = len(planes)
    if n_joins and list(world.models[0].headnode[:4]) != [0, 0, 1, 2]:
        errors.append(f"world head nodes {world.models[0].headnode} are not the join chain")
    for k, (a, d) in enumerate(planes):
        node = world.nodes[k]
        pl = world.planes[node.planenum]
        if pl.type != a or pl.normal[a] != 1.0 or pl.dist != d:
            errors.append(f"join node {k} plane {pl} is not axis {a} dist {d}")
        if any(world.clipnodes[3 * k + h].planenum != node.planenum for h in range(3)):
            errors.append(f"join clipnodes of split {k} do not share its plane")
        if k + 1 < n_joins and (node.children[1] != k + 1
                                or any(world.clipnodes[3 * k + h].children[1] != 3 * (k + 1) + h
                                       for h in range(3))):
            errors.append(f"join node {k} does not continue the chain")
    head_region = {world.nodes[k].children[0]: order[k] for k in range(n_joins)}
    if n_joins:
        head_region[world.nodes[n_joins - 1].children[1]] = order[-1]

    def node_region(p):
        if not n_joins:
            return order[0]
        num = 0
        while 0 <= num < n_joins:
            node = world.nodes[num]
            pl = world.planes[node.planenum]
            dist = p[pl.type] - pl.dist if pl.type < 3 else sum(p[c] * pl.normal[c] for c in range(3)) - pl.dist
            num = node.children[0] if dist >= 0 else node.children[1]
        return head_region.get(num)

    # partition: random points over the whole cell space and over the world, plus every plane
    # boundary (on it, one float32 step either side, +-1) crossed with the other axes' boundaries
    rng = random.Random(1234)
    lo, hi = -REGION_LIMIT, f32_next(REGION_LIMIT, 0.0)
    wmins, wmaxs = world.models[0].mins, world.models[0].maxs
    random_pts = [[rng.uniform(lo, hi) for _ in range(3)] for _ in range(200)]
    random_pts += [[rng.uniform(wmins[a] - 512, wmaxs[a] + 512) for a in range(3)] for _ in range(200)]
    axis_vals = [{lo, hi, 0.0} for _ in range(3)]
    for a, d in planes:
        axis_vals[a] |= {d, f32_next(d, -REGION_LIMIT), f32_next(d, REGION_LIMIT), d - 1, d + 1}
    boundary_pts = [list(p) for p in itertools.product(*[sorted(v) for v in axis_vals])]
    for a, d in planes:
        for _ in range(20):
            p = [rng.uniform(lo, hi) for _ in range(3)]
            p[a] = d
            boundary_pts.append(p)
    part = {"random_points": len(random_pts), "boundary_points": len(boundary_pts),
            "gaps": 0, "overlaps": 0, "join_node_mismatch": 0}
    bad = []
    for p in random_pts + boundary_pts:
        p = [f32(c) for c in p]
        own = owners(p)
        if len(own) == 0:
            part["gaps"] += 1
        elif len(own) > 1:
            part["overlaps"] += 1
        elif own[0] != node_region(p):
            part["join_node_mismatch"] += 1
        else:
            continue
        bad.append({"point": p, "cells": own, "join_nodes": node_region(p)})
    if bad:
        part["examples"] = bad[:10]
        errors.append(f"cells do not partition space like the join nodes: {len(bad)} bad points")
    check["partition"] = part

    # each region's tight bounds must lie inside its own cell
    inside = {}
    for e, (name, mn, mx) in zip(table, cells):
        tmn, tmx = vec(e.get("tight_mins")), vec(e.get("tight_maxs"))
        inside[name] = all(mn[a] <= tmn[a] and tmx[a] < mx[a] for a in range(3))
        if not inside[name]:
            errors.append(f"region {name} bounds {tmn} {tmx} leave its cell {mn} {mx}")
    check["bounds_inside_cell"] = inside

    # every placed entity must classify into its own region
    ent = {"point": 0, "brush": 0, "skipped_no_position": 0, "misplaced": 0,
           "by_region": {name: 0 for name in names}}
    misplaced = []
    if len(ents) != len(world.entities) or any(a.classname != b.classname for a, b in zip(ents, world.entities)):
        errors.append("written entity lump does not match the entity list it was written from")
    else:
        for src, e in zip(ents, world.entities):
            region = getattr(src, "region", None)
            if not region or e.classname in ("worldspawn", REGION_CLASS):
                continue
            model = e.get("model") or ""
            origin = vec(e.get("origin")) if e.get("origin") else None
            if model.startswith("*") and model[1:].isdigit() and int(model[1:]) > 0:
                mi = int(model[1:])
                if mi >= len(world.models):
                    misplaced.append({"classname": e.classname, "region": region, "model": model})
                    continue
                m = world.models[mi]
                o = origin or [0.0, 0.0, 0.0]
                p = [(m.mins[a] + m.maxs[a]) / 2 + o[a] for a in range(3)]
                ent["brush"] += 1
            elif origin:
                p = origin
                ent["point"] += 1
            else:
                ent["skipped_no_position"] += 1
                continue
            p = [f32(c) for c in p]
            ent["by_region"][region.lower()] += 1
            own = owners(p)
            if own != [region.lower()]:
                misplaced.append({"classname": e.classname, "targetname": e.get("targetname"),
                                  "region": region, "point": [round(c, 2) for c in p], "cells": own})
    ent["checked"] = ent["point"] + ent["brush"]
    ent["misplaced"] = len(misplaced)
    if misplaced:
        ent["examples"] = misplaced[:10]
        errors.append(f"{len(misplaced)} entities lie outside their region's cell")
    check["entities"] = ent
    check["errors"] = errors
    return errors


def main():
    cfg_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "edana_world.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
    started = time.time()
    regions = []
    for rc in cfg["regions"]:
        rc = dict(rc)
        rc["_style_map"] = {int(k): v for k, v in rc.get("style_map", {}).items()}
        regions.append(RegionSource(rc, ROOT))
    names = [reg.name for reg in regions]
    order = [names.index(n) for n in cfg["split"]["order"]]
    builder = WorldBuilder(regions, order)
    world = builder.build(cfg["split"].get("axis", 2), cfg["split"].get("planes") or cfg["split"]["dists"])
    report = builder.report
    report["links"] = []

    fixed = repair_extents(builder, world)
    report["texinfo_adjustments"] = fixed

    ents = process_entities(builder, cfg)
    apply_edits(ents, cfg, report)
    bosses = apply_bosses(ents, regions, cfg)
    ents = convert_links(world, ents, cfg, report)
    report["pruned_decor_models"] = len(builder.decor_models)
    # the engine spawns entities in lump order: the region table goes right after worldspawn
    if not ents or ents[0].classname != "worldspawn":
        raise ValueError("worldspawn must be the first entity")
    ents = ents[:1] + region_entities(regions, cfg, report) + ents[1:]
    if cfg.get("region_keys"):
        # For the region-aware ms.dll only (it consumes these keys; a stock DLL would hand them
        # to the entities): which region each entity belongs to, so an emptied region can be
        # removed and re-created, and which link entities must always stay loaded.
        tagged = kept = 0
        for e in ents:
            if e.classname in ("worldspawn", REGION_CLASS):
                continue
            if getattr(e, "region", None):
                e.set("msr_region", e.region.lower())
                tagged += 1
            if getattr(e, "keep", False):
                e.set("msr_keep", "1")
                kept += 1
        report["region_keys"] = {"tagged": tagged, "kept": kept}
    if bosses:
        index = {id(e): i for i, e in enumerate(ents)}
        report["bosses"] = [dict(entry, entity=index[id(e)]) for e, entry in bosses]
    world.entities = ents

    out_path = ROOT / cfg["output"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fmt = cfg.get("format", "bsp30ext")
    if fmt == "bsp2":
        from convert_bsp2 import light_size
        report["bsp2"] = world.save_bsp2(out_path, [light_size(world, f) for f in world.faces])
    else:
        world.save(out_path, bsp30ext=True)

    # reload from disk so verification covers the written file
    written = BSP.load(out_path)
    report["verification"] = verify(builder, written)
    region_errors = check_regions(written, ents, cfg, report)
    report["counts"] = {
        "planes": len(written.planes), "vertexes": len(written.vertexes), "nodes": len(written.nodes),
        "texinfo": len(written.texinfo), "faces": len(written.faces), "clipnodes": len(written.clipnodes),
        "leafs": len(written.leafs), "visleafs": written.models[0].visleafs,
        "marksurfaces": len(written.marksurfaces), "edges": len(written.edges),
        "surfedges": len(written.surfedges), "models": len(written.models), "textures": len(written.textures),
        "entities": len(written.entities), "lighting_bytes": len(written.lighting),
        "vis_bytes": len(written.visdata), "file_bytes": out_path.stat().st_size,
    }
    from bsp30 import count_tree
    report["world_hull_nodes"] = [count_tree(written, written.models[0].headnode[h], h > 0) for h in range(4)]
    report["world_bounds"] = [written.models[0].mins, written.models[0].maxs]
    report["detail_lines"] = merge_detail(regions, builder, ROOT / cfg["detail_output"])
    report["seconds"] = round(time.time() - started, 1)
    (ROOT / cfg["report"]).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("verification", "counts", "world_hull_nodes",
                                                "renamed_textures", "renamed_targets", "restyled_lights",
                                                "texinfo_adjustments", "detail_lines", "region_check",
                                                "seconds")}, indent=2))
    # FWGS loader limits: BSP30/BSP30ext index widths, or BSP2's rejecting (CHECK_OVERFLOW) lumps;
    # plus MSR's delta.lst entity origin range
    c = report["counts"]
    if fmt == "bsp2":
        limits = {"faces": 262144, "leafs": 131072, "nodes": 262144, "texinfo": 262144, "models": 2048}
    else:
        limits = {"vertexes": 65535, "planes": 65535, "faces": 65535, "marksurfaces": 65535,
                  "nodes": 32767, "leafs": 32767, "texinfo": 32767, "models": 2048}
    over = {k: (c[k], lim) for k, lim in limits.items() if c[k] > lim}
    extent = float(cfg.get("world_extent", 4095))   # 4095 classic; 32767 needs the -bigworld server
    far = [(e.classname, e.get("origin")) for e in written.entities if e.get("origin")
           and any(abs(float(x)) > extent for x in e.get("origin").split())]
    report["format_headroom"] = {k: f"{c[k]}/{lim} ({100 * c[k] / lim:.1f}%)" for k, lim in limits.items()}
    report["entities_outside_delta_range"] = far
    (ROOT / cfg["report"]).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["format_headroom"], indent=2))
    for b in report.get("bosses", []):
        print(f"boss {b['key']}: entity {b['entity']} {b['classname']} at {b['origin']}, "
              f"cooldown {b['cooldown']}, open {';'.join(b['open']) or '-'}")
    if over or far:
        raise SystemExit(f"format limits exceeded: {over} {far[:5]}")
    v = report["verification"]
    if v["hull_mismatch"] or v["extent_mismatch"] or v["vis_mismatch"] or v["tree_order_errors"]:
        raise SystemExit("verification FAILED")
    if region_errors:
        raise SystemExit(f"region check FAILED: {region_errors}")
    print("verification passed:", out_path)


if __name__ == "__main__":
    main()
