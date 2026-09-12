#ifndef MS_STEAM_CLIENT_HELPER_H
#define MS_STEAM_CLIENT_HELPER_H

#ifndef MSR_STANDALONE
#include <steam/steam_api.h>
#endif

class CSteamClientHelper
{
public:
	CSteamClientHelper();
	~CSteamClientHelper();

	void Think();
	void SetAchievement(const char* str);
	void SetStat(const char* str, int value);

private:
#ifndef MSR_STANDALONE
	bool m_bHasLoadedSteamStats;
	STEAM_CALLBACK(CSteamClientHelper, OnUserStatsReceived, UserStatsReceived_t, m_CallbackUserStatsReceived);
	STEAM_CALLBACK(CSteamClientHelper, OnUserStatsStored, UserStatsStored_t, m_CallbackUserStatsStored);
	STEAM_CALLBACK(CSteamClientHelper, OnAchievementStored, UserAchievementStored_t, m_CallbackAchievementStored);
#endif
};

#ifndef MSR_STANDALONE
extern CSteamAPIContext* steamapicontext;
#endif
extern CSteamClientHelper* steamhelper;

#endif // MS_STEAM_HELPER_H
