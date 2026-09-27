//
// Persistent world state on FN: load (GET) and batch write (POST) of one world
//

#include <cstring>
#include "WorldStateReq.h"

WorldStateRequest::WorldStateRequest(const char* url, const char* json, WorldStateCallback callback, unsigned int generation, unsigned int serial) :
	HTTPRequest(json ? HTTPMethod::POST : HTTPMethod::GET, url, json, json ? strlen(json) : 0),
	m_iRespCode(0),
	m_pCallback(callback),
	m_iGeneration(generation),
	m_iSerial(serial),
	m_bWrite(json != NULL),
	m_bAnswered(false)
{
	m_bRawBody = true;
}

WorldStateRequest::~WorldStateRequest()
{
	// Dropped unanswered (queue refused it, or aborted at shutdown): the owner must still
	// hear about it, or it would wait for this batch forever.
	if (!m_bAnswered && m_pCallback)
		m_pCallback(m_iGeneration, m_iSerial, -1, std::string());
}

void WorldStateRequest::OnResponse(int iRespCode)
{
	m_bAnswered = true;
	m_iRespCode = iRespCode;

	// Only codes and bytes cross over: the callback checks the generation before it
	// touches any state, and no entity is involved.
	if (m_pCallback)
		m_pCallback(m_iGeneration, m_iSerial, iRespCode, m_sResponseBody);
}
