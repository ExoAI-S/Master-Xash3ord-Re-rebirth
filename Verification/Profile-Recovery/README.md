# Profile recovery regression checks

Run `tests/Build-And-Test.ps1` from a writable copy of this folder on Windows.
The script uses the Windows .NET Framework C# compiler and Python on PATH.
It compiles the prior and current launcher source, creates inert local fixtures,
runs 125 recovery assertions, renders offscreen forms, and checks EXE/PDB pairing.
Generated fixtures contain synthetic identities and never contact FN or launch
the game. Keep generated files out of a release or source commit.

The unchanged baseline reproduces the different identity created after a move
to a new installation. The current build exercises unique-profile discovery,
explicit selection for conflicts, exact profile backups, cancellation, running
client and lock guards, source/target drift, and rollback after a second replace
fails. Physical picker clicks and a friend's own computer are not covered.
