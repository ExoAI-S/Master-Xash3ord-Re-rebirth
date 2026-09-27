"""Write the scripted region test (sandbox\\game\\msr\\bigworld_test.cfg).

The client loads character slot 0, then walks the 4-region world through the
walk-in teleports: Edana -> Thornlands -> Northern Thornlands -> Thornlands ->
Edana -> Sewers -> Edana. At each stop it waits for the region intro, says a
chat line (to check chat reaches every region) and takes a screenshot. The
server log shows the region changes, intros and weather rolls ("MSR: ...").

Usage: python write_region_test_cfg.py [screenshot prefix]
"""
import secrets
import sys
from pathlib import Path

prefix = sys.argv[1] if len(sys.argv) > 1 else "R"
cfg = Path(__file__).resolve().parent.parent / "sandbox" / "game" / "msr" / "bigworld_test.cfg"
steps = [
    ("BW_STEP_2_TO_THORNLANDS", "ent_fire a3trans touch", "thornlands"),
    ("BW_STEP_3_TO_THORNLANDS_NORTH", "ent_fire from_thorn_north touch", "thornlands_north"),
    ("BW_STEP_4_BACK_TO_THORNLANDS", "ent_fire from_thorn touch", "thornlands_again"),
    ("BW_STEP_5_TO_EDANA", "ent_fire SE-A3 touch", "edana"),
    ("BW_STEP_6_TO_SEWERS", "ent_fire sewer_entrance touch", "sewers"),
    ("BW_STEP_7_SEWERS_TO_EDANA", "ent_fire sewer_start touch", "edana_from_sewers"),
]
lines = [
    f'setinfo _fnid "{secrets.token_hex(16)}"', 'name "BigWorldTester"', "exec masterpiece.cfg", "developer 1",
    "connect 127.0.0.1:27199", "wait 4500", "echo BW_STEP_0_CREATE",
    "cmd char canjoin", "wait 300", "cmd char 0", "wait 1500", "echo BW_STEP_1_SPAWN", "ent_info 1",
    # first placement: intro after 10 s, difficulty 3 s later
    "wait 1500", f"screenshot scrshots/{prefix}_1_spawn_intro.png", "say chat_check_edana", "wait 300",
]
for n, (marker, cmd, shot) in enumerate(steps, 2):
    lines += [f"echo {marker}", cmd, "wait 350", "ent_info 1", f"screenshot scrshots/{prefix}_{n}_{shot}.png",
              f"say chat_check_{shot}", "wait 350"]
lines += ["echo BW_DONE", "quit"]
cfg.write_text("\n".join(lines) + "\n", encoding="ascii")
print(cfg)
