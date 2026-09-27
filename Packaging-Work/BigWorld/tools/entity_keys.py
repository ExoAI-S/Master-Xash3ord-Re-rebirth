"""Report entity keys whose values look like coordinates, and references to given names."""
import collections
import re
import sys

from bsp30 import BSP

VEC = re.compile(r"^\s*-?\d+(\.\d+)?\s+-?\d+(\.\d+)?\s+-?\d+(\.\d+)?\s*$")
IGNORE = {"origin", "angles", "rendercolor", "_light", "_color", "angle", "movedir"}


def main():
    bsp = BSP.load(sys.argv[1])
    names = set(sys.argv[2:])
    vec_keys = collections.defaultdict(set)
    for e in bsp.entities:
        for k, v in e.pairs:
            if k not in IGNORE and VEC.match(v):
                vec_keys[(e.classname, k)].add(v)
            if names and (v in names or k in names):
                print(f"ref: {e.classname} targetname={e.get('targetname')} {k}={v}")
    for (cls, k), vals in sorted(vec_keys.items()):
        print(f"vector-like: {cls}.{k} e.g. {sorted(vals)[:3]}")
    styled = [(e.classname, e.get('targetname'), e.get('style')) for e in bsp.entities
              if e.get('style') and e.classname.startswith('light')]
    print("light styles:", styled)


if __name__ == "__main__":
    main()
