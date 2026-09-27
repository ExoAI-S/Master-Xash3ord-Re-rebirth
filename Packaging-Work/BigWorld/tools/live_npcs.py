"""Ask a running sandbox realm for entity_info over rcon and summarise the live NPCs per region."""
import importlib.util
import re
import sys
from collections import Counter, defaultdict

port = int(sys.argv[1]) if len(sys.argv) > 1 else 27199
spec = importlib.util.spec_from_file_location("gq", r"C:\MSR\Portable-Package\FN\game_query.py")
gq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gq)
pw = open(r"C:\Users\cptki\Documents\Codex\MSR-BigWorld\sandbox\rcon.txt").read().strip()
text = gq.rcon(port, pw, "entity_info")
if len(sys.argv) > 2:
    open(sys.argv[2], "w", encoding="utf-8").write(text)

row = re.compile(r"^\s*(\d+) origin: (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)(.*)$")


def region(x, y, z):
    if y >= 14000:
        return "thornlands_north"
    if y >= 5000:
        return "thornlands"
    if z < -2112:
        return "edanasewers"
    return "edana"


npcs = defaultdict(Counter)
total = 0
for line in text.splitlines():
    m = row.match(line)
    if not m:
        continue
    total += 1
    x, y, z = (float(v) for v in m.group(2, 3, 4))
    rest = m.group(5)
    cls = re.search(r"class: ([^,]+)", rest)
    mdl = re.search(r"model: ([^,]+)", rest)
    cls = cls.group(1).strip() if cls else "?"
    if not (cls.startswith("msmonster") or cls in ("ms_npc", "msworlditem_treasure", "monster_generic")):
        continue
    model = mdl.group(1).strip() if mdl else "(no model)"
    npcs[region(x, y, z)][model.replace("models/", "")] += 1
print(f"entities listed: {total}")
for reg in ("edana", "thornlands", "edanasewers", "thornlands_north"):
    c = npcs.get(reg, Counter())
    print(f"== {reg}: {sum(c.values())} npcs")
    for model, n in c.most_common():
        print(f"   {n:3d}  {model}")
