//
// Update FN character
//

#ifndef HTTP_UPDATE_CHARACTER_REQUEST_H
#define HTTP_UPDATE_CHARACTER_REQUEST_H

#include "HTTPRequest.h"

class UpdateCharacterRequest : public HTTPRequest
{
public:
	UpdateCharacterRequest(ID64 steamID, ID64 slot, const char* url, const char* body, size_t bodySize);
	~UpdateCharacterRequest();
	void OnResponse(int iRespCode);
	const char* GetName() { return "UpdateCharacterRequest"; }

private:
	// Saves are single-flight per (account, slot): FNShared must hear when this one ends,
	// answered or dropped unsent, or the slot's next save would wait forever.
	bool m_bFinished;

	UpdateCharacterRequest(const UpdateCharacterRequest&);
};

#endif // HTTP_UPDATE_CHARACTER_REQUEST_H
