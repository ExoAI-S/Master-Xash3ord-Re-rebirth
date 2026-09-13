#include "sharedutil.h"
#include "stats/statdefs.h"
#include "stats/stats.h"
#include <tuple>
#include <vector>
#include <array>
#include <iostream>
#include <cstdarg>
#include <cmath>
#include <cstring>
#include <stdexcept>

constexpr int CHAR_LEVEL_CAP = 45;
struct hudtextparms_t { float x,y,fadeinTime,fadeoutTime,holdTime,fxTime; int effect,r1,g1,b1,r2,g2,b2; };
char* UTIL_VarArgs(const char* format, ...)
{
    static char text[2048]; va_list args; va_start(args,format);
    vsnprintf(text,sizeof(text),format,args); va_end(args); return text;
}
#define ALERT(...) ((void)0)
#define MS_ERROR(...) ((void)0)
#define ERROR_MISSING_PARMS ((void)0)
#define MESSAGE_BEGIN(...) ((void)0)
#define MESSAGE_END(...) ((void)0)
#define WRITE_BYTE(...) ((void)0)
#define WRITE_LONG(...) ((void)0)
#define V_max(a,b) ((a)>(b)?(a):(b))
#define V_min(a,b) ((a)<(b)?(a):(b))
#define RETURN_INT(value) msstring(UTIL_VarArgs("%i",value))
#define RETURN_FLOAT_PRECISION(value) msstring(UTIL_VarArgs("%.6f",static_cast<double>(value)))
void UTIL_HudMessage(void*, const hudtextparms_t&, const char*) {}
struct EngineStub { void pfnCVarSetString(const char*,const char*) {} } g_engfuncs;
class CMSMonster
{
public:
    statlist m_Stats;
    CMSMonster() { CStat::InitStatList(m_Stats); for(int n=0;n<STATS_TOTAL;++n) {
        auto& s=m_Stats[n]; for(unsigned p=0;p<s.m_SubStats.size();++p) {s.m_SubStats[p].Value=1; s.m_SubStats[p].Exp=0;}} }
    virtual bool IsPlayer() { return false; }
    CStat* FindStat(int n) { return n>=0 && n<STATS_TOTAL ? &m_Stats[n] : nullptr; }
    CStat* FindStat(const char* name) { return FindStat(GetSkillStatByName(name)); }
    int GetSkillStat(int n) { auto* s=FindStat(n); return s?s->Value():0; }
    int GetSkillStat(int n,int p);
    int GetSkillStat(const char* name,int p);
    std::tuple<bool,int> LearnSkill(int n,int p,int xp);
    void SetScriptVar(const char*,float) {}
    void TestSetStat(msstringlist& Params);
};
class LegacyMonster : public CMSMonster { public: std::tuple<bool,int> LearnSkill(int,int,int); };
class CBasePlayer : public CMSMonster
{
public:
    std::vector<std::array<std::string,3>> events;
    bool IsPlayer() override { return true; }
    std::tuple<bool,int> LearnSkill(int,int,int);
    bool LearnSkill(int,int);
    void SendInfoMsg(const char*,...) {}
    void CallScriptEvent(const char* event,msstringlist* params)
    {
        if(strcmp(event,"game_learnskill") || params->size()!=3) throw std::runtime_error("callback contract");
        events.push_back({(*params)[0].c_str(),(*params)[1].c_str(),(*params)[2].c_str()});
    }
};
class LegacyStatProxy
{
public:
    mslist<CSubStat>& m_SubStats;
    explicit LegacyStatProxy(CStat& stat):m_SubStats(stat.m_SubStats) {}
    int Value(); // Actual baseline CStat::Value body, renamed by extractor.
};
class LegacySkillPlayer : public CBasePlayer
{
public:
    using CBasePlayer::GetSkillStat;
    int GetSkillStat(int index) { return LegacyStatProxy(m_Stats[index]).Value(); }
};
#include "build/entrypoints.inc"
#include "build/script_consumers.inc"

static unsigned checks=0;
static void require(bool pass,const char* message) { ++checks; if(!pass)throw std::runtime_error(message); }
static void set(CMSMonster& p,const char* name,const char* value)
{ msstringlist params;params.add(name);params.add(value);p.TestSetStat(params); }
int main()
{
    try
    {
        for (int level = 0; level <= UnifiedWeapon::LevelCap; ++level)
            require(UnifiedWeapon::TrackCost(level) == static_cast<UnifiedWeapon::XP>(std::ceil(GetExpNeeded(level))),
                "Unified cost diverged from original formula");
        for(int prop=0;prop<3;++prop)
        {
            CBasePlayer p;
            require(!std::get<0>(p.LearnSkill(SKILL_SWORDSMANSHIP,prop,14)),"Early base level");
            require(std::get<0>(p.LearnSkill(SKILL_SWORDSMANSHIP,prop,1)),"Physical property did not train base");
            for(int alias=0;alias<3;++alias) require(p.GetSkillStat(SKILL_SWORDSMANSHIP,alias)==2,"Combat alias differs");
            require(p.events.size()==1 && p.events[0][0]=="Swordsmanship" && p.events[0][1]=="Base" && p.events[0][2]=="2","Base callback incorrect");
        }
        CBasePlayer p;
        require(p.LearnSkill(SKILL_ARCHERY,static_cast<int>(3*UnifiedWeapon::EarnedBefore(5))),"Bare award");
        require(p.GetSkillStat(SKILL_ARCHERY)==5 && p.events.size()==4,"Large award skipped base events");
        for(int n=0;n<4;++n) require(p.events[n][2]==std::to_string(n+2),"Callback level ordering");
        for(const char* suffix:{"prof","proficiency","balance","power"})
        {
            const std::string property=std::string("archery.")+suffix;
            set(p,property.c_str(),"20");
            require(p.GetSkillStat("archery",0)==20 && p.GetSkillStat("archery",2)==20,"MScript setter bypass");
            require(TestSkillGet(&p,("skill."+property).c_str())=="20","MScript getter alias");
            require(TestSkillGet(&p,("skill."+property+".ratio").c_str())=="0.200000","Ability ratio scale changed");
            require(TestSkillGet(&p,("skill."+property+".max").c_str())=="100","Ability max scale changed");
        }
        require(TestSkillGet(&p,"skill.archery")=="20" && TestSkillGet(&p,"skill.archery.ratio")=="0.066667","Bare ratio compatibility scale differs");
        require(TestSkillGet(&p,"skill.archery.max")=="300","Bare max compatibility scale differs");
        // Equal legacy tracks remove migration differences: compare the actual
        // old rounded-average value/getter with the current getter, then replay
        // the unchanged script arithmetic using their formatted ratio strings.
        for(int level=1;level<=45;++level)
        {
            CBasePlayer now;LegacySkillPlayer old;
            for(int skill:{SKILL_BLUNTARMS,SKILL_MARTIALARTS})
            {
                require(now.m_Stats[skill].SetWeaponLevel(level),"Consumer base setup");
                for(int prop=0;prop<3;++prop) old.m_Stats[skill].m_SubStats[prop].Value=level;
                require(now.GetSkillStat(skill)==old.GetSkillStat(skill),"Equal-track base differs");
            }
            const double torch=TorchDamage(&now,TestSkillGet);
            const double claws=DemonClawsDamage(&now,TestSkillGet);
            require(torch==TorchDamage(&old,LegacySkillGet),"Torch burn damage changed at equal tracks");
            require(claws==DemonClawsDamage(&old,LegacySkillGet),"Demon Claws damage changed at equal tracks");
            if(level==30)
            {
                require(std::abs(torch-3.0)<1e-9,"Torch level-30 golden damage");
                require(std::abs(claws-36.0)<1e-9,"Demon Claws level-30 golden damage");
                std::cout<<"Script-consumer level 30: torch "<<torch<<", Demon Claws "<<claws<<"; baseline equal tracks match.\n";
            }
        }
        set(p,"archery","8");require(p.GetSkillStat(SKILL_ARCHERY)==8,"Bare setter");
        set(p,"archery.power","46");require(p.GetSkillStat(SKILL_ARCHERY)==8,"Invalid setter changed base");
        set(p,"archery.balance","-1");require(p.GetSkillStat(SKILL_ARCHERY)==8,"Negative setter changed base");
        msstringlist tuple; tuple.add("archery");tuple.add("10");tuple.add("25");tuple.add("20");
        p.TestSetStat(tuple);require(p.GetSkillStat(SKILL_ARCHERY)==8,"Conflicting player tuple silently accepted");
        CMSMonster npc;set(npc,"archery.power","30");require(npc.GetSkillStat(SKILL_ARCHERY)==1,"NPC setter changed old behavior");
        set(p,"spellcasting.fire","12");set(p,"spellcasting.ice","17");
        require(TestSkillGet(&p,"skill.spellcasting.fire")=="12" && TestSkillGet(&p,"skill.spellcasting.ice")=="17","Magic getter/setter merged schools");
        require(TestSkillGet(&p,"skill.spellcasting.max")=="300","Magic max changed");
        // Differential replay of actual old/current monster LearnSkill code:
        // all school indices and Parry, threshold boundaries and large remainders.
        for(int skill:{SKILL_SPELLCASTING,SKILL_PARRY})
            for(int prop=0;prop<(skill==SKILL_SPELLCASTING?5:1);++prop)
                for(int level:{1,2,10,25,26,44,45})
                    for(int input:{0,1,4,20,1000000})
                    {
                        CMSMonster now;LegacyMonster old;
                        now.m_Stats[skill].m_SubStats[prop].Value=level;
                        old.m_Stats[skill].m_SubStats[prop].Value=level;
                        now.m_Stats[skill].m_SubStats[prop].Exp=static_cast<ulong>(std::ceil(GetExpNeeded(level)))-1;
                        old.m_Stats[skill].m_SubStats[prop].Exp=now.m_Stats[skill].m_SubStats[prop].Exp;
                        require(now.LearnSkill(skill,prop,input)==old.LearnSkill(skill,prop,input),"Nonweapon award return changed");
                        for(unsigned n=0;n<now.m_Stats[skill].m_SubStats.size();++n)
                            require(now.m_Stats[skill].m_SubStats[n].Value==old.m_Stats[skill].m_SubStats[n].Value &&
                                now.m_Stats[skill].m_SubStats[n].Exp==old.m_Stats[skill].m_SubStats[n].Exp,"Nonweapon award state changed");
                    }
        std::cout<<"PASS "<<checks<<" entrypoint assertions; actual LearnSkill/get/set/callback bodies; 210 baseline magic/Parry differential cases; 90 script-consumer formula comparisons. Engine I/O is inert; no script VM run.\n";
    }
    catch(const std::exception& error) { std::cerr<<"FAIL "<<checks<<": "<<error.what()<<'\n';return 1; }
}
