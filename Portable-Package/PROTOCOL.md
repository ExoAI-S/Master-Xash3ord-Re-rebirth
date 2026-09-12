# FN compatibility and sources

Private FN implements the **game-facing Nexus/FN v2 API**, not the entire Nexus administration API. It keeps the existing FN terminology and game integration. It has no connection to the official FN database.

| Game request | Response |
| --- | --- |
| `GET /api/v2/internal/ping` | HTTP 200, `data: true` |
| `GET /api/v2/internal/map/{name}/{unsigned_crc32}` | HTTP 200, `data` boolean from the approved manifest |
| `GET /api/v2/internal/sc/{unsigned_crc32}` | HTTP 200, `data` boolean from the scripts manifest |
| `GET /api/v2/internal/character/{steamid64}/{slot}` | HTTP 200 with character; HTTP 204 with no body when empty |
| `POST /api/v2/internal/character/` | HTTP 201 with `data: {id, flags}` |
| `PUT /api/v2/internal/character/{uuid}` | HTTP 200 with the UUID after committing the update |
| `DELETE /api/v2/internal/character/{uuid}` | HTTP 200 with the UUID after a recoverable delete |

Create/update JSON uses `steamid` (a decimal string), `slot` (integer 0–2), `size` (decoded byte count), and `data` (base64 character bytes). A loaded character includes `id`, `flags`, `size`, `data`, `steamid`, and `slot` under the top-level `data` object. Responses also include `status` and `code`.

The current source caps loaded characters at 51,200 bytes; this service enforces that limit on writes. CRC32 is the standard reflected CRC32 used by the game's checksum helper. The archive contains 93 map BSPs; their checksums and the supplied `scripts.pak` checksum are recorded in `FN/content-manifest.json`.

The compatibility setting is:

```text
sv_lan 0
ms_serverchar 3
ms_central_enabled 1
ms_central_addr "127.0.0.1:5710"
```

Do not include `http://` in `ms_central_addr`; the existing game prepends it. FN player flags are banned=1, donor=2, admin=4. Game progression modifiers remain in the supplied game code/scripts.

The legacy game API carries no character session lease or revision token. Writes are serialized by SQLite, and the latest committed update wins. Avoid loading the same character simultaneously on two game servers. The trusted game server chooses player IDs; clients do not connect directly to this API. Loopback binding and source-IP restrictions preserve compatibility without inventing credentials the existing game cannot send. Requests with browser-origin headers or unrecognized Host headers are rejected. Do not put this legacy HTTP API on the public Internet.

Administrative operations use the local CLI. SQLite transactions, online backup snapshots, previous-save revisions, ownership/slot checks, bounded requests and recoverable deletes are implemented in `FN/fn_server.py`. Only the Python standard library is required.

## Primary references inspected September 10, 2026

- [MSR FN description](https://msrebirth.net/Project-Information/fuzznet/) explains central character storage and the FN name.
- [MSR server setup](https://msrebirth.net/Developer-Knowledge-Articles/misc/server-setup/) describes the included dedicated server, Steam app 1961680, launch parameters and configuration.
- [MasterSwordRebirth at 2c28f72](https://github.com/MSRevive/MasterSwordRebirth/tree/2c28f72ec916a2c5d449bc94628c0fb9436a1c6a): `src/game/server/fn/FNSharedDefs.cpp`, `HTTPRequest.cpp`, `LoadCharacterReq.cpp`, `CreateCharacterReq.cpp`, `svglobals.cpp`, `sv_character.cpp`, and `src/game/shared/ms/crc/` provide the client-side protocol, payload limits and checksum behavior.
- [Nexus2 at fc062ef](https://github.com/MSRevive/nexus2/tree/fc062ef635b9477e2228ff9d2b54b0fda863e687): `internal/controller/internal.go`, `internal/payload/payload.go`, `internal/response/response.go`, `internal/middleware/auth.go` and `internal/payload/charfile.go` were cross-checked for response shapes and save-file handling.
- [Python 3.14.7 official release](https://www.python.org/downloads/release/python-3147/): the included Windows x64 embeddable runtime ZIP was verified against SHA-256 `d297e5ff019966817ad8502465176139f2d3d840fa4ed84b13bed399a6ab1f15`.

The supplied game DLL was also inspected and contains the same seven FN endpoint patterns. Runtime testing confirmed its ping, script and map requests against this service. The service is an independent implementation of that protocol, not a copy of the official FN database or a claim of official affiliation.

