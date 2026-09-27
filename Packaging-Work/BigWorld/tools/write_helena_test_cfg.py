"""Write the scripted Helena test (sandbox\\game\\msr\\bigworld_test.cfg).

Run with tools\\run_lifecycle_test.ps1 (short ms_region_unload_time): the client walks
Edana -> Thornlands -> Helena (region intro, chat, screenshot) and back to Edana, then
waits in the Sewers (away from every way into Thornlands and Helena) until both unload.
Back at Edana's Thornlands gate, Thornlands should load ahead of the player over several
frames; the player then goes through to Thornlands and on into Helena, which is re-created
(ahead, if the Thornlands arrival is close enough to its gate, else as the player arrives)
and runs its game_master game_spawn again.

Usage: python write_helena_test_cfg.py [screenshot prefix]
"""
import secrets
import sys
from pathlib import Path

prefix = sys.argv[1] if len(sys.argv) > 1 else "H"
cfg = Path(__file__).resolve().parent.parent / "sandbox" / "game" / "msr" / "bigworld_test.cfg"
long_wait = ["wait 3000"] * 4  # well past the unload time at any frame rate the test client runs at
lines = [
    f'setinfo _fnid "{secrets.token_hex(16)}"', 'name "BigWorldTester"', "exec masterpiece.cfg", "developer 1",
    "connect 127.0.0.1:27199", "wait 4500", "echo BW_STEP_0_CREATE",
    "cmd char canjoin", "wait 300", "cmd char 0", "wait 1500", "echo BW_STEP_1_SPAWN", "ent_info 1",
    "ent_fire SE-A3 touch", "wait 400",                      # start in Edana wherever the character was saved
    "echo BW_H1_TO_THORNLANDS", "ent_fire a3trans touch", "wait 400",
    "echo BW_H2_TO_HELENA", "ent_fire NE-A3 touch", "wait 500", "ent_info 1",
    f"screenshot scrshots/{prefix}_2_helena.png", "say helena_chat_check", "wait 400",
    "echo BW_H3_HELENA_TO_THORNLANDS", "ent_fire helena touch", "wait 400", "ent_info 1",
    f"screenshot scrshots/{prefix}_3_thornlands_from_helena.png",
    "echo BW_H4_TO_EDANA_AND_SEWERS", "ent_fire SE-A3 touch", "wait 300", "ent_fire sewer_entrance touch", "wait 300", "ent_info 1",
    "echo BW_H5_WAITING_FOR_UNLOAD", *long_wait,
    "echo BW_H6_BACK_TO_THE_THORNLANDS_GATE", "ent_fire sewer_start touch", "wait 300", "ent_fire SE-A3 touch", "ent_info 1",
    "wait 600",                                              # Thornlands loads ahead meanwhile
    "echo BW_H7_THROUGH_TO_THORNLANDS", "ent_fire a3trans touch", "ent_info 1", "wait 600",
    "echo BW_H8_ON_TO_HELENA", "ent_fire NE-A3 touch", "wait 500", "ent_info 1",
    f"screenshot scrshots/{prefix}_8_helena_reloaded.png", "wait 300",
    "echo BW_H9_BACK_TO_EDANA", "ent_fire helena touch", "wait 300", "ent_fire SE-A3 touch", "wait 300",
    "echo BW_DONE", "quit",
]
cfg.write_text("\n".join(lines) + "\n", encoding="ascii")
print(cfg)
