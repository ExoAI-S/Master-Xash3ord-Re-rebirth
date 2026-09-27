"""Write, drive and check the scripted boss respawn timer test (Thornlands Queen, boss.thornlands.queen).

The scripted client (sandbox\\game\\msr\\bigworld_test.cfg) only walks and fires map entities; an
rcon driver run next to it watches "msr_bosses" and does the server side (kill, region unload and
reload, reset). The driver reads the rcon password from sandbox\\rcon.txt itself and never prints
it. Both phases need the new ms.dll, the bigworld5 map with msr_boss keys, ms_realm "sandbox" in
server_sandbox.cfg and (phase 2) the sandbox FN with the world endpoints.

Phase 1: kill, then the hold after a region unload/reload
  python tools\\write_boss_test_cfg.py kill
  start python tools\\write_boss_test_cfg.py drive kill boss1          (driver first; it waits for the server)
  powershell -File tools\\run_lifecycle_test.ps1 -Name boss1 -UnloadSeconds 600 -ClientSeconds 900
      Client: join, Edana -> Thornlands (a3trans), "ent_fire wave4 use" (the Queen's spawner; the
      stock chain is flesh sac -> sstart -> three waves -> sstart4 -> wave4). Driver: sees the Queen
      alive, "msr_bosses kill queen" (credited to player 1). Client: back to Edana and into the
      Sewers. Driver: msr_region_unload thornlands, msr_region_load thornlands. Client: back to
      Thornlands, fires wave4 again. Driver: the Queen must be "held, N min left, kept from
      spawning, exits opened" (break3 fired instead of her death).

Phase 2: the hold after a server restart (the timer comes back from FN), then reset
  python tools\\write_boss_test_cfg.py restart
  start python tools\\write_boss_test_cfg.py drive restart boss2
  powershell -File tools\\run_lifecycle_test.ps1 -Name boss2 -UnloadSeconds 600 -ClientSeconds 900
      Client: join, Thornlands, fire wave4. Driver: Queen held (kept from spawning, exits opened);
      "msr_bosses reset queen" (she stays away in this instance: her exits were opened); client
      goes to the Sewers; driver unloads and reloads Thornlands; client comes back and fires wave4:
      the Queen must spawn (alive). The driver ends with "msr_bosses reset all" so no timer is left.

Check (reads <prefix>-driver.log, written by the driver, and <prefix>-server.log from the runner):
  python tools\\write_boss_test_cfg.py check sandbox\\logs\\boss1 [sandbox\\logs\\boss2]

Expected lines (server console / -log; lines printed while an rcon command runs may only be in
the rcon reply, which the driver log keeps):
  phase 1  MSR: boss boss.thornlands.queen killed by msr_bosses (credited to BigWorldTester)
           MSR: boss boss.thornlands.queen killed, back in 30 min
           MSR: region thornlands unloaded (command): ...
           MSR: region thornlands loaded (command): N entities re-created ...
           MSR: boss boss.thornlands.queen held, back in 30 min (spawner wave4)       (29 or 30)
           MSR: boss boss.thornlands.queen: fired break3 as if it had died; it stays away until its region reloads
  phase 2  MSR: worldstate sandbox/edana: N keys loaded from FN
           MSR: boss boss.thornlands.queen held, back in <30 min (spawner wave4)
           MSR: boss boss.thornlands.queen: fired break3 as if it had died; ...
           MSR: boss boss.thornlands.queen timer reset
           MSR: boss boss.thornlands.queen already opened its exits here: it stays away until thornlands reloads
           MSR: region thornlands unloaded (command) / loaded (command)
           then msr_bosses shows the Queen "alive" (no new "held" line after the reload)
With FN off or without world endpoints phase 1 still passes (in memory) but phase 2 cannot:
"msr_bosses" then says "world state in memory only".
"""
import importlib.util
import re
import sys
import time
from pathlib import Path

W = Path(__file__).resolve().parent.parent
CFG = W / "sandbox" / "game" / "msr" / "bigworld_test.cfg"
LOGS = W / "sandbox" / "logs"
PORT = 27199
KEY = "boss.thornlands.queen"
SPAWNER = "wave4"

JOIN = ["connect 127.0.0.1:27199", "wait 4500", "echo BW_STEP_0_CREATE", "cmd char canjoin", "wait 300", "cmd char 0", "wait 1500"]
HOLD = ["wait 3000"] * 2    # the driver acts meanwhile (seconds at any frame rate the test client runs at)
AWAY = ["wait 3000"] * 4    # region unload + reload by the driver


def client_lines() -> list:
    """The same walk in both phases; only what the driver expects at each spawner fire differs."""
    return [
        'name "BigWorldTester"', "exec masterpiece.cfg", "developer 1", *JOIN,
        "echo BW_BOSS_0_JOINED", "ent_fire SE-A3 touch", "wait 300",   # to Edana, wherever the character was saved
        "echo BW_BOSS_1_TO_THORNLANDS", "ent_fire a3trans touch", "wait 400", "ent_info 1",
        "echo BW_BOSS_2_FIRE_SPAWNER", f"ent_fire {SPAWNER} use", *HOLD,
        # the Sewers are away from every way into Thornlands, so nothing loads it ahead meanwhile
        "echo BW_BOSS_3_TO_SEWERS", "ent_fire SE-A3 touch", "wait 300", "ent_fire sewer_entrance touch", *AWAY,
        "echo BW_BOSS_4_BACK_TO_THORNLANDS", "ent_fire sewer_start touch", "wait 300", "ent_fire a3trans touch", "wait 400",
        "echo BW_BOSS_5_FIRE_SPAWNER_AGAIN", f"ent_fire {SPAWNER} use", *HOLD,
        "echo BW_DONE", "quit",
    ]


# ---------------------------------------------------------------------------- driver
class Driver:
    def __init__(self, name: str, port: int):
        spec = importlib.util.spec_from_file_location("gq", r"C:\MSR\Portable-Package\FN\game_query.py")
        self.gq = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.gq)
        self._pw = (W / "sandbox" / "rcon.txt").read_text(encoding="utf-8-sig").strip()
        self.port = port
        LOGS.mkdir(parents=True, exist_ok=True)
        self.log = open(LOGS / f"{name}-driver.log", "w", encoding="utf-8")
        self.failed = False

    def note(self, text: str):
        line = f"[{time.strftime('%H:%M:%S')}] {text}"
        print(line, flush=True)
        self.log.write(line + "\n")
        self.log.flush()

    def rcon(self, command: str, quiet: bool = False) -> str:
        try:
            reply = self.gq.rcon(self.port, self._pw, command)
        except OSError as exc:
            reply = f"(rcon failed: {exc})"
        if not quiet:
            self.note(f"> {command}")
            for line in reply.splitlines():
                if line.strip():
                    self.log.write("  " + line + "\n")
            self.log.flush()
        return reply

    def result(self, what: str, passed: bool):
        self.note(f"{'PASS' if passed else 'FAIL'} {what}")
        self.failed |= not passed

    def state(self) -> str:
        """The Queen's msr_bosses state text ("alive (hp ...)", "held, 29 min left, ...", "ready")."""
        reply = self.rcon("msr_bosses", quiet=True)
        m = re.search(rf"^\s*{re.escape(KEY)}: ([^|]*)", reply, re.MULTILINE)
        return m.group(1).strip() if m else ""

    def wait_for(self, what: str, pattern: str, timeout: float) -> str:
        """Poll msr_bosses until the Queen's state matches pattern."""
        end = time.time() + timeout
        last = None
        while time.time() < end:
            st = self.state()
            if st != last:
                self.note(f"  {KEY}: {st or '(not listed)'}")
                last = st
            if re.search(pattern, st):
                self.rcon("msr_bosses")
                return st
            time.sleep(0.5)
        self.rcon("msr_bosses")
        self.result(f"{what} (waited {timeout:.0f} s for '{pattern}')", False)
        return ""

    def wait_server(self, timeout: float = 180) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            if "MSR: bosses on" in self.rcon("msr_bosses", quiet=True):
                self.rcon("msr_worldstate list boss.")
                return True
            time.sleep(2)
        self.result("server with msr_bosses answering rcon", False)
        return False

    def reload_thornlands(self, timeout: float = 240) -> bool:
        """Unload Thornlands once the player has left it, then load it again."""
        end = time.time() + timeout
        while time.time() < end:
            reply = self.rcon("msr_region_unload thornlands", quiet=True)
            if re.search(r"region thornlands unloaded \(", reply):  # not "thornlands not unloaded (a player is there)"
                self.note("> msr_region_unload thornlands")
                self.log.write("  " + reply.strip() + "\n")
                reply = self.rcon("msr_region_load thornlands")
                # a player standing near a way in may have made it load ahead already
                ok = bool(re.search(r"region thornlands loaded \(|already loaded", reply))
                self.result("Thornlands unloaded and re-created", ok)
                return ok
            time.sleep(0.5)
        self.result("Thornlands unloaded (the player never left it?)", False)
        return False

    def run_kill(self):
        if not self.wait_server():
            return
        self.rcon(f"msr_bosses reset {KEY}")  # a clean start: an earlier run may have left a timer
        if not self.wait_for("Queen spawned by wave4", r"^alive", 420):
            return
        reply = self.rcon("msr_bosses kill queen")
        self.result("msr_bosses kill queen started her timer", "killed, back in" in reply or bool(re.search(r"^held", self.state())))
        st = self.wait_for("Queen on her timer after the kill", r"^held, \d+ min left", 30)
        self.rcon("msr_worldstate list boss.")
        if not st or not self.reload_thornlands():
            return
        st = self.wait_for("Queen held in the re-created Thornlands", r"kept from spawning", 600)
        if st:
            self.result("hold after a region reload (kept from spawning)", True)
            self.result("her exit (break3) fired instead", "exits opened" in st)

    def run_restart(self):
        if not self.wait_server():
            return
        self.rcon("msr_worldstate list")
        left = re.search(r"held, (\d+) min left", self.state())
        self.result("Queen timer back after the restart", bool(left))
        st = self.wait_for("Queen held after the restart", r"kept from spawning", 420)
        if st:
            self.result("hold after a server restart (kept from spawning)", True)
            self.result("her exit (break3) fired instead", "exits opened" in st)
        reply = self.rcon(f"msr_bosses reset {KEY}")
        self.result("msr_bosses reset queen", "timer reset" in reply)
        st = self.wait_for("Queen waits for a reload after the reset", r"held until thornlands reloads", 30)
        if not self.reload_thornlands():
            return
        st = self.wait_for("Queen spawns again once reset and reloaded", r"^alive", 600)
        if st:
            self.result("reset + reload lets her spawn", True)
        self.rcon("msr_bosses reset all")
        self.rcon("msr_worldstate list boss.")


def drive(phase: str, name: str) -> int:
    d = Driver(name, PORT)
    d.note(f"boss test driver, phase {phase}")
    try:
        d.run_kill() if phase == "kill" else d.run_restart()
    finally:
        d.note("driver done: " + ("FAILED" if d.failed else "all checks passed"))
        d.log.close()
    return 1 if d.failed else 0


# ---------------------------------------------------------------------------- check
EXPECT = {
    "kill": [
        ("kill credited to a player", r"MSR: boss boss\.thornlands\.queen killed by msr_bosses \(credited to "),
        ("timer started at the kill", r"MSR: boss boss\.thornlands\.queen killed, back in 30 min"),
        ("Thornlands unloaded", r"MSR: region thornlands unloaded \("),
        ("Thornlands re-created", r"MSR: region thornlands loaded \("),
        ("held in the new instance", r"MSR: boss boss\.thornlands\.queen held, back in (29|30) min \(spawner wave4\)"),
        ("break3 fired instead", r"MSR: boss boss\.thornlands\.queen: fired break3 as if it had died"),
    ],
    "restart": [
        ("world state loaded from FN", r"MSR: worldstate \S+/edana: \d+ keys loaded from FN"),
        ("held after the restart", r"MSR: boss boss\.thornlands\.queen held, back in \d+ min \(spawner wave4\)"),
        ("break3 fired instead", r"MSR: boss boss\.thornlands\.queen: fired break3 as if it had died"),
        ("reset", r"MSR: boss boss\.thornlands\.queen timer reset"),
        ("held until reload after the reset", r"MSR: boss boss\.thornlands\.queen already opened its exits here"),
        ("Thornlands re-created", r"MSR: region thornlands loaded \("),
    ],
}


def check(prefixes: list) -> int:
    ok = True
    for phase, prefix in zip(("kill", "restart"), prefixes):
        text = ""
        for suffix in ("-server.log", "-driver.log"):
            p = Path(prefix + suffix)
            if p.exists():
                text += p.read_text(encoding="utf-8-sig", errors="replace") + "\n"
            else:
                print(f"(missing {p})")
        print(f"--- {phase}: {prefix}")
        for what, pattern in EXPECT[phase]:
            found = re.search(pattern, text)
            print(f"{'PASS' if found else 'FAIL'} {what}")
            ok &= bool(found)
        fails = re.findall(r"^\[[\d:]+\] FAIL .*$", text, re.MULTILINE)
        for f in fails:
            print("driver " + f)
        ok &= not fails
        for line in text.splitlines():
            if re.search(r"MSR: (boss |region thornlands (un)?loaded|worldstate .*(loaded from FN|FN off|no world))", line):
                print("  " + line.strip())
    print("ALL PASS" if ok else "PROBLEMS FOUND")
    return 0 if ok else 1


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "check" and len(sys.argv) > 2:
        return check(sys.argv[2:4])
    if mode == "drive" and len(sys.argv) > 2 and sys.argv[2] in ("kill", "restart"):
        return drive(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else ("boss1" if sys.argv[2] == "kill" else "boss2"))
    if mode in ("kill", "restart"):
        CFG.write_text("\n".join(client_lines()) + "\n", encoding="ascii")
        print(CFG)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
