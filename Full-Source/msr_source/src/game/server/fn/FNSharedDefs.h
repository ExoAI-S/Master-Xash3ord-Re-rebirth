//
// FN Shared Definitions
//

#ifndef FN_SHAREDDEFS_H
#define FN_SHAREDDEFS_H

#include "rapidjson/fwd.h"
#include <Platform.h>
#include <memory>

class CBasePlayer;
class HTTPRequest;

// This has match up with user flags defined in the FN server!
enum FNPlayerFlags
{
	FN_FLAG_BANNED = (1 << 0),
	FN_FLAG_DONOR = (1 << 1),
	FN_FLAG_ADMIN = (1 << 2),
};

namespace FNShared
{
	void Print(const char* fmt, ...);
	bool IsSlotValid(int slot);
	bool IsEnabled(void);
	bool Validate(void);
	bool ValidateMap(void);
	bool ValidateSC(void);
	bool ValidateFN(void);
	
	bool IsBanned(int flags);
	bool IsDonor(int flags);
	bool IsAdmin(int flags);
	void LoadCharacter(CBasePlayer* pPlayer);
	void LoadCharacter(CBasePlayer* pPlayer, int slot);
	void CreateOrUpdateCharacter(CBasePlayer* pPlayer, int slot, const char* data, size_t size, bool bIsUpdate);
	void DeleteCharacter(CBasePlayer* pPlayer, int slot);

	// Sends on a worker thread while the game thread waits (bounded by the curl timeouts);
	// the request's OnResponse has run when this returns. The caller keeps ownership.
	bool SendBlocking(HTTPRequest* req);

	// Character saves are single-flight per (account, slot); see CreateOrUpdateCharacter.
	void CharacterSaveFinished(unsigned long long steamID, int slot, bool bAborted); // UpdateCharacterRequest
	void ThinkSaves(void); // every frame, and before draining: sends saves held behind a dropped one
}

#endif // FN_SHAREDDEFS_H