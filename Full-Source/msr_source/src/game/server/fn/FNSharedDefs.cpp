//
// FN Shared Definitions
//

#include "rapidjson/document.h"
#include "FNSharedDefs.h"
#include "msdllheaders.h"
#include "player.h"
#include "global.h"
#include "crc/crchash.h"
#include "RequestManager.h"
#include "mslogger.h"

// Requests
#include "ValidateConReq.h"
#include "ValidateScriptsReq.h"
#include "ValidateMapReq.h"
#include "CreateCharacterReq.h"
#include "UpdateCharacterReq.h"
#include "LoadCharacterReq.h"
#include "DeleteCharacterReq.h"

#include <map>
#include <string>
#include <utility>
#include <vector>

constexpr unsigned int STRING_BUFFER = 1024;

// AsyncSendRequest does not make use the connection pooling.
// Frequent requests should make use the RequestManager to take advantage of
// libcurl's async features and connection pooling.

void FNShared::Print(const char* fmt, ...)
{
	static char string[STRING_BUFFER];

	va_list argptr;
	va_start(argptr, fmt);
	vsnprintf(string, sizeof(string), fmt, argptr);
	va_end(argptr);

	MS_INFO("[FuzzNet] %s", string);
}

bool FNShared::IsSlotValid(int slot)
{
	return ((slot >= 0) && (slot < MAX_CHARSLOTS));
}

bool FNShared::IsEnabled(void)
{
#ifdef MSR_STANDALONE
	// Private FN also stores characters for local/LAN hosts. The network
	// browser's LAN setting must not change the character storage backend.
	return (MSGlobals::CentralEnabled && MSGlobals::ServerSideChar);
#else
	return (MSGlobals::CentralEnabled && !MSGlobals::IsLanGame && MSGlobals::ServerSideChar);
#endif
}

static bool SendBlockingRequest(HTTPRequest* req)
{
	CURLSH* share = g_FNRequestManager.GetShareHandle();
	if (share)
		req->SetShareHandle(share);

	return req->AsyncSendRequest();
}

bool FNShared::SendBlocking(HTTPRequest* req)
{
	return req && SendBlockingRequest(req);
}

// {"status":..,"code":..,"data":<bool>} -> data; false for anything else (never assert on odd replies)
static bool ReplyBool(const std::string& body)
{
	JSONDocument doc = HTTPRequest::ParseJSON(body.c_str());
	if (!doc.IsObject() || !doc.HasMember("data") || !doc["data"].IsBool())
		return false;

	return doc["data"].GetBool();
}

static bool QueueSlotRequest(HTTPRequest* pReq, charinfo_t& CharInfo, decltype(charinfo_t::Status) prevStatus)
{
	if (g_FNRequestManager.QueueRequest(pReq))
		return true;

	CharInfo.Status = prevStatus;
	CharInfo.m_CachedStatus = CDS_UNLOADED; // force an update!
	return false;
}

// Send validation requests to the FN backend.
bool FNShared::Validate(void)
{
	if (IsEnabled() == false)
		return false;

	if (ValidateMap() && ValidateSC())
		return true;

	return false;
}

bool FNShared::ValidateFN(void)
{
	if (IsEnabled() == false)
		return true;

	std::unique_ptr<HTTPRequest> pReq(new ValidateConRequest("/api/v2/internal/ping"));
	const auto req = pReq.get();
	if (SendBlockingRequest(req))
		return ReplyBool(req->m_sResponseBody);

	return false;
}

bool FNShared::ValidateMap(void)
{
	if (IsEnabled() == false)
		return true;

	char mapFile[MAX_PATH];
	_snprintf(mapFile, sizeof(mapFile), "%s/maps/%s.bsp", MSGlobals::AbsGamePath.c_str(), MSGlobals::MapName.c_str());
	unsigned int mapFileHash = GetFileCheckSum(mapFile);

	std::unique_ptr<HTTPRequest> pReq(new ValidateMapRequest(UTIL_VarArgs("/api/v2/internal/map/%s/%u", MSGlobals::MapName.c_str(), mapFileHash)));
	const auto req = pReq.get();
	if (SendBlockingRequest(req))
		return ReplyBool(req->m_sResponseBody);

	return false;
}

bool FNShared::ValidateSC(void)
{
	if (IsEnabled() == false)
		return true;

	char scFile[MAX_PATH];
	_snprintf(scFile, sizeof(scFile), "%s/scripts.pak", MSGlobals::AbsGamePath.c_str());
	unsigned int scFileHash = GetFileCheckSum(scFile);

	std::unique_ptr<HTTPRequest> pReq(new ValidateScriptsRequest(UTIL_VarArgs("/api/v2/internal/sc/%u", scFileHash)));
	const auto req = pReq.get();
	if (SendBlockingRequest(req))
		return ReplyBool(req->m_sResponseBody);

	return false;
}

// Check if player has BANNED flag.
bool FNShared::IsBanned(int flags)
{
	return (flags & FN_FLAG_BANNED) == FN_FLAG_BANNED;
}

// Check if player has DONOR flag.
bool FNShared::IsDonor(int flags)
{
	return (flags & FN_FLAG_DONOR) == FN_FLAG_DONOR;
}

// Check if player has ADMIN flag.
bool FNShared::IsAdmin(int flags)
{
	return (flags & FN_FLAG_ADMIN) == FN_FLAG_ADMIN;
}

// Single-flight character saves. Autosaves run every 5-10 s and FN gives no ordering between
// two requests in flight, so an older blob could land last. At most one PUT per (account,
// slot) is on the wire; while it is, only the newest blob waits and goes out when the first
// one ends (answered or failed). Entries only store bytes, never player pointers, so a
// reply after the player left (or during the next map's load) is harmless.
namespace
{
struct held_save_t
{
	bool inFlight = false;
	bool held = false;	// blob/url below wait for the PUT in flight
	std::string url;
	std::string blob;
};
std::map<std::pair<unsigned long long, int>, held_save_t> g_Saves;

// The entry may be looked up again (or its flag reset) from inside QueueRequest when the
// queue refuses the request: its destructor reports the save as finished.
void SendSave(unsigned long long steamID, int slot, const char* url, const char* data, size_t size)
{
	g_Saves[std::make_pair(steamID, slot)].inFlight = true;

	if (!g_FNRequestManager.QueueRequest(new UpdateCharacterRequest(steamID, slot, url, data, size)))
		FNShared::Print("Failed to queue save for %llu slot %i!", steamID, slot);
}

// A save of this account/slot still on its way (in flight or waiting behind one)
bool SaveBusy(unsigned long long steamID, int slot)
{
	auto it = g_Saves.find(std::make_pair(steamID, slot));
	return (it != g_Saves.end()) && (it->second.inFlight || it->second.held);
}

// Character loads that wait for such a save: loading now would return the older copy, and the
// player's next autosave would then overwrite the newer one (a quick reconnect on a slow FN).
struct deferred_load_t
{
	int index;						// player slot
	unsigned long long steamID;
	int slot;
	decltype(charinfo_t::Status) prevStatus;
	float when;						// gpGlobals->time; a smaller time later means a new map
};
std::vector<deferred_load_t> g_DeferredLoads;

// True when the load was put off (CharInfo stays CDS_LOADING until ThinkSaves sends it)
bool DeferLoad(CBasePlayer* pPlayer, int slot, decltype(charinfo_t::Status) prevStatus)
{
	if (!SaveBusy(pPlayer->steamID64, slot))
		return false;
	g_DeferredLoads.push_back({pPlayer->entindex(), pPlayer->steamID64, slot, prevStatus, gpGlobals->time});
	return true;
}
}

// Load all characters!
void FNShared::LoadCharacter(CBasePlayer* pPlayer)
{
	if ((pPlayer == NULL) || (pPlayer->steamID64 == 0ULL))
		return;

	for (unsigned int i = 0; i < MAX_CHARSLOTS; i++)
	{
		charinfo_t& CharInfo = pPlayer->m_CharInfo[i];

		if (CharInfo.Status == CDS_LOADING)
			continue;

		const auto prevStatus = CharInfo.Status;

		CharInfo.m_CachedStatus = CDS_UNLOADED;
		CharInfo.Status = CDS_LOADING;

		if (DeferLoad(pPlayer, (int)i, prevStatus))
			continue;

		if (!QueueSlotRequest(new LoadCharacterRequest(pPlayer->steamID64, i,
				UTIL_VarArgs("/api/v2/internal/character/%llu/%i", pPlayer->steamID64, i)),
				CharInfo, prevStatus))
		{
			FNShared::Print("Failed to queue character load for %llu slot %u!", pPlayer->steamID64, i);

			// The only failure mode today is a manager that isn't loaded, so the
			// remaining slots would fail identically. Remove this break if
			// QueueRequest ever grows per-request failure modes.
			break;
		}
	}
}

// Load a specific character!
void FNShared::LoadCharacter(CBasePlayer* pPlayer, int slot)
{
	if ((pPlayer == NULL) || (pPlayer->steamID64 == 0ULL) || !IsSlotValid(slot))
		return;

	charinfo_t& CharInfo = pPlayer->m_CharInfo[slot];

	if (CharInfo.Status == CDS_LOADING)
		return;

	const auto prevStatus = CharInfo.Status;

	CharInfo.m_CachedStatus = CDS_UNLOADED;
	CharInfo.Status = CDS_LOADING;

	if (DeferLoad(pPlayer, slot, prevStatus))
		return;

	if (!QueueSlotRequest(new LoadCharacterRequest(pPlayer->steamID64, slot,
			UTIL_VarArgs("/api/v2/internal/character/%llu/%i", pPlayer->steamID64, slot)),
			CharInfo, prevStatus))
	{
		FNShared::Print("Failed to queue character load for %llu slot %i!", pPlayer->steamID64, slot);
	}
}

void FNShared::CharacterSaveFinished(unsigned long long steamID, int slot, bool bAborted)
{
	auto it = g_Saves.find(std::make_pair(steamID, slot));
	if (it == g_Saves.end())
		return;

	it->second.inFlight = false;

	// A dropped request may be inside the queue's own teardown: never queue from there,
	// ThinkSaves sends the held blob instead.
	if (bAborted || !it->second.held)
		return;

	std::string url, blob;
	url.swap(it->second.url);
	blob.swap(it->second.blob);
	it->second.held = false;
	SendSave(steamID, slot, url.c_str(), blob.data(), blob.size());
}

void FNShared::ThinkSaves(void)
{
	for (auto it = g_Saves.begin(); it != g_Saves.end();)
	{
		held_save_t& save = it->second;
		if (save.inFlight)
		{
			++it;
			continue;
		}

		if (!save.held)
		{
			it = g_Saves.erase(it);
			continue;
		}

		const unsigned long long steamID = it->first.first;
		const int slot = it->first.second;
		std::string url, blob;
		url.swap(save.url);
		blob.swap(save.blob);
		save.held = false;
		++it; // SendSave only touches its own entry, never erases
		SendSave(steamID, slot, url.c_str(), blob.data(), blob.size());
	}

	for (size_t i = 0; i < g_DeferredLoads.size();)
	{
		const deferred_load_t d = g_DeferredLoads[i];
		if (SaveBusy(d.steamID, d.slot) && gpGlobals->time >= d.when)
		{
			++i;
			continue;
		}
		g_DeferredLoads.erase(g_DeferredLoads.begin() + i);
		if (gpGlobals->time < d.when)
			continue; // from a previous map: the player loads again on this one
		CBasePlayer* pPlayer = (CBasePlayer*)UTIL_PlayerByIndex(d.index);
		if ((pPlayer == NULL) || (pPlayer->steamID64 != d.steamID))
			continue; // left, or someone else has the slot now
		charinfo_t& CharInfo = pPlayer->m_CharInfo[d.slot];
		if (CharInfo.Status != CDS_LOADING)
			continue;
		if (!QueueSlotRequest(new LoadCharacterRequest(d.steamID, d.slot,
				UTIL_VarArgs("/api/v2/internal/character/%llu/%i", d.steamID, d.slot)),
				CharInfo, d.prevStatus))
			FNShared::Print("Failed to queue character load for %llu slot %i!", d.steamID, d.slot);
	}
}

// Create or Update FN character!
void FNShared::CreateOrUpdateCharacter(CBasePlayer* pPlayer, int slot, const char* data, size_t size, bool bIsUpdate)
{
	if ((pPlayer == NULL) || (pPlayer->steamID64 == 0ULL) || (data == NULL) || (size == 0) || !IsSlotValid(slot))
		return; // Quick validation - steamId is vital.

	if (bIsUpdate && (pPlayer->m_CharacterState == CHARSTATE_UNLOADED))
		return; // You cannot update your char (save) if there is no char loaded.

	charinfo_t& CharInfo = pPlayer->m_CharInfo[slot];

	if (!bIsUpdate && (CharInfo.Status == CDS_LOADING))
		return; // Busy, wait for callback!

	char pchApiUrl[REQUEST_URL_SIZE];

	if (bIsUpdate)
	{
		_snprintf(pchApiUrl, REQUEST_URL_SIZE, "/api/v2/internal/character/%s", CharInfo.Guid);

		auto it = g_Saves.find(std::make_pair(pPlayer->steamID64, slot));
		if ((it != g_Saves.end()) && (it->second.inFlight || it->second.held))
		{
			// Replaces any older held blob: only the newest state matters (ThinkSaves sends it
			// when nothing is in flight, so it can never land before an older one)
			it->second.held = true;
			it->second.url = pchApiUrl;
			it->second.blob.assign(data, size);
			return;
		}

		SendSave(pPlayer->steamID64, slot, pchApiUrl, data, size);
	}
	else
	{
		_snprintf(pchApiUrl, REQUEST_URL_SIZE, "/api/v2/internal/character/");

		const auto prevStatus = CharInfo.Status;

		CharInfo.m_CachedStatus = CDS_UNLOADED;
		CharInfo.Status = CDS_LOADING;

		if (!QueueSlotRequest(new CreateCharacterRequest(
				pPlayer->steamID64, slot, pchApiUrl, data, size), CharInfo, prevStatus))
		{
			FNShared::Print("Failed to queue character creation for %llu slot %i!", pPlayer->steamID64, slot);
		}
	}
}

void FNShared::DeleteCharacter(CBasePlayer* pPlayer, int slot)
{
	if ((pPlayer == NULL) || (pPlayer->steamID64 == 0ULL) || !IsSlotValid(slot))
		return;

	charinfo_t& CharInfo = pPlayer->m_CharInfo[slot];

	if (CharInfo.Status == CDS_LOADING)
		return;

	const auto prevStatus = CharInfo.Status;

	char pchApiUrl[REQUEST_URL_SIZE];
	_snprintf(pchApiUrl, REQUEST_URL_SIZE, "/api/v2/internal/character/%s", CharInfo.Guid);

	CharInfo.m_CachedStatus = CDS_UNLOADED;
	CharInfo.Status = CDS_LOADING;

	if (!QueueSlotRequest(new DeleteCharacterRequest(
			pPlayer->steamID64, slot, pchApiUrl, static_cast<int>(prevStatus)),
			CharInfo, prevStatus))
	{
		FNShared::Print("Failed to queue character deletion for %llu slot %i!", pPlayer->steamID64, slot);
	}
}
