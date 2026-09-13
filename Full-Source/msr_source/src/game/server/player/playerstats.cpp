#include "msdllheaders.h"
#include "msitemdefs.h"
#include "stats/stats.h"
#include "stats/statdefs.h"
#include "syntax/syntax.h"
#include "player.h"
#include "weapons/weapons.h"
#include "weapons/genericitem.h"
#include "modeldefs.h"

Vector CBasePlayer::Size(int flags)
{
	return Vector(m_Width, m_Width, (!(flags & FL_DUCKING)) ? m_Height : m_Height / 2);
}
void CBasePlayer::SetSize(int flags)
{
	UTIL_SetSize(pev, -(Size(flags) / 2), Size(flags) / 2);
}
void CBasePlayer::SendMenu(int iMenu, TCallbackMenu* cbmMenu)
{
	switch (iMenu)
	{
	case MENU_USERDEFINED:
		if (!cbmMenu)
			return;
		//CurrentCallbackMenu must be dynamic memory
		if (CurrentCallbackMenu && CurrentCallbackMenu != cbmMenu)
		{
			TCallbackMenu* pOldMenu = CurrentCallbackMenu;
			CBaseEntity* pOwner = GetClassPtr((CBaseEntity*)pOldMenu->pevOwner);
			//Let the callback function delete its own memory, then I delete the menu
			if (pOwner && pOldMenu->m_MenuCallback)
				(pOwner->*(pOldMenu->m_MenuCallback))(this, -1, pOldMenu);
			delete pOldMenu;
		}
		CurrentCallbackMenu = cbmMenu;
		ShowMenu(cbmMenu->cMenuText, cbmMenu->iValidslots);
		break;
	}
	CurrentMenu = iMenu;
}
void CBasePlayer::ParseMenu(int iMenu, int slot)
{
	int validselections = 0; //, i;
	switch (iMenu)
	{
	case MENU_USERDEFINED:
		if (!CurrentCallbackMenu || !CurrentCallbackMenu->m_MenuCallback || !CurrentCallbackMenu->pevOwner)
			break;
		CBaseEntity* pOwner = GetClassPtr((CBaseEntity*)CurrentCallbackMenu->pevOwner);
		if (!pOwner)
			break;

		TCallbackMenu* pOldMenu = CurrentCallbackMenu;
		(pOwner->*(pOldMenu->m_MenuCallback))(this, slot, pOldMenu);
		//CurrentCallbackMenu must be dynamic memory
		if (CurrentCallbackMenu == pOldMenu)
			CurrentCallbackMenu = NULL;

		delete pOldMenu;
		break;
	}
}

std::tuple<bool, int> CBasePlayer::LearnSkill(int iStat, int iStatType, int EnemySkillLevel)
{
    CStat* weapon = FindStat(iStat);
    if (!weapon || iStat < SKILL_FIRSTSKILL || iStat >= STATS_TOTAL)
        return std::make_tuple(false, 0);
    if (weapon->IsUnifiedWeapon())
    {
        static_assert(CHAR_LEVEL_CAP == UnifiedWeapon::LevelCap, "Weapon progression cap must match the game cap");
        if (iStatType < 0 || iStatType >= UnifiedWeapon::Tracks || EnemySkillLevel <= 0)
            return std::make_tuple(false, 0);
        const int before = weapon->Value();
        int accepted = 0, levels = 0;
        if (!weapon->AwardWeaponXP(EnemySkillLevel, accepted, levels))
            return std::make_tuple(false, 0);
        const char* name = SkillStatList[iStat - SKILL_FIRSTSKILL].Name;
        if (accepted > 0) ALERT(at_console, "Gained XP: %i in skill %s\n", accepted, name);
        if (levels > 0)
        {
            SendInfoMsg("You become more adept at %s. Level %i.\n", name, weapon->Value());
            hudtextparms_t htp{};
            htp.x = 0.02f; htp.y = 0.6f; htp.effect = 2;
            htp.g1 = 128; htp.r2 = 178; htp.g2 = 119;
            htp.fadeinTime = 0.02f; htp.fadeoutTime = 3.0f; htp.holdTime = 2.0f; htp.fxTime = 0.6f;
            UTIL_HudMessage(this, htp, UTIL_VarArgs("%s +%i\n", name, levels));
            // Event arity is unchanged; weapon advancement is now Base. Emit
            // each crossed level once so large awards cannot skip callbacks.
            for (int level = before + 1; level <= before + levels; ++level)
            {
                msstringlist params;
                params.add(name); params.add("Base");
                params.add(UTIL_VarArgs("%i", level));
                CallScriptEvent("game_learnskill", &params);
            }
        }
        return std::make_tuple(levels > 0, 0);
    }
	//see if a skill leveled.
	bool bSkillLeveled = false;

	// track remaining exp
	int iRemainingExp = EnemySkillLevel;

	while (iRemainingExp > 0) {
		CStat* csExpStat = CMSMonster::FindStat(iStat);
		int iFirstSubValue = csExpStat->m_SubStats[0].Value;

		// find the best substat to give things to;
		int iBestSubstatId = 10;
		int iEqualCount = 0;

		//keep highest exp remaining for second check, moved here to be debuggable
		long double	ldHighestExpRemaining = 0;

		//see if anything has lower substats than the first skill in the list
		if (csExpStat->m_SubStats.size() < 4)
		{
			for (unsigned int idx = 0; idx < csExpStat->m_SubStats.size(); idx++) {
				if (csExpStat->m_SubStats[idx].Value < iFirstSubValue) {
					iBestSubstatId = idx;
				} 
				//ensure we get a substat in case we dont have 3 equal substats
				else if (csExpStat->m_SubStats[idx].Value == iFirstSubValue && iBestSubstatId == 10) {
					iBestSubstatId = idx;
				}
				if (csExpStat->m_SubStats[idx].Value == iFirstSubValue) {
					iEqualCount++;
				}
			}

			//if we didn't find a low substat, go through the remaining exp instead
			if (iEqualCount == 3) {

				for (unsigned int idx = 0; idx < csExpStat->m_SubStats.size(); idx++) {
					long double ldCurrentExpRemaining = abs(GetExpNeeded(csExpStat->m_SubStats[idx].Value) - csExpStat->m_SubStats[idx].Exp);

					if (ldCurrentExpRemaining >= ldHighestExpRemaining) {
						ldHighestExpRemaining = ldCurrentExpRemaining;
						iBestSubstatId = idx;
					}

				}
			}
		}
		else {
			//if this is spellcasting just use the given id
			iBestSubstatId = iStatType;
		}

		//set debug cvar to avoid spamming console but be able to get debug info
		char sDebugInfo[64];
		_snprintf(sDebugInfo, 64, "Stat: %i , Equalcount : %i , Highest EXP needed: %lf", iBestSubstatId, iEqualCount, ldHighestExpRemaining);
		g_engfuncs.pfnCVarSetString("DEBUG_bestxpstat", sDebugInfo);

		//run learnskill
		std::tuple<bool, int> tbiSuccess = CMSMonster::LearnSkill(iStat, iBestSubstatId, iRemainingExp);
		int iStatIdx = iStat - SKILL_FIRSTSKILL;

		//Thoth DEC2008a level cap
		if (GetSkillStat(iStatIdx, iBestSubstatId) >= CHAR_LEVEL_CAP)
			return std::make_tuple(false, 0);

		msstring stat_name = SkillStatList[iStatIdx].Name;
		bool is_spell_stat = stat_name.contains("Spell");
		if (is_spell_stat)
			ALERT(at_console, "Gained XP: %i in skill %s %s \n", EnemySkillLevel, SkillStatList[iStatIdx].Name, SpellTypeList[iBestSubstatId]); //Thothie returns XP gained by monsters
		else
			ALERT(at_console, "Gained XP: %i in skill %s %s \n", EnemySkillLevel, SkillStatList[iStatIdx].Name, SkillTypeList[iBestSubstatId]); //Thothie returns XP gained by monsters

		if (std::get<0>(tbiSuccess))
		{
			hudtextparms_t htp;
			memset(&htp, 0, sizeof(hudtextparms_t));
			htp.x = 0.02;
			htp.y = 0.6;
			htp.effect = 2;
			htp.r1 = 0;
			htp.g1 = 128;
			htp.b1 = 0;
			htp.r2 = 178;
			htp.g2 = 119;
			htp.b2 = 0;
			htp.fadeinTime = 0.02;
			htp.fadeoutTime = 3.0;
			htp.holdTime = 2.0;
			htp.fxTime = 0.6;
			UTIL_HudMessage(this, htp, UTIL_VarArgs("%s %s +1\n", SkillStatList[iStatIdx].Name, SkillTypeList[iBestSubstatId]));

			if (!is_spell_stat)
			{
				SendInfoMsg("You become more adept at %s.\n", SkillStatList[iStatIdx].Name);
				UTIL_HudMessage(this, htp, UTIL_VarArgs("%s %s +1\n", SkillStatList[iStatIdx].Name, SkillTypeList[iBestSubstatId]));
			}
			else
			{
				SendInfoMsg("You become more adept at %s.\n", SkillStatList[iStatIdx]);
				UTIL_HudMessage(this, htp, UTIL_VarArgs("%s %s +1\n", SkillStatList[iStatIdx].Name, SpellTypeList[iBestSubstatId]));
			}

			msstringlist Params;
			Params.add(SkillStatList[iStatIdx].Name);
			if (!is_spell_stat)
				Params.add(SkillTypeList[iBestSubstatId]);
			else
				Params.add(SpellTypeList[iBestSubstatId]);
			
			Params.add(UTIL_VarArgs("%i", GetSkillStat(iStatIdx, iBestSubstatId)));
			CallScriptEvent("game_learnskill", &Params);
		}

		bSkillLeveled = true;
		iRemainingExp = std::get<1>(tbiSuccess);
	}

	return std::make_tuple(bSkillLeveled, 0);
}

bool CBasePlayer::LearnSkill(int iStat, int EnemySkillLevel)
{
	//Exp is added to a random property of the skill
	CStat* pStat = FindStat(iStat);
	if (!pStat)
		return false;

	int iSubStat = 1;
	//SendInfoMsg( "You gain %d XP", EnemySkillLevel ); //thothie - XP report - no workie

	return std::get<0>(LearnSkill(iStat, iSubStat, EnemySkillLevel));
}
