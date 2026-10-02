# Daragoth mouse-look repair

The private preview's generated `config.cfg` had lost the original `+mlook`
setting. Before touching a horse, the native client held `in_mlook.state = 0`.
The existing input mapping then converted a mouse-Y delta of 32 into forward
movement -96, with zero pitch change. Restoring `+mlook` gave pitch +2.112 and
zero forward, side or vertical movement at the unchanged sensitivity of 3.

Mounting, dismounting and the first/third-person commands do not alter mlook.
Do not force it on those transitions: deliberate mlook-off preferences, inverted
pitch and custom sensitivity must remain valid. Repair the missing setting once,
with the interactive preview closed, using `restore_preview_mouse_look.py` and
an explicitly selected game path and fresh private backup directory. It preserves
every other config byte and refuses an explicit `-mlook` instruction. The optional
userconfig still executes afterward and can override the setting.

All automated clients must use `-nowriteconfig`. Xash otherwise serializes their
current input state back into `config.cfg` at shutdown. The local `lab.py`,
`mount_audit.py` and combined meadow smoke launcher have been corrected. The
human-operated `Play-Daragoth.ps1` launcher still permits saving real preferences.
There is no evidence attributing the first loss to one particular earlier fixture.

## Native evidence

`Reports/daragoth-mouse-look-20261002.json` records 38 passing checks in the
detached synthetic realm (UDP27249, FN5842). Three real native mounts and normal
client Use dismounts retained vertical look with zero mouse-generated movement.
An additional ride preserved intentionally disabled mlook, sensitivity4.7 and
inverted m_pitch-0.031. First/third-person switches also preserved these settings.
The test client left the copied interactive config byte-identical after quitting.
Three additional startup checks applied the actual backed-up repair script to the
detached config, launched a fresh native client without issuing runtime `+mlook`,
observed its real mlook button active, and verified a normal quit with unchanged
config bytes. An earlier main-menu probe ran before useful logging and returned
no probe lines; the successful startup check uses the independent state reader.

The Debug-only `ms_mouse_probe <label> <vertical delta>` command calls the exact
production mouse mapping with synthetic deltas. It does not move the OS cursor,
move the player/camera, modify preferences or consume button state. Release builds
do not register the command. The mapping was extracted unchanged from
`IN_MouseMove`; no mount or server movement behavior was changed.

The input-state reader uses read-only process memory and the existing `KB_Find`
list to independently observe actual client mlook state. Its Win32/MSVC Debug
instruction decoder deliberately rejects unfamiliar binaries.

## Reproduction and limitations

Prepare the existing synthetic audit runtime and build Win32 Debug with
`build_game.ps1`. Keep the initial detached fixture's config without `+mlook` to
reproduce the reported baseline; do not disable the user's live preferences.
Start the detached server after installing the selected meadow and wait for it
to become ready. Run `test_mount_mouse_look.py --lab <private lab directory>`.
It requires the existing private audit helper, synthetic character slot2, and
loopback server/FN. Never point the fixture at real profiles or public realms.

The successful evidence was recovered by supervised postprocessing after the
test incorrectly waited for an echo placed after `quit`. All probes and ride
transitions had already completed; the native client exited normally. The runner
now waits for process exit instead. Earlier helper-return, stale-log and sign-on
harness failures are retained in the private audit folder. The published report
does not claim a fully unattended run or a physical-mouse visual test.

The functional repair is the missing configuration setting, not a discovered
horse lifecycle defect. Preview config restoration and any DLL update must be
coordinated with map staging, with backups and current process identity checks.
