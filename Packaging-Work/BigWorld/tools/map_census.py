"""Census of every MSR map: bounds, lump counts, hull sizes, entity/model counts, texture bytes."""
import json
import sys
from pathlib import Path

from bsp30 import BSP, count_tree


def main():
    maps_dir, out = Path(sys.argv[1]), Path(sys.argv[2])
    rows = []
    for p in sorted(maps_dir.glob("*.bsp")):
        if p.stat().st_size < 1024:
            continue
        try:
            b = BSP.load(p)
        except Exception as exc:  # noqa: BLE001
            rows.append({"map": p.stem, "error": str(exc)})
            continue
        w = b.models[0]
        size = [round(w.maxs[k] - w.mins[k]) for k in range(3)]
        rows.append({
            "map": p.stem,
            "file_mb": round(p.stat().st_size / 1e6, 2),
            "mins": [round(v) for v in w.mins], "maxs": [round(v) for v in w.maxs], "size": size,
            "planes": len(b.planes), "vertexes": len(b.vertexes), "nodes": len(b.nodes),
            "texinfo": len(b.texinfo), "faces": len(b.faces), "clipnodes": len(b.clipnodes),
            "leafs": len(b.leafs), "visleafs": w.visleafs, "marksurfaces": len(b.marksurfaces),
            "edges": len(b.edges), "surfedges": len(b.surfedges), "models": len(b.models),
            "entities": len(b.entities), "entstring_bytes": sum(len(k) + len(v) + 6 for e in b.entities for k, v in e.pairs),
            "miptex": len(b.textures), "miptex_bytes": len(b.texture_lump()),
            "lighting_bytes": len(b.lighting), "vis_bytes": len(b.visdata),
            "world_hull_nodes": [count_tree(b, w.headnode[h], h > 0) for h in range(4)],
            "classes": {},
        })
        for e in b.entities:
            rows[-1]["classes"][e.classname] = rows[-1]["classes"].get(e.classname, 0) + 1
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    ok = [r for r in rows if "error" not in r]
    print(f"{len(ok)} maps, {len(rows) - len(ok)} errors")
    for key in ("vertexes", "nodes", "faces", "planes", "models", "entities", "miptex_bytes"):
        vals = sorted(r[key] for r in ok)
        print(f"{key:14s} min={vals[0]} median={vals[len(vals)//2]} max={vals[-1]} total={sum(vals)}")
    tall = sorted(ok, key=lambda r: r["size"][2])
    print("shortest:", [(r["map"], r["size"]) for r in tall[:5]])
    print("tallest:", [(r["map"], r["size"]) for r in tall[-5:]])


if __name__ == "__main__":
    main()
