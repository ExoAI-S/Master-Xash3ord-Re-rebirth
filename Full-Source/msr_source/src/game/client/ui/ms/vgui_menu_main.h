
// Menu Dimensions
#define MAINWIN_SIZE_X XRES(120)
#define MAINWIN_SIZE_Y YRES(170)
#define MAINWIN_X XRES(320) - MAINWIN_SIZE_X / 2
#define MAINWIN_Y YRES(240) - MAINWIN_SIZE_Y / 2

#define BTN_SPACER_X XRES(15)
#define BTN_SPACER_Y YRES(10)
#define BTN_SIZE_X (MAINWIN_SIZE_X - BTN_SPACER_X * 2.0f)
#define BTN_SIZE_Y YRES(12)
#define BTN_X MAINWIN_SIZE_X / 2.0f - BTN_SIZE_X / 2.0f
#define BTN_START_Y YRES(50)

#define MAINMENU_FADETIME 0.5f //Thothie DEC2012_24 - reduce menu fade time

#define MAINLABEL_TOP_Y YRES(0)

// Creation
class VGUI_DungeonMaster : public VGUI_MenuBase
{
public:
	VGUI_DungeonMaster(Panel *parent) : VGUI_MenuBase(parent)
	{
		m_Name = "dungeon_master";
		Init();
		m_pMainPanel->setBounds(XRES(200), YRES(105), XRES(240), YRES(270));
		m_Title->setBounds(0,YRES(10),XRES(240),YRES(20));
		m_Title->setText("Dungeon Master");
		m_TitleSep->setVisible(false);
		MSLabel *hint = new MSLabel(m_pMainPanel, "Host control required | Edana events: town gate", XRES(8),YRES(33),XRES(224),YRES(12));
		hint->setFont(g_FontSml);
		hint->setFgColor(190,190,190,0);
		m_ButtonY=YRES(55);
		const char *labels[]={"Show status", "Summon Orc raiders", "Summon giant rats", "Enable random encounters", "Pause random encounters", "Clear director encounter", "Back"};
		for (int i=0;i<7;++i) AddButton(labels[i],XRES(210),msvariant(i));
	}
	void Select(int index, msvariant &data) override
	{
		if (index==6) { setVisible(false); ((VGUI_MenuBase *)getParent())->Reset(); return; }
		const char *commands[]={"ms_dm status\n","ms_dm orcs\n","ms_dm rats\n","ms_dm on\n","ms_dm off\n","ms_dm clear\n"};
		if (index>=0 && index<6) gEngfuncs.pfnClientCmd((char *)commands[index]);
	}
};

class VGUI_MenuMain : public VGUI_MenuBase
{
public:
	class CPanel_Options *m_OptionsPanel;
	VGUI_DungeonMaster *m_DungeonMaster;

	VGUI_MenuMain(Panel *pParent) : VGUI_MenuBase(pParent)
	{
		m_Name = "main";

		Init();

		struct btninfo_t
		{
			const char *Name;
			int Width;
			int OptionScreen;
		} static g_ButtonNames[] =
			{
				"#PARTY", XRES(28), OPTIONSC_PARTY,
				"#VOTEKICK", XRES(30), OPTIONSC_VOTEKICK,
				"#VOTETIME", XRES(23), OPTIONSC_VOTETIME,
				"Dungeon Master", XRES(90), 0,
				"#CANCEL", XRES(33), 0};

		m_ButtonY = BTN_START_Y;
		for (unsigned int i = 0; i < std::size(g_ButtonNames); i++)
			MSButton *pButton = AddButton(Localized(g_ButtonNames[i].Name), g_ButtonNames[i].Width, msvariant(g_ButtonNames[i].OptionScreen));

		m_OptionsPanel = new CPanel_Options(this);
		m_OptionsPanel->setVisible(false);
		m_DungeonMaster = new VGUI_DungeonMaster(this);
		m_DungeonMaster->setVisible(false);
	}

	// Update
	void Update()
	{
		m_Buttons[OPT_VOTEKICK]->setEnabled(false);
		m_Buttons[OPT_VOTETIME]->setEnabled(false);
		for (unsigned int i = 0; i < vote_t::VotesTypesAllowed.size(); i++)
		{
			if (vote_t::VotesTypesAllowed[i] == "kick")
				m_Buttons[OPT_VOTEKICK]->setEnabled(true);
			if (vote_t::VotesTypesAllowed[i] == "advtime")
				m_Buttons[OPT_VOTETIME]->setEnabled(true);
		}
		//m_pButton[OPT_VOTE]->SetBGColorRGB( BtnColor );
	}

	void Select(int BtnIdx, msvariant &Data)
	{
		m_pMainPanel->setVisible(false);

		if (BtnIdx == OPT_DUNGEONMASTER)
		{
			m_DungeonMaster->Reset();
			m_DungeonMaster->setVisible(true);
			gEngfuncs.pfnClientCmd((char *)"ms_dm status\n");
			return;
		}
		if (BtnIdx != OPT_CANCEL)
			m_OptionsPanel->Open((option_e)(int)Data);
		else
			//Clicked Cancel
			VGUI::HideMenu(this);
	}

	void Reset(void)
	{
		VGUI_MenuBase::Reset();
		m_OptionsPanel->setVisible(false);
		m_DungeonMaster->setVisible(false);
	}
	bool SlotInput(int slot) override
	{
		return m_DungeonMaster->isVisible() ? m_DungeonMaster->SlotInput(slot) : VGUI_MenuBase::SlotInput(slot);
	}

	// Update the menu before opening it
	//void Open( void )
	//{
	//	foreach( i, MAX_MAINBUTTONS ) m_Buttons[i]->setArmed( false );

	//	Update( );
	//	CMenuPanel::Open( );
	//	m_OpenTime = gpGlobals->time;
	//}
};

VGUI_MainPanel *CreateHUD_MenuMain(Panel *pParent) { return new VGUI_MenuMain(pParent); }
