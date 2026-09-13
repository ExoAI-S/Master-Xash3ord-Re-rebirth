// Equipment targets use authored wear positions. Item movement stays server-owned.
#include "inc_weapondefs.h"
#undef DLLEXPORT
#include "hud.h"
#include "cl_util.h"
#include "vgui_teamfortressviewport.h"
#include "vgui_containerlist.h"
#include <VGUI_App.h>
#include <cstdio>

namespace
{
std::vector<MSREquipment::Position> Positions()
{
    std::vector<MSREquipment::Position> positions;
    for (unsigned n=0; n<player.m_WearPositions.size(); ++n)
    {
        auto& authored=player.m_WearPositions[n]; // Legacy msstring::c_str is non-const.
        bool duplicate=false;
        for (const auto& p:positions) if (p.name==authored.Name.c_str()) duplicate=true;
        if (!duplicate) positions.push_back({authored.Name.c_str(),authored.MaxAmt,0});
    }
    for (unsigned n=0; n<player.Gear.size(); ++n)
    {
        auto* item=player.Gear[n];
        if (!item || item->m_pParentContainer || !item->IsWorn() || !(item->MSProperties()&ITEM_WEARABLE)) continue;
        for (unsigned w=0; w<item->m_WearPositions.size(); ++w)
            for (auto& p:positions)
                if (p.name==item->m_WearPositions[w].Name.c_str()) p.used+=item->m_WearPositions[w].Slots;
    }
    return positions;
}
std::vector<MSREquipment::Requirement> Requirements(CGenericItem* item)
{
    std::vector<MSREquipment::Requirement> requirements;
    if (item) for (unsigned n=0; n<item->m_WearPositions.size(); ++n)
        requirements.push_back({item->m_WearPositions[n].Name.c_str(),item->m_WearPositions[n].Slots});
    return requirements;
}
bool UnwornWearable(CGenericItem* item)
{
    return item && MSREquipment::Eligible((item->MSProperties()&ITEM_WEARABLE)!=0,item->CurrentAttack!=nullptr,
        item->m_pParentContainer!=nullptr,item->IsWorn(),item->m_WearPositions.size(),
        (item->MSProperties()&ITEM_GROUPABLE)!=0,item->iQuantity);
}
ulong ParentID(CGenericItem* item) { return item && item->m_pParentContainer ? item->m_pParentContainer->m_iId : 0; }
std::string Occupant(const std::string& position)
{
    std::string name; unsigned count=0;
    for (unsigned n=0; n<player.Gear.size(); ++n)
    {
        auto* item=player.Gear[n];
        if (!item || item->m_pParentContainer || !item->IsWorn() || !(item->MSProperties()&ITEM_WEARABLE)) continue;
        for (unsigned w=0; w<item->m_WearPositions.size(); ++w)
            if (position==item->m_WearPositions[w].Name.c_str())
            { if (!count) name=item->DisplayName(); ++count; break; }
    }
    if (count>1) { char more[24]; snprintf(more,sizeof(more)," +%u",count-1); name+=more; }
    return count ? name : "Empty";
}
class EquipmentDragInput : public InputSignal
{
    CContainerPanel* owner;
public:
    explicit EquipmentDragInput(CContainerPanel* p):owner(p) {}
    void cursorMoved(int,int,Panel*) override { owner->MoveItemDrag(); }
    void mouseReleased(MouseCode code,Panel*) override { if (code==MOUSE_LEFT) owner->EndItemDrag(); }
    void mousePressed(MouseCode code,Panel*) override { if (code==MOUSE_RIGHT) owner->CancelItemDrag(); }
    void mouseDoublePressed(MouseCode code,Panel*) override { if (code==MOUSE_LEFT) owner->MarkDragDoubleClick(); }
    void mouseWheeled(int delta,Panel*) override { owner->EquipmentWheel(delta); }
    void keyPressed(KeyCode code,Panel*) override { if (code==KEY_ESCAPE) owner->CancelItemDrag(); }
    void keyTyped(KeyCode code,Panel*) override { if (code==KEY_ESCAPE) owner->CancelItemDrag(); }
    void cursorEntered(Panel*) override {}
    void cursorExited(Panel*) override {}
    void keyReleased(KeyCode,Panel*) override {}
    void keyFocusTicked(Panel*) override {}
};
#ifndef NDEBUG
void DebugEquipment()
{
    if (gViewPort && gViewPort->m_pContainerMenu) gViewPort->m_pContainerMenu->DebugEquipmentState();
}
bool DebugID(int argument,ulong& id)
{
    const char* text=gEngfuncs.Cmd_Argv(argument);
    if (!text || !*text) return false;
    for (const char* p=text;*p;++p) if (*p<'0' || *p>'9') return false;
    char* end=nullptr; id=strtoul(text,&end,10);
    return end && !*end;
}
void DebugEquipmentDrop()
{
    ulong id=0;
    if (gViewPort && gViewPort->m_pContainerMenu && gEngfuncs.Cmd_Argc()==3 && DebugID(1,id))
        gViewPort->m_pContainerMenu->DebugDrop(id,gEngfuncs.Cmd_Argv(2));
}
void DebugEquipmentContainer()
{
    ulong id=0;
    if (gViewPort && gViewPort->m_pContainerMenu && gEngfuncs.Cmd_Argc()==2 && DebugID(1,id))
        gViewPort->m_pContainerMenu->DebugContainer(id);
}
#endif
}

class CEquipmentSlot : public Panel
{
    MSLabel *title,*occupant;
    bool validTarget=false, hoveredTarget=false;
public:
    std::string name;
    CEquipmentSlot(Panel* parent):Panel(0,0,100,62)
    {
        setParent(parent);
        title=new MSLabel(this,"",6,2,90,24); occupant=new MSLabel(this,"",6,27,90,28);
        title->setFont(g_FontSml); occupant->setFont(g_FontSml);
        title->setContentFitted(false); occupant->setContentFitted(false);
    }
    void Show(const MSREquipment::Position& position,int x,int y,int width,bool valid,bool hovered)
    {
        name=position.name;setBounds(x,y,width,62);setVisible(true);
        setBgColor(valid ? 38 : 23,valid ? 65 : 35,valid ? 40 : 37,0);
        validTarget=valid;hoveredTarget=hovered;
        title->setBounds(6,2,width-12,24);occupant->setBounds(6,27,width-12,28);
        title->setFgColor(valid?226:219,valid?229:183,valid?168:112,0);
        occupant->setFgColor(186,200,188,0);
        std::string caption=name;
        if (caption.compare(0,5,"right")==0) caption="R. "+caption.substr(5);
        else if (caption.compare(0,4,"left")==0) caption="L. "+caption.substr(4);
        char text[160];snprintf(text,sizeof(text),"%s  %lld/%lld",caption.c_str(),position.used,position.capacity);
        title->setText(text);occupant->setText(Occupant(name).c_str());
    }
    void paintBackground() override
    {
        drawSetColor(validTarget?38:23,validTarget?65:35,validTarget?40:37,0);
        drawFilledRect(0,0,getWide(),getTall());
        drawSetColor(validTarget?164:84,validTarget?184:104,validTarget?101:104,0);
        const int edge=validTarget&&hoveredTarget?2:1;
        drawFilledRect(0,0,getWide(),edge);drawFilledRect(0,getTall()-edge,getWide(),getTall());
        drawFilledRect(0,0,edge,getTall());drawFilledRect(getWide()-edge,0,getWide(),getTall());
    }
};

void CContainerPanel::InitializeEquipmentUI()
{
    m_EquipmentHeading=new MSLabel(this,"EQUIPMENT SLOTS",0,0,100,24);
    m_EquipmentHeading->setFont(g_FontSml);m_EquipmentHeading->setFgColor(219,183,112,0);
    m_EquipmentScroll=new CTFScrollPanel(0,0,1,1);m_EquipmentScroll->setParent(this);
    m_EquipmentScroll->setScrollBarAutoVisible(false,true);m_EquipmentScroll->setScrollBarVisible(false,true);
    m_DragCapture=new Panel(0,0,1,1);m_DragCapture->setParent(this);m_DragCapture->setBgColor(0,0,0,255);
    m_DragCapture->addInputSignal(new EquipmentDragInput(this));m_DragCapture->setVisible(false);
    m_DragGhost=new MSLabel(m_DragCapture,"",0,0,320,32);
    m_DragGhost->setFont(g_FontSml);m_DragGhost->setFgColor(240,224,167,0);m_DragGhost->setBgColor(13,23,23,20);
#ifndef NDEBUG
    gEngfuncs.pfnAddCommand("msr_ui_equipment",DebugEquipment);
    gEngfuncs.pfnAddCommand("msr_ui_drop",DebugEquipmentDrop);
    gEngfuncs.pfnAddCommand("msr_ui_container",DebugEquipmentContainer);
#endif
}

void CContainerPanel::LayoutEquipment(int x,int y,int width,int height)
{
    if (!m_EquipmentScroll) return;
    m_EquipmentHeading->setBounds(x,y-25,width,24);
    m_EquipmentScroll->setBounds(x,y,width,height);
    m_EquipmentHeading->setVisible(m_Page!=2);m_EquipmentScroll->setVisible(m_Page!=2);
    RefreshEquipment();
}

void CContainerPanel::RefreshEquipment()
{
    if (!m_EquipmentScroll || !m_AllowUpdate || !isVisible() || m_Page==2) return;
    m_EquipmentHeading->setText(EquipmentDragAvailable()?"EQUIPMENT SLOTS":"EQUIPMENT (VIEW ONLY)");
    const auto positions=Positions();
    CGenericItem* dragged=m_ItemDrag.id ? MSUtil_GetItemByID(m_ItemDrag.id,&player) : nullptr;
    const auto requirements=Requirements(dragged);
    int mouseX=0,mouseY=0;DragCursor(mouseX,mouseY);
    const std::string target=EquipmentTargetAt(mouseX,mouseY);
    const int usable=m_EquipmentScroll->getWide()-24;
    const int columns=usable>=280 ? 2 : 1;
    const int slotWidth=(usable-6*(columns-1))/columns;
    unsigned visible=0;
    for (const auto& p:positions)
    {
        if (p.capacity<=0) continue;
        if (visible>=m_EquipmentSlots.size()) m_EquipmentSlots.push_back(new CEquipmentSlot(m_EquipmentScroll->getClient()));
        const bool valid=m_ItemDrag.dragging && UnwornWearable(dragged) && MSREquipment::Compatible(positions,requirements,p.name);
        m_EquipmentSlots[visible]->Show(p,(visible%columns)*(slotWidth+6),(visible/columns)*68,slotWidth,valid,p.name==target);
        ++visible;
    }
    for (unsigned n=visible;n<m_EquipmentSlots.size();++n) m_EquipmentSlots[n]->setVisible(false);
    m_EquipmentScroll->validate();
}

std::string CContainerPanel::EquipmentTargetAt(int x,int y)
{
    if (!m_EquipmentScroll || !m_EquipmentScroll->isVisible() || !m_EquipmentScroll->isWithin(x,y)) return {};
    for (auto* slot:m_EquipmentSlots)
        if (slot->isVisible() && slot->isWithin(x,y)) return slot->name;
    return {};
}

VGUI_ItemButton* CContainerPanel::VisibleItemButton(ulong id)
{
    if (!m_AllowUpdate || m_Rebuilding || !isVisible() || m_Page!=0) return nullptr;
    for (unsigned n=0;n<m_GearPanel->GearItemButtonTotal;++n)
    {
        auto* container=m_GearPanel->GearItemButtons[n]->m_ItemContainer;
        if (!container || !container->isVisible()) continue;
        for (unsigned i=0;i<container->m_ItemButtonTotal;++i)
        {
            auto* button=container->m_ItemButtons[i];
            if (button->isVisible() && button->m_Data.ID==id) return button;
        }
    }
    return nullptr;
}

bool CContainerPanel::BeginItemDrag(void* data,bool doubleClick)
{
    if (!EquipmentDragAvailable() || !m_ModernReady || !m_DragCapture || !data || !m_AllowUpdate || !isVisible() || m_Page!=0) return false;
    const ulong id=static_cast<VGUI_ItemButton*>(data)->m_Data.ID;
    auto* item=MSUtil_GetItemByID(id,&player);
    if (!UnwornWearable(item) || !VisibleItemButton(id)) return false;
    CancelItemDrag();mpMoveItemPanel->setVisible(false);
    int x=0,y=0;DragCursor(x,y);
    m_ItemDrag.Arm(id,ParentID(item),item->iQuantity,x,y,ScreenWidth(),ScreenHeight(),gHUD.m_flTime,doubleClick);
    removeChild(m_DragCapture);addChild(m_DragCapture); // Capture/ghost above all menu children.
    m_DragCapture->setBounds(0,0,ScreenWidth(),ScreenHeight());m_DragCapture->setVisible(true);
    m_DragGhost->setVisible(false);m_DragCapture->setAsMouseCapture(true);
    return true;
}

void CContainerPanel::MoveItemDrag()
{
    if (!m_ItemDrag.id) return;
    auto* item=MSUtil_GetItemByID(m_ItemDrag.id,&player);
    if (!EquipmentDragAvailable() || !UnwornWearable(item) || !VisibleItemButton(m_ItemDrag.id) ||
        !m_ItemDrag.Valid(item->m_iId,ParentID(item),item->iQuantity,ScreenWidth(),ScreenHeight(),gHUD.m_flTime))
    { CancelItemDrag();return; }
    int x=0,y=0;DragCursor(x,y);
    if (m_ItemDrag.Move(x,y)) { UnSelectAllItems();ResetClicks(); }
    if (!m_ItemDrag.dragging) return;
    const std::string target=EquipmentTargetAt(x,y);
    const bool valid=MSREquipment::Compatible(Positions(),Requirements(item),target);
    char text[256];snprintf(text,sizeof(text),"%s: %s",valid?"Equip":"Drag to a free compatible slot",item->DisplayName());
    const int ghostX=x+14>ScreenWidth()-325?ScreenWidth()-325:x+14;
    const int ghostY=y+16>ScreenHeight()-38?ScreenHeight()-38:y+16;
    m_DragGhost->setText(text);m_DragGhost->setPos(ghostX>0?ghostX:0,ghostY>0?ghostY:0);m_DragGhost->setVisible(true);
    RefreshEquipment();
}

void CContainerPanel::EndItemDrag()
{
    if (!m_ItemDrag.id) return;
    MoveItemDrag();if (!m_ItemDrag.id) return;
    const auto gesture=m_ItemDrag.Take(); // Exactly one release owns dispatch.
    m_DragCapture->setAsMouseCapture(false);m_DragCapture->setVisible(false);
    if (!gesture.dragging)
    {
        if (auto* button=VisibleItemButton(gesture.id))
        { if (gesture.doubleClick) button->Doubleclicked(); else button->Clicked(); }
        return;
    }
    int x=0,y=0;DragCursor(x,y);
    auto* item=MSUtil_GetItemByID(gesture.id,&player);
    if (UnwornWearable(item) && MSREquipment::Compatible(Positions(),Requirements(item),EquipmentTargetAt(x,y)))
        SendEquipmentDrop(gesture.id,item->m_pParentContainer!=nullptr);
    RefreshEquipment();
}

void CContainerPanel::SendEquipmentDrop(ulong id,bool fromBag)
{
    if (!EquipmentDragAvailable()) return;
    char command[128];
    if (fromBag)
    {
        snprintf(command,sizeof(command),"inv transfer %lu 0\n",id);
        ServerCmd(command);
    }
    snprintf(command,sizeof(command),"use -1 %lu\n",id);
#ifndef NDEBUG
    ++m_EquipmentCommandBatches;
    gEngfuncs.Con_Printf("MSR_EQUIPMENT_DROP id=%lu from_bag=%i batch=%u\n",id,fromBag,m_EquipmentCommandBatches);
#endif
    ServerCmd(command);
}

bool CContainerPanel::EquipmentDragAvailable() const
{
    const char* value=gEngfuncs.PhysInfo_ValueForKey ? gEngfuncs.PhysInfo_ValueForKey("msr_equip_guard") : nullptr;
    return value && !strcmp(value,"1");
}

void CContainerPanel::DragCursor(int& x,int& y)
{
#ifndef NDEBUG
    // Scoped callback-test coordinates; physical input always uses VGUI below.
    if (m_DebugDragCursor) { x=m_DebugDragX;y=m_DebugDragY;return; }
#endif
    App::getInstance()->getCursorPos(x,y);
}

void CContainerPanel::CancelItemDrag()
{
    const bool captured=m_ItemDrag.id!=0;
    if (m_ItemDrag.dragging) ResetClicks();
    m_ItemDrag.Clear();
    if (m_DragCapture) { if (captured) m_DragCapture->setAsMouseCapture(false);m_DragCapture->setVisible(false); }
    if (m_DragGhost) m_DragGhost->setVisible(false);
    if (captured && !m_Rebuilding) RefreshEquipment();
}

void CContainerPanel::EquipmentWheel(int delta)
{
    if (!m_ItemDrag.id || !m_EquipmentScroll) return;
    int x=0,y=0;App::getInstance()->getCursorPos(x,y);
    if (m_EquipmentScroll->isWithin(x,y))
    { auto* bar=m_EquipmentScroll->getVerticalScrollBar();bar->setValue(bar->getValue()-delta*38);m_EquipmentScroll->validate();MoveItemDrag(); }
}

bool CContainerPanel::KeyInput(int down,int keynum,const char* binding)
{
    // Escape cancels capture first; existing viewport routing still closes the menu.
    if (down && keynum==27) CancelItemDrag();
    return VGUI_ContainerPanel::KeyInput(down,keynum,binding);
}
#ifndef NDEBUG
void CContainerPanel::DebugEquipmentState()
{
    const ulong probeID=gEngfuncs.Cmd_Argc()>1 ? strtoul(gEngfuncs.Cmd_Argv(1),nullptr,10) : m_ItemDrag.id;
    auto* probe=probeID ? MSUtil_GetItemByID(probeID,&player) : nullptr;
    const auto positions=Positions();
    gEngfuncs.Con_Printf("MSR_EQUIPMENT_STATE visible=%i page=%i item=%lu dragging=%i batches=%u slots=%u\n",
        isVisible(),m_Page,m_ItemDrag.id,m_ItemDrag.dragging,m_EquipmentCommandBatches,(unsigned)m_EquipmentSlots.size());
    if (probeID) gEngfuncs.Con_Printf("MSR_EQUIPMENT_ITEM id=%lu exists=%i parent=%lu worn=%i quantity=%i\n",
        probeID,probe!=nullptr,ParentID(probe),probe ? probe->IsWorn() : false,probe ? probe->iQuantity : 0);
    if (probe) for (unsigned n=0;n<probe->m_WearPositions.size();++n)
        gEngfuncs.Con_Printf("MSR_EQUIPMENT_REQUIREMENT id=%lu name=%s units=%i\n",probeID,
            probe->m_WearPositions[n].Name.c_str(),probe->m_WearPositions[n].Slots);
    if (m_AllowUpdate && isVisible() && !m_Rebuilding)
        for (unsigned n=0;n<m_GearPanel->GearItemButtonTotal;++n)
        {
            auto* gear=m_GearPanel->GearItemButtons[n];
            gEngfuncs.Con_Printf("MSR_EQUIPMENT_CONTAINER id=%lu selected=%i container=%i name=%s\n",gear->m_GearItemID,
                static_cast<int>(n)==m_GearPanel->m_Selected,gear->m_GearItem.IsContainer,gear->m_GearItem.Name.c_str());
            auto* container=gear->m_ItemContainer;
            if (!container || !container->isVisible()) continue;
            for (unsigned i=0;i<container->m_ItemButtonTotal;++i)
            {
                auto* button=container->m_ItemButtons[i];
                auto* item=MSUtil_GetItemByID(button->m_Data.ID,&player);
                if (!button->isVisible() || !item) continue;
                int x=button->getWide()/2,y=button->getTall()/2;button->localToScreen(x,y);
                gEngfuncs.Con_Printf("MSR_EQUIPMENT_VISIBLE id=%lu wearable=%i parent=%lu center_visible=%i name=%s\n",item->m_iId,
                    UnwornWearable(item),ParentID(item),container->m_pScrollPanel->isWithin(x,y),item->DisplayName());
            }
        }
    for (const auto& p:positions)
        gEngfuncs.Con_Printf("MSR_EQUIPMENT_SLOT name=%s used=%lld capacity=%lld item=%lu compatible=%i\n",p.name.c_str(),p.used,p.capacity,probeID,
            UnwornWearable(probe) && MSREquipment::Compatible(positions,Requirements(probe),p.name));
}

void CContainerPanel::DebugContainer(ulong id)
{
    if (!m_AllowUpdate || !isVisible() || m_Rebuilding || m_Page!=0 || gViewPort->m_pCurrentMenu!=this) return;
    for (unsigned n=0;n<m_GearPanel->GearItemButtonTotal;++n)
        if (m_GearPanel->GearItemButtons[n]->m_GearItemID==id && m_GearPanel->GearItemButtons[n]->m_GearItem.IsContainer)
        { CancelItemDrag();UnSelectAllItems();m_GearPanel->Select(n);DebugEquipmentState();return; }
    gEngfuncs.Con_Printf("MSR_EQUIPMENT_CONTAINER rejected id=%lu\n",id);
}

void CContainerPanel::DebugDrop(ulong id,const char* slotName)
{
    if (!m_AllowUpdate || !isVisible() || m_Rebuilding || m_Page!=0 || gViewPort->m_pCurrentMenu!=this ||
        !EquipmentDragAvailable() || m_ItemDrag.id || !id || !slotName || !*slotName)
    { gEngfuncs.Con_Printf("MSR_EQUIPMENT_QA rejected=context id=%lu\n",id);return; }
    auto* button=VisibleItemButton(id);
    auto* item=MSUtil_GetItemByID(id,&player);
    if (!button || !UnwornWearable(item))
    { gEngfuncs.Con_Printf("MSR_EQUIPMENT_QA rejected=visible_owned_wearable id=%lu\n",id);return; }
    int startX=button->getWide()/2,startY=button->getTall()/2;button->localToScreen(startX,startY);
    for (Panel* ancestor=button;ancestor;ancestor=ancestor->getParent())
        if (!ancestor->isVisible() || !ancestor->isWithin(startX,startY))
        { gEngfuncs.Con_Printf("MSR_EQUIPMENT_QA rejected=source_clipped id=%lu\n",id);return; }
    RefreshEquipment();
    CEquipmentSlot* target=nullptr;
    for (auto* slot:m_EquipmentSlots) if (slot->isVisible() && slot->name==slotName) { target=slot;break; }
    if (!target) { gEngfuncs.Con_Printf("MSR_EQUIPMENT_QA rejected=unknown_slot id=%lu\n",id);return; }
    // Reveal the actual slot via its existing scroll panel, then use its center.
    int localX=0,localY=0;target->getPos(localX,localY);
    m_EquipmentScroll->setScrollValue(0,localY);m_EquipmentScroll->validate();
    int endX=target->getWide()/2,endY=target->getTall()/2;target->localToScreen(endX,endY);
    if (EquipmentTargetAt(endX,endY)!=slotName)
    { gEngfuncs.Con_Printf("MSR_EQUIPMENT_QA rejected=target_clipped id=%lu\n",id);return; }
    const unsigned before=m_EquipmentCommandBatches;
    gEngfuncs.Con_Printf("MSR_EQUIPMENT_QA before id=%lu slot=%s parent=%lu worn=%i from=%i,%i to=%i,%i\n",
        id,slotName,ParentID(item),item->IsWorn(),startX,startY,endX,endY);
    struct CursorScope { bool& flag;CursorScope(bool& f):flag(f){flag=true;}~CursorScope(){flag=false;} } scope(m_DebugDragCursor);
    m_DebugDragX=startX;m_DebugDragY=startY;
    const bool armed=BeginItemDrag(button,false);
    m_DebugDragX=endX;m_DebugDragY=endY;
    if (armed) { MoveItemDrag();EndItemDrag(); }
    CancelItemDrag();
    gEngfuncs.Con_Printf("MSR_EQUIPMENT_QA after id=%lu armed=%i command_batches=%u gesture=%lu server_result=pending callback_test=1 physical_input=0\n",
        id,armed,m_EquipmentCommandBatches-before,m_ItemDrag.id);
    DebugEquipmentState();
}
#endif
