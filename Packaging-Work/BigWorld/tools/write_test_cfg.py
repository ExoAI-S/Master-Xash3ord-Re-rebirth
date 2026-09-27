"""Write the scripted crossing test (sandbox\\game\\msr\\bigworld_test.cfg) with a screenshot prefix."""
import secrets
import sys
from pathlib import Path

prefix = sys.argv[1] if len(sys.argv) > 1 else "bw"
cfg = Path(__file__).resolve().parent.parent / "sandbox" / "game" / "msr" / "bigworld_test.cfg"
steps = [
    ("BW_STEP_2_TO_THORNLANDS", "ent_fire a3trans touch", "thornlands"),
    ("BW_STEP_3_TO_EDANA", "ent_fire SE-A3 touch", "edana_north"),
    ("BW_STEP_4_TO_SEWERS", "ent_fire sewer_entrance touch", "sewers"),
    ("BW_STEP_5_SEWERS_TO_EDANA", "ent_fire sewer_start touch", "edana_from_sewers"),
]
lines = [
    f'setinfo _fnid "{secrets.token_hex(16)}"', 'name "BigWorldTester"', "exec masterpiece.cfg", "developer 1",
    "connect 127.0.0.1:27199", "wait 4500", "echo BW_STEP_0_CREATE",
    "cmd char canjoin", "wait 300", "cmd char 0", "wait 1500", "echo BW_STEP_1_SPAWN", "ent_info 1",
    f"screenshot scrshots/{prefix}_1_spawn.png", "wait 100",
]
for n, (marker, cmd, shot) in enumerate(steps, 2):
    lines += [f"echo {marker}", cmd, "wait 400", "ent_info 1", f"screenshot scrshots/{prefix}_{n}_{shot}.png", "wait 100"]
lines += ["echo BW_STEP_6_DIE", "kill", "wait 1800", "ent_info 1", "echo BW_DONE", "quit"]
cfg.write_text("\n".join(lines) + "\n", encoding="ascii")
print(cfg)

