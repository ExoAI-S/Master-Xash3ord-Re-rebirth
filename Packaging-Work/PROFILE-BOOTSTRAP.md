# Standalone client profile initialization

The Enhanced Windows client uses the same durable `player-profile.json` as the native launcher. `Initialize` validates the current and sibling version's files under the shared `.player-profile.lock`, securely creates a key only if neither version has one, and synchronously sets `_fnid`. Malformed or conflicting files stop initialization without replacing their contents. Stable's client binary is unchanged.

The validated key is cached in memory. At the start of `HUD_Frame`, the client compares the current `_fnid` with that key and restores it only when it differs. This prevents a stale `setinfo _fnid` line in `config.cfg` from selecting a different identity. The frame hook does not read files, generate keys, acquire locks, or change a profile file. A manually restored profile takes effect after restarting the game.

The shipped Xash engine source establishes the required ordering:

- `engine/common/host.c:1240` calls `CL_Init`, which loads the game client and calls its `Initialize` hook.
- `engine/common/host.c:1272-1288` subsequently executes startup configuration, including `config.cfg` and user configuration; command-line configuration follows at line 1297.
- `engine/client/dll_int/cl_game.c:2780` implements `PlayerInfo_SetValueForKey` by updating `cls.userinfo` immediately.
- `engine/client/cl_main.c:3907` calls the client frame hook before reading challenge replies at line 3913 and before initiating or retrying connections at line 3926.
- `engine/client/cl_main.c:1319` sends the connect packet using the current `cls.userinfo`.

The profile helper's 20 native x86 C++ checks cover creation, reuse, conflict preservation, malformed input, UTF-8 BOM and metadata preservation, sharing-violation retries, and simultaneous launches of both versions. The later frame hook leaves the tested file helper unchanged; its integration check is the rebuilt Debug client plus a direct launch with a stale configuration identity. Such a runtime check must verify the connected identity without printing its private key. GUI playtesting remains separate from source-order verification.

The profile key identifies the player; it does not move character data. Direct local saves and characters in an FN database remain separate stores. The host/version controller is responsible for switching the FN database with backups.
