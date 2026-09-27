#include "storeshared.h"
#include <vector>

class CStore
{
	mslist<storeitem_t> Items;

public:
	// Entities whose scripts created this store (edict index + serial number), so a
	// merged big-world region that unloads can drop the stores only it was using.
	struct creator_t { int index, serial; };
	std::vector<creator_t> m_Creators;
	bool HasCreator(edict_t *pCreator)
	{
		for (const creator_t &c : m_Creators)
			if (pCreator && c.index == ENTINDEX(pCreator) && c.serial == pCreator->serialnumber)
				return true;
		return false;
	}
	void AddCreator(edict_t *pCreator)
	{
		if (pCreator && !HasCreator(pCreator))
			m_Creators.push_back({ENTINDEX(pCreator), pCreator->serialnumber});
	}

	void SetName(const char *pszName);
	void Offer(edict_t *pePlayer, int iBuyFlags, CBaseMonster *pVendor);
	bool AddItem(const char *pszItemName, int iQuantity, int CostPercent, float flSellRatio, int iBundleAmt);
	storeitem_t *GetItem(const char *pszItemName);
	storeitem_t *GetItem(int idx);
	msstring m_Name;
	void Deactivate();
	void RemoveItem(const char* Name);
	void RemoveAllItems();

	static CStore *GetStoreByName(const char* Name)
	{
		for (unsigned int i = 0; i < m_gStores.size(); i++)
			if (FStrEq(m_gStores[i]->m_Name, Name))
				return m_gStores[i];
		return NULL;
	}
	static void RemoveAllStores()
	{
		while (m_gStores.size())
			m_gStores[0]->Deactivate();
	}
	static mslist<CStore *> m_gStores;
};
