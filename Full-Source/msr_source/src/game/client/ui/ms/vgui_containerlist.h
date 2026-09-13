#include "vgui_storemainwin.h"
#include "vgui_moveitempanel.h"
#include "equipment_drag_state.h"

class ContainerButton;
class CInventoryWorldMap;
class CWeaponProgress;
class CEquipmentSlot;
#define CONTAINER_INFO_LABELS 1
#define MAX_CONTAINTER_ITEMS 128
#define MAX_NPCHANDS 3

class CContainerPanel : public VGUI_ContainerPanel
{
private:
	VGUI_MoveItemPanel *mpMoveItemPanel;
	bool m_ModernReady = false, m_Rebuilding = false;
	int m_Page = 0, m_LastWidth = 0, m_LastHeight = 0;
	float m_NextInfoRefresh = 0;
	ulong m_DetailItemID = 0;
	MSLabel *m_Identity = nullptr, *m_Vitals = nullptr, *m_GearHeading = nullptr, *m_DetailHeading = nullptr;
	TextPanel *m_DetailText = nullptr, *m_StatsText = nullptr;
	TextPanel *m_OtherSkillsText = nullptr;
	CWeaponProgress *m_WeaponBars[9] = {};
	CTFScrollPanel *m_StatsScroll = nullptr, *m_DetailScroll = nullptr;
	CTFScrollPanel *m_EquipmentScroll = nullptr;
	MSLabel *m_EquipmentHeading = nullptr, *m_DragGhost = nullptr;
	Panel *m_DragCapture = nullptr;
	std::vector<CEquipmentSlot*> m_EquipmentSlots;
	MSREquipment::Gesture m_ItemDrag;
	VGUI_ItemButton* VisibleItemButton(ulong id);
	std::string EquipmentTargetAt(int x, int y);
	void SendEquipmentDrop(ulong id, bool fromBag);
	void DragCursor(int& x, int& y);
#ifndef NDEBUG
	unsigned m_EquipmentCommandBatches = 0;
	bool m_DebugDragCursor = false;
	int m_DebugDragX = 0, m_DebugDragY = 0;
#endif
	MSButton *m_PageButtons[3] = {};
	MSButton *m_SortButton = nullptr;
	CInventoryWorldMap *m_WorldMap = nullptr;
	CTFScrollPanel* ScrollForPoint(int x, int y);
#ifndef NDEBUG
	unsigned m_InfoRefreshSerial = 0;
#endif

public:
	ulong m_OpenContainerID;

	CContainerPanel(int iTrans, int iRemoveMe, int x, int y, int wide, int tall);
	void UpdateSubtitle();
	void RemoveGear();
	void DropAllSelected();

	virtual void Open(void);
	virtual void Close(void);
	void InitializeModernUI();
	void ApplyLayout();
	void RefreshCharacterInfo();
	void ShowPage(int page);
	void InitializeEquipmentUI();
	void LayoutEquipment(int x, int y, int width, int height);
	void RefreshEquipment();
	bool EquipmentDragAvailable() const;
	bool BeginItemDrag(void* data, bool doubleClick) override;
	void MoveItemDrag();
	void EndItemDrag();
	void CancelItemDrag();
	void MarkDragDoubleClick() { if (m_ItemDrag.id && !m_ItemDrag.dragging) m_ItemDrag.doubleClick = true; }
	void EquipmentWheel(int delta);
	bool KeyInput(int down, int keynum, const char* binding) override;
#ifndef NDEBUG
	void DebugSelectMap(const char* id);
	void DebugPrintState();
	void DebugRunChecks();
	void DebugEquipmentState();
	void DebugDrop(ulong id, const char* slot);
	void DebugContainer(ulong id);
	void DebugAtlas(const char* action);
#endif
	void Update() override;
	void Think() override;
	CTFScrollPanel* GetScrollForStepInput() override;
	void ItemHighlighted(void* data) override;
	void InspectItem(containeritem_t& item);
	void paintBackground() override;

	//From VGUI_ItemCallbackPanel
	void ItemSelectChanged(ulong ID, bool fSelected);
	void GearItemSelected(ulong ID);
	bool GearItemClicked(ulong ID);
	bool GearItemDoubleClicked(ulong ID);
	void ItemDoubleclicked(ulong ID);

	virtual void ItemRightClicked(void *pData);
	virtual void MoveItem(VGUI_ItemButton *pButton, int vNumMove);
	virtual bool ItemClicked(void *pData);
	virtual void InvTypeChanged(int vInvType);
	virtual void AlphabeticChanged(bool bAlphabetic);

	void ActionPerformed();

	void StepInput(bool bDirUp); // MIB FEB2015_21 [INV_SCROLL]
};
