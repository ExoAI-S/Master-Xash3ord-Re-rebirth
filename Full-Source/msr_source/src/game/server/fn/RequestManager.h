#ifndef MS_REQUEST_MANAGER
#define MS_REQUEST_MANAGER

#include "HTTPRequest.h"
#include <vector>
#include <curl/curl.h>

class CRequestManager
{
public:
	CRequestManager() = default;
	~CRequestManager() = default;
	void Init();

	void Think(bool bForceDiscard = false);
	void Shutdown(void);

	// Longer than REQUEST_TIMEOUT_MS: a transfer on the wire when a drain starts has finished
	// (or timed out) before the drain gives up, so nothing sent later can overtake it.
	static constexpr int kDrainTimeoutMs = 10000;

	// Blocks (pumping Think) until every queued request got its reply or the time ran out;
	// the manager stays usable. Returns true when the queue is empty.
	bool Drain(int timeoutMs = kDrainTimeoutMs);

	void Clear(void);

	bool QueueRequest(HTTPRequest* req);

	CURLSH* GetShareHandle() const { return m_pShareHandle; }

private:
	void ProcessMultiCompleted();

	bool m_bLoaded = false;

	CURLM* m_pMultiHandle = nullptr;
	CURLSH* m_pShareHandle = nullptr;

	int m_iRunningTransfers = 0; // this is for curl_multi_perform to keep track of handles.
	std::vector<HTTPRequest*> m_vRequests;

private:
	CRequestManager(const CRequestManager&); // No copy pls.
	CRequestManager& operator=(const CRequestManager&);
};

extern CRequestManager g_FNRequestManager;

#endif // MS_REQUEST_MANAGER