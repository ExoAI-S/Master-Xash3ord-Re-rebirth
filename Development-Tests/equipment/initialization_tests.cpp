#include "sharedutil.h"
#include <vector>
#include <string>
#include <iostream>
#include <stdexcept>

struct wearpos_t {msstring Name;union{int MaxAmt;int Slots;};wearpos_t(){}wearpos_t(msstring n,int v):Name(n),MaxAmt(v){}};
struct SCRIPT_EVENT{};struct scriptcmd_t{};
const int MAX_CHARSLOTS=3,PLAYER_SCRIPT_ID=1;
const char* PLAYER_SCRIPT="player/player";
#define MS_ERROR(...) ((void)0)
#define ERROR_MISSING_PARMS ((void)0)
#define SetBits(v,b) ((v)|=(b))
#define ClearBits(v,b) ((v)&=~(b))
#define FBitSet(v,b) ((v)&(b))

class CBasePlayer
{
public:
    bool m_Initialized=false;void* m_ChosenArrow=nullptr;float m_AnimSpeedAdj=0;
    struct Info{int Index=0;} m_CharInfo[MAX_CHARSLOTS];
    mslist<wearpos_t> m_WearPositions;
    int statsCreated=0,entityEventCalls=0;
    bool IsPlayer(){return true;}
    void CreateStats(){++statsCreated;}
    void CallScriptEvent(const char*){++entityEventCalls;} // Its own script list is empty on the client.
    void InitialSpawn();void LegacyInitialSpawn();
} player;
class CScript
{
public:
    struct{CBasePlayer* pScriptedEnt=nullptr;} m;
    int resets=0;
    bool ScriptCmd_SetWearPos(SCRIPT_EVENT&,scriptcmd_t&,msstringlist&);
    void RunScriptEventByName(const char*);
};
struct HudScript
{
    CScript script;bool missing=false;int creates=0;
    CScript* CreateScript(const char*,msstringlist&,bool,int)
    {++creates;script.m.pScriptedEnt=&player;return missing?nullptr:&script;}
} hudScript;
struct{HudScript* m_HUDScript=&hudScript;} gHUD;

constexpr int ITEM_WEARABLE=1,ITEM_GROUPABLE=2,ITEM_DRINKABLE=4,ITEM_PERISHABLE=8,ITEM_SPELL=16;
class CGenericItem
{
public:
    mslist<wearpos_t> m_WearPositions;
    ulong m_iId=0;int m_Location=0,m_Hand=0,Properties=0,iQuantity=0,Quality=0,MaxQuality=0;
    float Spell_TimePrepare=0;bool Spell_CastSuccess=false;
    int MSProperties(){return Properties;}
    void TestWearable(msstringlist&);
} networkItem;
bool itemExists=false;
CGenericItem* MSUtil_GetItemByID(ulong id){return itemExists&&networkItem.m_iId==id?&networkItem:nullptr;}
struct CGenericItemMgr{static CGenericItem* NewGenericItem(int);};
std::vector<int> wire;size_t cursor=0;
#define READ_LONG() wire.at(cursor++)
#define READ_SHORT() wire.at(cursor++)
#define READ_BYTE() wire.at(cursor++)
#define READ_COORD() wire.at(cursor++)
#include "build/initialization_paths.inc"
#include "build/authored_wear.inc"

void CScript::RunScriptEventByName(const char* event)
{
    if(std::string(event)!="game_reset_wear_positions")throw std::runtime_error("Unexpected event");
    ++resets;SCRIPT_EVENT e;scriptcmd_t cmd;
    for(const auto& input:wearCommands){msstringlist args;for(const auto& x:input)args.add(x.c_str());ScriptCmd_SetWearPos(e,cmd,args);}
}
CGenericItem* CGenericItemMgr::NewGenericItem(int)
{
    // Adapter for the established factory/Spawn script boundary: replay the
    // unchanged wearable commands from the actual Leather Vest script.
    networkItem.m_WearPositions.clearitems();networkItem.Properties=0;itemExists=true;
    for(const auto& input:vestCommands){msstringlist args;for(const auto& x:input)args.add(x.c_str());networkItem.TestWearable(args);}
    return &networkItem;
}
unsigned checks=0;
void require(bool value,const char* why){++checks;if(!value)throw std::runtime_error(why);}
void resetPlayer(){player.m_Initialized=false;player.m_WearPositions.clearitems();player.entityEventCalls=0;hudScript.script.resets=0;hudScript.creates=0;hudScript.missing=false;}
void checkAuthored()
{
    require(player.m_WearPositions.size()==wearCommands.size()-1,"Authored position count mismatch");
    for(unsigned n=1;n<wearCommands.size();++n)
    {
        require(player.m_WearPositions[n-1].Name==wearCommands[n][0].c_str(),"Invented or duplicated position");
        require(player.m_WearPositions[n-1].MaxAmt==std::stoi(wearCommands[n][1]),"Authored capacity changed");
    }
}
int main()
{
    try
    {
        resetPlayer();player.LegacyInitialSpawn();
        require(player.m_WearPositions.size()==0&&player.entityEventCalls==1&&hudScript.script.resets==0,"Baseline no longer reproduces missing client event");
        resetPlayer();player.InitialSpawn();checkAuthored();
        require(hudScript.script.resets==1&&player.entityEventCalls==0,"Reset not dispatched to created HUD script");
        player.InitialSpawn();checkAuthored();require(hudScript.script.resets==1,"Repeated initialization duplicated reset");
        for(int n=0;n<3;++n){hudScript.script.RunScriptEventByName("game_reset_wear_positions");checkAuthored();}
        // Replay initialization after cleared state, matching map/reconnect cleanup.
        resetPlayer();player.InitialSpawn();checkAuthored();
        resetPlayer();hudScript.missing=true;player.InitialSpawn();require(player.m_WearPositions.size()==0,"Missing script invented fallback slots");
        resetPlayer();player.InitialSpawn();
        SCRIPT_EVENT event;scriptcmd_t command;msstringlist args;args.add("chest");args.add("0");
        hudScript.script.ScriptCmd_SetWearPos(event,command,args);require(player.m_WearPositions.size()==21&&player.m_WearPositions[2].MaxAmt==0,"Existing capacity update duplicated position");
        hudScript.script.RunScriptEventByName("game_reset_wear_positions");checkAuthored();
        wire={123,0,0,1,ITEM_WEARABLE};cursor=0;auto* vest=ReadGenericItem(true);
        require(vest&&cursor==wire.size()&&vest->m_WearPositions.size()==2,"New item lost authored requirements");
        require(vest->m_WearPositions[0].Name=="chest"&&vest->m_WearPositions[1].Name=="arms","Vest requirements mismatch");
        require(vest->m_WearPositions[0].Slots==1&&vest->m_WearPositions[1].Slots==1,"Vest required units mismatch");
        wire={123,0,2,1,ITEM_WEARABLE};cursor=0;require(ReadGenericItem(false)==vest&&cursor==wire.size()&&vest->m_WearPositions.size()==2,"Item update lost wear metadata");
        msstringlist duplicate;duplicate.add("1");duplicate.add("chest;arms");vest->TestWearable(duplicate);require(vest->m_WearPositions.size()==2,"Repeated wearable definition duplicated metadata");
        msstringlist clear;clear.add("0");vest->TestWearable(clear);require(vest->m_WearPositions.size()==0&&!(vest->Properties&ITEM_WEARABLE),"Wearable clear did not clear metadata");
        std::cout<<"PASS "<<checks<<" initialization/metadata assertions; baseline zero-slot failure reproduced, corrected client event yields21 authored positions; reset/reconnect and real item reader checked. Inert script-boundary adapter, no engine/VM run.\n";
    }
    catch(const std::exception& e){std::cerr<<"FAIL "<<checks<<": "<<e.what()<<'\n';return 1;}
}
