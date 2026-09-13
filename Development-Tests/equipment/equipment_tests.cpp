#include "sharedutil.h"
#include "equipment_drag_state.h"
#include <vector>
#include <iostream>
#include <stdexcept>
#include <limits>
#include <climits>
#include <cstring>

static unsigned assertions=0;
void require(bool pass,const char* message){++assertions;if(!pass)throw std::runtime_error(message);}
template<class T> struct CheckedList:std::vector<T> { using std::vector<T>::vector;T& operator[](size_t n){return this->at(n);} };
struct wearpos_t { msstring Name;union{int MaxAmt;int Slots;};wearpos_t(const char* name,int value):Name(name),MaxAmt(value){} };
class CGenericItem;
struct CMSMonster { CheckedList<CGenericItem*> Gear; };
class CBasePlayer:public CMSMonster
{
public:
    CheckedList<wearpos_t> m_WearPositions;
    CGenericItem* hands[3]={};int m_CurrentHand=0,m_StatusFlags=0;std::vector<int> uses;
    CGenericItem* Hand(int h){return h>=0&&h<3?hands[h]:nullptr;}
    void SendInfoMsg(const char*,...){}
    void UseItem(int h,bool){uses.push_back(h);}
};
class CGenericItem
{
public:
    CMSMonster* m_pOwner=nullptr;CBasePlayer* m_pPlayer=nullptr;
    CheckedList<wearpos_t> m_WearPositions;bool worn=false,wearable=true;
    void* m_pParentContainer=nullptr;void* CurrentAttack=nullptr;unsigned long m_iId=1;
    int MSProperties(){return wearable?1:0;}bool IsWorn(){return worn;}bool CanWearItem();
};
constexpr int ITEM_WEARABLE=1,MAX_NPC_HANDS=3,PLAYER_MOVE_NOMOVE=1;
#define FBitSet(value,flag) ((value)&(flag))
#define CMD_ARGC() static_cast<int>(args.size())
#define CMD_ARGV(n) (static_cast<size_t>(n)<args.size()?args[n].c_str():"")
namespace SPEECH{const char* ItemName(CGenericItem*){return "fixture";}}
std::vector<std::string> commands;
void ServerCmd(const char* command){commands.push_back(command);}
struct EngineStub
{
    float now=1;float GetClientTime(){return now;}float pfnGetCvarFloat(const char*){return .3f;}
    void Con_Printf(const char*,...){}
} gEngfuncs;
class CContainerPanel{public:unsigned m_EquipmentCommandBatches=0;bool available=true;bool EquipmentDragAvailable()const{return available;}void SendEquipmentDrop(unsigned long,bool);};
#include "build/game_paths.inc"

enum MouseCode{MOUSE_LEFT,MOUSE_RIGHT,MOUSE_LAST};enum KeyCode{KEY_ESCAPE};struct Panel{};
struct InputSignal{};
struct Callback{bool consume=false;int starts=0;bool BeginItemDrag(void*,bool){++starts;return consume;}};
struct VGUI_ItemButton
{
    Callback* m_CallbackPanel=nullptr;bool m_Selected=false;int clicks=0,doubles=0,splits=0;
    void Clicked(){++clicks;m_Selected=!m_Selected;}void Doubleclicked(){++doubles;}
    void RightClicked(){++splits;}void Highlight(bool){}
};
#include "build/input_paths.inc"

int main()
{
    try
    {
        using namespace MSREquipment;
        require(Eligible(true,false,true,false,1,false,0),"Nonstack armor with quantity zero rejected");
        require(!Eligible(true,false,true,false,1,true,0),"Empty stack accepted");
        require(!Eligible(true,false,false,true,1,false,0),"Already worn accepted");
        require(!Eligible(true,true,true,false,1,false,0),"Attacking item accepted");
        std::vector<Position> positions={{"head",1,0},{"chest",1,0},{"arms",2,1},{"back",3,2},{"leftfinger",10,9}};
        require(Compatible(positions,{{"head",1}},"head"),"Empty compatible slot");
        require(!Compatible(positions,{{"head",1}},"chest"),"Wrong slot accepted");
        require(Compatible(positions,{{"chest",1},{"arms",1}},"chest"),"Multi-position fit");
        require(!Compatible(positions,{{"chest",1},{"arms",2}},"chest"),"Other required position over capacity");
        require(!Compatible(positions,{{"unknown",1}},"unknown"),"Invented position");
        require(!Compatible(positions,{{"head",-1}},"head"),"Negative slot units");
        require(Compatible(positions,{{"leftfinger",1}},"leftfinger"),"Authored many-slot position");
        for(int used=0;used<=4;++used)for(int cost=1;cost<=4;++cost)
            require(Compatible({{"back",3,used}},{{"back",cost}},"back")==bool(used+cost<=3),"Capacity boundary");
        Gesture g;g.Arm(11,9,0,100,100,1280,720,1,false);
        require(!g.Move(103,104)&&!g.dragging,"Click threshold changed");
        require(g.Move(106,100)&&g.dragging,"Drag threshold missing");
        require(g.Valid(11,9,0,1280,720,2),"Valid gesture stale");
        require(!g.Valid(12,9,0,1280,720,2),"Deleted/replaced ID not canceled");
        require(!g.Valid(11,8,0,1280,720,2),"Moved item not canceled");
        require(!g.Valid(11,9,1,1280,720,2),"Changed stack not canceled");
        require(!g.Valid(11,9,0,1920,1080,2),"Resolution change not canceled");
        require(!g.Valid(11,9,0,1280,720,11),"Gesture timeout");
        require(g.Take().id==11 && g.Take().id==0,"Repeated release can dispatch twice");
        g.Arm(11,0,1,0,0,1280,720,1,false);require(g.Move(INT_MAX,INT_MIN),"Extreme coordinate overflow");
        g.Clear();require(!g.id&&!g.dragging,"Cancel retained state");

        CBasePlayer player;player.m_WearPositions={{"chest",1},{"arms",2}};
        CGenericItem existing,candidate;existing.m_pOwner=&player;existing.m_pPlayer=&player;existing.worn=true;
        existing.m_WearPositions={{"arms",1}};
        candidate.m_pOwner=&player;candidate.m_pPlayer=&player;candidate.m_WearPositions={{"chest",1},{"arms",1}};
        player.Gear={&existing,&candidate};player.hands[1]=&candidate;candidate.m_iId=17;
        require(candidate.CanWearItem(),"Multi-position worn-index regression (old code indexes past one-slot item)");
        candidate.m_WearPositions[1].Slots=2;require(!candidate.CanWearItem(),"Authoritative capacity overfill");
        candidate.m_WearPositions[1].Slots=1;
        TestUse(&player,{"use","-1","17"});require(player.uses.size()==1&&player.uses[0]==1,"Guard did not resolve actual item hand");
        player.uses.clear();TestUse(&player,{"use","-1","999"});require(player.uses.empty(),"Stale ID used unrelated item");
        candidate.m_pParentContainer=&existing;TestUse(&player,{"use","-1","17"});require(player.uses.empty(),"Failed transfer equipped item");candidate.m_pParentContainer=nullptr;
        candidate.CurrentAttack=&existing;TestUse(&player,{"use","-1","17"});require(player.uses.empty(),"Attack guard");candidate.CurrentAttack=nullptr;
        candidate.worn=true;TestUse(&player,{"use","-1","17"});require(player.uses.empty(),"Repeated equip guard");candidate.worn=false;
        existing.m_WearPositions[0].Slots=2;TestUse(&player,{"use","-1","17"});require(player.uses.empty(),"Race to occupied slot");existing.m_WearPositions[0].Slots=1;
        TestUse(&player,{"use","-1","17"},false);require(player.uses.empty(),"Inventory permission bypass");
        TestUse(&player,{"use","0"});require(player.uses.size()==1&&player.uses[0]==0,"Original use command changed");
        CContainerPanel ui;ui.SendEquipmentDrop(17,true);
        require(commands==std::vector<std::string>{"inv transfer 17 0\n","use -1 17\n"},"Bag drop command order/count");
        commands.clear();ui.SendEquipmentDrop(17,false);require(commands==std::vector<std::string>{"use -1 17\n"},"Hand drop duplicated transfer");
        commands.clear();ui.available=false;ui.SendEquipmentDrop(17,true);require(commands.empty(),"Old server received guarded equip command");
        Callback fallback;VGUI_ItemButton button;button.m_CallbackPanel=&fallback;VGUI_DoubleClickDetector detector;
        CHandler_ItemButton handler(&button,&detector);
        handler.mousePressed(MOUSE_LEFT,nullptr);require(button.clicks==1,"Shop/storage default click changed");
        gEngfuncs.now+=.1f;handler.mousePressed(MOUSE_LEFT,nullptr);require(button.doubles==1,"Default double click changed");
        handler.mousePressed(MOUSE_RIGHT,nullptr);require(button.splits==1,"Right-click split changed");
        fallback.consume=true;handler.mousePressed(MOUSE_LEFT,nullptr);handler.mouseDoublePressed(MOUSE_LEFT,nullptr);
        require(button.clicks==1&&button.doubles==1,"Captured wearable executed click before release");
        std::cout<<"PASS "<<assertions<<" equipment assertions; real guarded-use, wear-capacity, command dispatch and item input bodies. No engine/UI run.\n";
    }
    catch(const std::exception& e){std::cerr<<"FAIL "<<assertions<<": "<<e.what()<<'\n';return 1;}
}
