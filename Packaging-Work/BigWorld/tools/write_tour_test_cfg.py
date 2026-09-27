"""Write the scripted grand-tour test (sandbox\\game\\msr\\bigworld_test.cfg).

Run with tools\\run_lifecycle_test.ps1 -Name tour -UnloadSeconds 20 -ClientSeconds 1800: the
client makes <loops> (default 4) loops of
    Edana -> Thornlands -> Northern Thornlands -> Thornlands -> Helena -> Thornlands -> Edana
    -> Sewers -> (wait in the Sewers) -> Edana.
Every loop starts at Edana's Thornlands gate (SE-A3 puts the player next to a3trans) and waits
there, so Thornlands loads ahead over several frames; every other crossing is made straight
away, so Northern Thornlands, Helena and the Sewers are re-created as the player arrives.
The Sewers wait (4x 'wait 3000') lets Thornlands, Northern Thornlands and Helena unload.
'echo BW_T<loop>_<step>_<what>' comes before and 'ent_info 1' after every crossing; there is a
screenshot on arrival in each region on the first and last loop, and 'say tour_chat_<loop>'
in Helena on every loop.

Two players at once (tools\\run_lifecycle_test.ps1 runs one client, so start these yourself):
    python write_tour_test_cfg.py pair [prefix]
writes bigworld_test_a.cfg and bigworld_test_b.cfg. A goes to Helena, says tour_chat_A, flies
(noclip) away from Helena's gate, beyond ms_region_preload_range, and parks there; B creates
a character in slot 0 (a fresh profile has none), makes two loops of Edana -> Thornlands ->
Northern Thornlands -> Thornlands -> Edana -> Sewers (tour_chat_B_<loop>) -> wait -> Edana and
a last pass through Thornlands and Northern Thornlands, while Helena must stay loaded for A.
The two clients need different player profiles: client.dll forces _fnid from
<runtime>\\player-profile.json, where <runtime> is three folders above msr\\cl_dlls\\client.dll,
so B has to run from another <runtime> folder (e.g. a directory junction <x>\\game ->
sandbox\\game), with -log <name> so the two consoles do not share engine.log. No setinfo _fnid
here on purpose.

'wait' counts client frames (the test client runs at 100-250 fps) and the server can stall for a
second or more on a synchronous region load, so with the default settle (250 frames) replies
and screenshots can lag a crossing; pass a larger settle for screenshots taken after arrival.

Usage: python write_tour_test_cfg.py [screenshot prefix] [loops] [settle frames]
       python write_tour_test_cfg.py pair [screenshot prefix]
"""
import sys
from pathlib import Path

msr = Path(__file__).resolve().parent.parent / "sandbox" / "game" / "msr"
long_wait = ["wait 3000"] * 4  # well past ms_region_unload_time 20 at any frame rate the test client runs at
gate_wait = "wait 600"         # at Edana's Thornlands gate: Thornlands loads ahead meanwhile
settle_frames = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[1] != "pair" else 250
settle = f"wait {settle_frames}"  # after a crossing: arrive and get the region's entities, then ent_info
ent_info = "ent_info 1"           # the player's own edict: 1 for the first client on the server


def join(name, create=None):
    lines = [f'name "{name}"', "exec masterpiece.cfg", "developer 1",
             "connect 127.0.0.1:27199", "wait 4500", "echo BW_STEP_0_CREATE", "cmd char canjoin", "wait 300"]
    if create:  # a fresh profile has no character: make slot 0 (name, gender 0, starting weapon)
        lines += [f'cmd char 0 "{create}" 0 swords_rsword', "wait 800"]
    return lines + ["cmd char 0", "wait 1500", "echo BW_STEP_1_SPAWN", ent_info, "wait 50"]


def cross(marker, trigger, shot=None, extra=()):
    lines = [f"echo {marker}", f"ent_fire {trigger} touch", settle, ent_info]
    if shot:
        lines.append(f"screenshot scrshots/{shot}.png")
    return lines + list(extra) + ["wait 50"]


def tour_loop(loop, prefix, shots, helena=True, sewers=True, chat="tour_chat"):
    """One loop, from anywhere in Edana back to Edana."""
    route = [("GATE", "SE-A3", "edana_gate"), ("TO_THORNLANDS", "a3trans", "thornlands"),
             ("TO_NORTH", "from_thorn_north", "north"), ("NORTH_TO_THORNLANDS", "from_thorn", "thornlands_from_north")]
    if helena:
        route += [("TO_HELENA", "NE-A3", "helena"), ("HELENA_TO_THORNLANDS", "helena", "thornlands_from_helena")]
    route += [("TO_EDANA", "SE-A3", "edana")]
    if sewers:
        route += [("TO_SEWERS", "sewer_entrance", "sewers"), ("WAIT_IN_SEWERS", None, None),
                  ("SEWERS_TO_EDANA", "sewer_start", "edana_from_sewers")]
    chat_at = "NE-A3" if helena else "sewer_entrance"
    lines = []
    for step, (what, trigger, shot) in enumerate(route, 1):
        marker = f"BW_T{loop}_{step}_{what}"
        if trigger is None:
            lines += [f"echo {marker}", *long_wait]
            continue
        extra = [f"say {chat}_{loop}"] if trigger == chat_at else []
        lines += cross(marker, trigger, f"{prefix}{loop}_{step}_{shot}" if shots else None, extra)
        if what == "GATE":
            lines.append(gate_wait)
    return lines


def write(name, lines):
    cfg = msr / name
    cfg.write_text("\n".join(lines) + "\n", encoding="ascii")
    print(cfg)


if len(sys.argv) > 1 and sys.argv[1] == "pair":
    prefix = sys.argv[2] if len(sys.argv) > 2 else "P"
    a = join("BigWorldTester")
    a += cross("BW_PA_1_GATE", "SE-A3") + [gate_wait]
    a += cross("BW_PA_2_TO_THORNLANDS", "a3trans")
    a += cross("BW_PA_3_TO_HELENA", "NE-A3", f"{prefix}A_3_helena", ["say tour_chat_A"])
    # off the arrival, beyond ms_region_preload_range (1500) of the gate back to Thornlands: 1500 frames
    # of noclip flight only covered ~1200 units (9983 9120 -> 9983 10334), so fly 4000 (~3200 units)
    a += ["echo BW_PA_4_PARK", "god", "noclip", "+forward", "wait 4000", "-forward", "wait 100", ent_info,
          f"screenshot scrshots/{prefix}A_4_parked.png", "wait 50"]
    for n in range(1, 17):  # 48800 frames: well past B's tour (38650 frames) at the same frame rate
        a += [f"echo BW_PA_5_PARKED_{n}", "wait 3000", ent_info, "wait 50"]
    a += ["say tour_chat_A_end", "wait 100", "echo BW_DONE", "quit"]
    write("bigworld_test_a.cfg", a)
    ent_info = "ent_info 2"  # B joins after A, so B's player is edict 2
    b = join("BigWorldTesterB", create="TourB")
    for loop in (1, 2):
        b += tour_loop(loop, f"{prefix}B", shots=False, helena=False, chat="tour_chat_B")
    b += tour_loop(3, f"{prefix}B", shots=True, helena=False, sewers=False, chat="tour_chat_B")
    b += ["echo BW_DONE", "quit"]
    write("bigworld_test_b.cfg", b)
else:
    prefix = sys.argv[1] if len(sys.argv) > 1 else "T"
    loops = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    lines = join("BigWorldTester")
    for loop in range(1, loops + 1):
        lines += tour_loop(loop, prefix, shots=loop in (1, loops))
    lines += ["echo BW_DONE", "quit"]
    write("bigworld_test.cfg", lines)
