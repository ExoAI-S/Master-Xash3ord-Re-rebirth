# MSR PrimeXT DM Debug edition — 2026-09-12

The Enhanced client and server were compiled as Debug with `/Zi /Od /Ob0
/RTC1` and the project's existing static CRT setting. Matching `client.pdb`
and `ms.pdb` are beside their DLLs; linker maps are in `Debug-Symbols/Enhanced`.
The engine executable/renderers are unchanged; matching engine PDBs are included.

## Confirmed findings and changes

- Magic frame sprites were submitted before their model was assigned, so the
  engine rejected them. They are now fully initialized before submission.
- Six-argument dynamic lights read a nonexistent optional flag. Required
  arguments and optional flags now have correct bounds checks.
- Script getter dispatch and five number/vector formatters returned pointers
  into destroyed strings. Getter results now retain storage, and formatters use
  a thread-local ring of return buffers. This repairs corrupted spell endpoints,
  widths and sound positions without changing the script or network formats.
- The downloaded-file security marker can cause the bundled PowerShell runtime
  to reject unsigned launcher scripts under its existing RemoteSigned setting.
  A marked, harmless script reproduced the rejection. The new entry points use
  a native launcher and bundled Python; no Windows execution policy was changed.
- A fresh direct executable launch followed by Create Game / Edana repeatedly
  rejected its own connection for missing `_fnid`. It remained responsive and
  did not produce an access violation. Enhanced now loads or securely creates
  its persistent player profile during client initialization, using the same
  profile and cross-version lock as the launcher.
- Create Game left central FN disabled. The local host launcher now writes FN
  settings for the Enhanced listen server after confirming its owned FN is ready.
  The standalone game no longer disables private FN simply because `sv_lan=1`.
- Host shutdown now retains state and FN when a live realm's ownership cannot
  be verified, instead of reporting a successful stop and abandoning a server.
- Native Enhanced/Stable switching preserves FN database snapshots and player
  identity using the existing verified transfer helper. Stable game assets stay
  unchanged.

## Evidence

- An isolated Debug client displayed the Erratic Lightning hand glow after the
  sprite fix. A real cast initially reached the client but played its positional
  sound at `(0,0,0)`. After the string-lifetime fixes, a subsequent cast received
  endpoints `(-2249.29,-2432.03,-9.41)` and `(-2249.29,-2432.03,4086.59)`;
  the spell then invoked `weather/lightning.wav` at its ground impact position
  `(-2249.29,-2432.03,-143.97)` with volume 0.70. The test client remained running.
- The rendering regression executes the actual light/frame-sprite code with
  checked arguments and the engine's model requirement. The lifetime regression
  compiles the real string implementation, formatter helpers and getter dispatch;
  it checks stack reuse, 16 outstanding results, nested getters and thread
  isolation. Both suites pass and detect mutations restoring the original bugs.
- A temporary spell-grant fixture was confined to the loopback test server.
  Production source was restored byte-for-byte and rebuilt with the normal
  lockdown guards. The final server DLL excludes the QA grant marker.
- Before the startup changes, a Debug client loaded a playable character on one
  isolated dedicated realm, then loaded the same character on the second realm.
  The isolated FN database contained one active character and four revisions.
- The corrected profile helper passed 20 native C++ checks: first launch,
  reuse, cross-version reuse, malformed/conflicting identities, UTF-8 BOM and
  metadata, sharing violations, and simultaneous cross-version creation.
- The actual FN predicate was compiled in standalone and original modes;
  all 16 combinations of central/LAN/server-character settings passed.
- A real dedicated server using the corrected Debug DLL retained `sv_lan=1`
  across an Edana reload and logged FN connection, script validation and map
  validation success. Both test realms then shut down with an FN backup.
- The new native controller passed isolated lifecycle/switch tests and real
  Enhanced → Stable → Enhanced hosting tests. Both versions loaded Edana and
  responded to A2S. Shutdown saved FN backups and freed both realm ports.
- Fourteen controller regression tests passed, including identity-conflict
  refusal before save transfer and disabling generated FN listen settings when
  the host is successfully stopped. A final real start/stop verified that cleanup.
- The real version-switch test transferred a labelled synthetic database marker
  both ways and verified prior database snapshots. This was a database migration
  test, not a second playable-character test.
- The diagnostic collector successfully read local Windows crash events and
  produced a report from an isolated installation.

## Limits

Computer-use screenshots do not capture PC audio. The lightning test verified
the sound file, engine call and corrected position; it is not a listening test
of the user's speaker/headphone output.

The friend's `0xC0000005` exception remains unconfirmed without their actual
faulting module/offset or dump. No speculative `g_pGameRules` null check was
added. The inspected `AttemptToMaterialize` call is server-side and may be
relevant to local hosting, but no crash evidence currently identifies it.

Computer control stopped after Escape, so the corrected Create Game UI flow
and new launcher/DM windows have not received a complete visual retest. Injected
keyboard behavior was inconclusive; mouse menu clicks worked in the reproduced
case. Public UDP server queries responded, but this is not proof of a complete
join from a friend's external network.

The local FN database and the original host's public FN database are separate.
This package includes neither existing player identities nor character saves.
