//
// Update FN character
//

#include "rapidjson/document.h"
#include "UpdateCharacterReq.h"
#include "FNSharedDefs.h"
#include "msdllheaders.h"
#include "player.h"
#include "util.h"

UpdateCharacterRequest::UpdateCharacterRequest(ID64 steamID, ID64 slot, const char* url, const char* body, size_t bodySize) :
	HTTPRequest(HTTPMethod::PUT, url, body, bodySize, steamID, slot),
	m_bFinished(false)
{
}

UpdateCharacterRequest::~UpdateCharacterRequest()
{
	// Dropped without a reply (queue refused it, or aborted at shutdown)
	if (!m_bFinished)
		FNShared::CharacterSaveFinished(m_iSteamID64, static_cast<int>(m_iSlot), true);
}

void UpdateCharacterRequest::OnResponse(int iRespCode)
{
	// Success or failure alike: the slot's newest held save (if any) goes out now.
	// A failed save is not retried; the next autosave carries the same data anyway.
	m_bFinished = true;
	FNShared::CharacterSaveFinished(m_iSteamID64, static_cast<int>(m_iSlot), false);
}
