"""Pre-merge analysis of two BSP30 maps: hull sizes, conflicts, ordering assumptions."""
import collections
import sys

from bsp30 import BSP, count_tree


def describe(name, bsp):
    print(f"== {name}")
    w = bsp.models[0]
    print(f"  leafs={len(bsp.leafs)} world.visleafs={w.visleafs} models={len(bsp.models)} "
          f"clipnodes={len(bsp.clipnodes)} nodes={len(bsp.nodes)}")
    for h in range(4):
        print(f"  world hull{h} headnode={w.headnode[h]} tree={count_tree(bsp, w.headnode[h], h > 0)}")
    # submodel headnode oddities
    odd = collections.Counter()
    maxhull = [0, 0, 0, 0]
    for i, m in enumerate(bsp.models[1:], 1):
        for h in range(1, 4):
            hn = m.headnode[h]
            if hn == 0:
                odd[f"hull{h}=0"] += 1
            elif hn < 0:
                odd[f"hull{h}<0"] += 1
            elif hn >= len(bsp.clipnodes):
                odd[f"hull{h}>=numclip"] += 1
            else:
                maxhull[h] = max(maxhull[h], count_tree(bsp, hn, True))
    print(f"  submodel headnode oddities: {dict(odd)}  largest submodel hull trees: {maxhull}")
    # leaves referenced by world tree vs submodels
    world_leaves = set()
    stack = [w.headnode[0]]
    seen = set()
    while stack:
        n = stack.pop()
        if n < 0:
            world_leaves.add(-n - 1)
            continue
        if n in seen:
            continue
        seen.add(n)
        stack.extend(bsp.nodes[n].children)
    print(f"  world leaf index range: {min(world_leaves)}..{max(world_leaves)} count={len(world_leaves)}")
    sub_leaves = set()
    for m in bsp.models[1:]:
        stack = [m.headnode[0]]
        while stack:
            n = stack.pop()
            if n < 0:
                sub_leaves.add(-n - 1)
                continue
            stack.extend(bsp.nodes[n].children)
    print(f"  submodel leaves: range {min(sub_leaves)}..{max(sub_leaves)} count={len(sub_leaves)} "
          f"overlap-with-world={len(sub_leaves & world_leaves)}")
    styles = collections.Counter(s for f in bsp.faces for s in f.styles if s != 255)
    print(f"  face light styles: {dict(sorted(styles.items()))}")
    ext = sum(1 for t in bsp.textures if t.raw is not None and t.external)
    print(f"  textures={len(bsp.textures)} external={ext} missing={sum(1 for t in bsp.textures if t.raw is None)}")
    origin_brush = [(e.classname, e.get('model'), e.get('origin')) for e in bsp.entities
                    if (e.get('model') or '').startswith('*') and e.get('origin')]
    print(f"  brush entities with origin: {len(origin_brush)} {origin_brush[:8]}")


def main():
    a = BSP.load(sys.argv[1])
    b = BSP.load(sys.argv[2])
    describe("A " + sys.argv[1], a)
    describe("B " + sys.argv[2], b)
    at = {t.name.lower(): t for t in a.textures if t.raw}
    conflicts, same = [], 0
    for t in b.textures:
        if t.raw and t.name.lower() in at:
            if at[t.name.lower()].raw.rstrip(b"\0") == t.raw.rstrip(b"\0"):
                same += 1
            else:
                conflicts.append(t.name)
    print(f"texture names shared={same + len(conflicts)} identical={same} differing={conflicts}")
    an = collections.Counter(e.get('targetname') for e in a.entities if e.get('targetname'))
    bn = collections.Counter(e.get('targetname') for e in b.entities if e.get('targetname'))
    print("targetname conflicts:", sorted(set(an) & set(bn)))
    high = [(e.classname, e.get('origin')) for e in a.entities
            if e.get('origin') and float(e.get('origin').split()[2]) > 900]
    print("A entities with origin z > 900:", high)
    low = [(e.classname, e.get('origin')) for e in b.entities
           if e.get('origin') and float(e.get('origin').split()[2]) < -2144]
    print("B entities with origin z < -2144:", low)


if __name__ == "__main__":
    main()
