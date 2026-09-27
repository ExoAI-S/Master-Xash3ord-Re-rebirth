"""Write (and check) the scripted exact-logout-spot test (sandbox\\game\\msr\\bigworld_test.cfg).

Two phases, each run by a runner that starts a fresh FN + dedicated server (so phase 2 is
"after a server restart"). The client's durable profile (_fnid) is forced by client.dll, so
both phases use the same FN character; no setinfo _fnid here on purpose.

  python write_logout_test_cfg.py rejoin
  powershell -File tools\\run_lifecycle_test.ps1 -Name logout1 -UnloadSeconds 15
      Join, go to Thornlands (a3trans), walk off the arrival and turn, wait for the region
      tracker's capture and an autosave (spot A), disconnect, stay away long enough for
      Thornlands to unload, rejoin: the player must be back at spot A (region re-created
      first). Then go to Northern Thornlands (from_thorn_north), walk and turn (spot B),
      wait for an autosave and quit (disconnect save).

  python write_logout_test_cfg.py restart
  powershell -File tools\\run_sandbox_test.ps1 -Name logout2
      Join the restarted server: the player must be back at spot B.

  python write_logout_test_cfg.py check sandbox\\logs\\logout1 [sandbox\\logs\\logout2]
      Compares the ent_info positions in <prefix>-client.log (A before/after the rejoin,
      B before the quit/after the restart) and lists the server's logout-spot lines from
      <prefix>-server.log.

ent_info prints "origin: x y z" / "angles: p y r"; the runners copy the client console to
sandbox\\logs\\<Name>-client.log and the server log to <Name>-server.log.
"""
import re
import sys
from pathlib import Path

W = Path(__file__).resolve().parent.parent
CFG = W / "sandbox" / "game" / "msr" / "bigworld_test.cfg"

JOIN = ["connect 127.0.0.1:27199", "wait 4500", "cmd char canjoin", "wait 300", "cmd char 0", "wait 1500"]
FIRST_JOIN = JOIN[:2] + ["echo BW_STEP_0_CREATE"] + JOIN[2:]  # run_sandbox_test.ps1 prints the log from this marker
SETTLE_AND_SAVE = ["wait 150", "ent_info 1", "wait 1200"]  # capture (0.25 s), then 12 s: an autosave (5-10 s)


def walk_and_turn(forward_frames: int, turn: str) -> list:
    # Off the teleport arrival (a transition spawn could land near it) and a new yaw
    return ["+forward", f"wait {forward_frames}", "-forward", f"+{turn}", "wait 25", f"-{turn}"]


def rejoin_lines() -> list:
    return [
        'name "BigWorldTester"', "exec masterpiece.cfg", "developer 1",
        *FIRST_JOIN, "echo BW_LO_0_JOINED", "ent_info 1",
        "echo BW_LO_1_TO_THORNLANDS", "ent_fire a3trans touch", "wait 500",
        *walk_and_turn(80, "left"),
        "echo BW_LO_2_SPOT_A", *SETTLE_AND_SAVE,
        "echo BW_LO_3_DISCONNECT", "disconnect",
        "wait 2500",  # > ms_region_unload_time 15 s of the lifecycle runner: Thornlands unloads
        "echo BW_LO_4_REJOIN", *JOIN,
        "echo BW_LO_5_REJOINED_EXPECT_SPOT_A", "ent_info 1", "wait 300",
        "echo BW_LO_6_TO_NORTH", "ent_fire from_thorn_north touch", "wait 500",
        *walk_and_turn(60, "right"),
        "echo BW_LO_7_SPOT_B", *SETTLE_AND_SAVE,
        "echo BW_LO_8_QUIT", "echo BW_DONE", "quit",
    ]


def restart_lines() -> list:
    return [
        'name "BigWorldTester"', "exec masterpiece.cfg", "developer 1",
        *FIRST_JOIN, "echo BW_LO_9_RESTARTED_EXPECT_SPOT_B", "ent_info 1", "wait 300",
        "echo BW_DONE", "quit",
    ]


def read_positions(log: Path) -> dict:
    """marker -> (origin, angles) of the first ent_info after each BW_LO_ marker."""
    out, marker = {}, None
    for line in log.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        m = re.search(r"\b(BW_LO_\d+)_", line)
        if m:
            marker = m.group(1)
            out.setdefault(marker, [None, None])
            continue
        if marker and out[marker][0] is None and line.startswith("origin:"):
            out[marker][0] = [float(v) for v in line.split()[1:4]]
        elif marker and out[marker][1] is None and line.startswith("angles:"):
            out[marker][1] = [float(v) for v in line.split()[1:4]]
    return out


def same_spot(a, b) -> bool:
    if not a or not b or None in a or None in b:
        return False
    close = all(abs(x - y) <= 2.0 for x, y in zip(a[0], b[0]))
    yaw = abs((a[1][1] - b[1][1] + 180.0) % 360.0 - 180.0) <= 3.0
    return close and yaw


def check(prefixes: list) -> int:
    ok = True
    p1 = read_positions(Path(prefixes[0] + "-client.log"))
    a, a2, b = p1.get("BW_LO_2"), p1.get("BW_LO_5"), p1.get("BW_LO_7")
    print(f"spot A {a}\nrejoin  {a2}\nspot B {b}")
    ok &= report("same-server rejoin at spot A", same_spot(a, a2))
    if len(prefixes) > 1:
        b2 = read_positions(Path(prefixes[1] + "-client.log")).get("BW_LO_9")
        print(f"restart {b2}")
        ok &= report("rejoin after restart at spot B", same_spot(b, b2))
    for prefix in prefixes:
        server = Path(prefix + "-server.log")
        if server.exists():
            print(f"--- {server.name}")
            for line in server.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                if re.search(r"MSR: .*(rejoined at|logout spot not used|loaded \(.*player rejoining)", line):
                    print(line)
    return 0 if ok else 1


def report(what: str, passed: bool) -> bool:
    print(f"{'PASS' if passed else 'FAIL'} {what}")
    return passed


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "rejoin"
    if mode == "check":
        if len(sys.argv) < 3:
            print(__doc__)
            return 2
        return check(sys.argv[2:4])
    if mode not in ("rejoin", "restart"):
        print(__doc__)
        return 2
    lines = rejoin_lines() if mode == "rejoin" else restart_lines()
    CFG.write_text("\n".join(lines) + "\n", encoding="ascii")
    print(CFG)
    return 0


if __name__ == "__main__":
    sys.exit(main())
