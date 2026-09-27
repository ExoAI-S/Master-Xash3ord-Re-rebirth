"""Write the scripted region unload/reload test (sandbox\\game\\msr\\bigworld_test.cfg).

Run with a short ms_region_unload_time (tools\\run_lifecycle_test.ps1 uses 15 s): the
client visits Thornlands, returns to Edana and waits so Thornlands (and the never-visited
Sewers / Northern Thornlands) unload, then goes back into each region, which must be
re-created before the player arrives. The runner polls msr_regions for a timeline.

Usage: python write_lifecycle_test_cfg.py [screenshot prefix]
"""
import secrets
import sys
from pathlib import Path

prefix = sys.argv[1] if len(sys.argv) > 1 else "L"
cfg = Path(__file__).resolve().parent.parent / "sandbox" / "game" / "msr" / "bigworld_test.cfg"
long_wait = ["wait 3000"] * 4  # well past the unload time at any frame rate the test client runs at
lines = [
    f'setinfo _fnid "{secrets.token_hex(16)}"', 'name "BigWorldTester"', "exec masterpiece.cfg", "developer 1",
    "connect 127.0.0.1:27199", "wait 4500", "echo BW_STEP_0_CREATE",
    "cmd char canjoin", "wait 300", "cmd char 0", "wait 1500", "echo BW_STEP_1_SPAWN", "ent_info 1",
    "ent_fire SE-A3 touch", "wait 400",                      # start in Edana wherever the character was saved
    "echo BW_L1_VISIT_THORNLANDS", "ent_fire a3trans touch", "wait 500",
    f"screenshot scrshots/{prefix}_1_thornlands_first.png",
    "echo BW_L2_BACK_TO_EDANA", "ent_fire SE-A3 touch", "wait 300",
    "echo BW_L3_WAITING_FOR_UNLOAD", *long_wait,
    "echo BW_L4_THORNLANDS_AGAIN", "ent_fire a3trans touch", "wait 500", "ent_info 1",
    f"screenshot scrshots/{prefix}_4_thornlands_reloaded.png", "say lifecycle_chat_thornlands", "wait 300",
    "echo BW_L5_TO_NORTH", "ent_fire from_thorn_north touch", "wait 500", "ent_info 1",
    f"screenshot scrshots/{prefix}_5_north_reloaded.png", "wait 300",
    "echo BW_L6_NORTH_TO_THORNLANDS_TO_EDANA", "ent_fire from_thorn touch", "wait 300", "ent_fire SE-A3 touch", "wait 300",
    "echo BW_L7_TO_SEWERS", "ent_fire sewer_entrance touch", "wait 500", "ent_info 1",
    f"screenshot scrshots/{prefix}_7_sewers_reloaded.png", "wait 200",
    "echo BW_L8_SEWERS_TO_EDANA", "ent_fire sewer_start touch", "wait 300",
    "echo BW_DONE", "quit",
]
cfg.write_text("\n".join(lines) + "\n", encoding="ascii")
print(cfg)
