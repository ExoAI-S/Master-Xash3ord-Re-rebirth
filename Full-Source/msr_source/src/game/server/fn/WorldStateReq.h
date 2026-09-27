//
// Persistent world state on FN: load (GET) and batch write (POST) of one world,
// /api/v2/internal/world/<realm>/<map>. See msr_worldstate.h.
//

#ifndef HTTP_WORLD_STATE_REQUEST_H
#define HTTP_WORLD_STATE_REQUEST_H

#include "HTTPRequest.h"

// HTTP code (0: transport failure, -1: dropped before any reply) and the reply body.
// generation/serial let msr_worldstate.cpp ignore a reply meant for an older map or batch:
// queued replies can arrive while the next map loads.
typedef void (*WorldStateCallback)(unsigned int generation, unsigned int serial, int respCode, const std::string& body);

class WorldStateRequest : public HTTPRequest
{
public:
	// json == NULL: GET (load). Otherwise POST with json as the raw body; world writes
	// never use the character envelope. callback may be NULL for a blocking send: read
	// m_iRespCode and m_sResponseBody once FNShared::SendBlocking returns.
	WorldStateRequest(const char* url, const char* json, WorldStateCallback callback, unsigned int generation, unsigned int serial);
	~WorldStateRequest();
	void OnResponse(int iRespCode);
	const char* GetName() { return m_bWrite ? "WorldStateWriteRequest" : "WorldStateLoadRequest"; }

	int m_iRespCode;

private:
	WorldStateCallback m_pCallback;
	unsigned int m_iGeneration;
	unsigned int m_iSerial;
	bool m_bWrite;
	bool m_bAnswered;

	WorldStateRequest(const WorldStateRequest&);
	WorldStateRequest& operator=(const WorldStateRequest&);
};

#endif // HTTP_WORLD_STATE_REQUEST_H
