
#include "vgui_int.h"
#include <VGUI_Label.h>
#include <VGUI_BorderLayout.h>
#include <VGUI_LineBorder.h>
#include <VGUI_SurfaceBase.h>
#include <VGUI_TextEntry.h>
#include <VGUI_ActionSignal.h>
#include <string.h>
#include "hud.h"
#include "cl_util.h"
#include "camera.h"
#include "kbutton.h"
#include "cvardef.h"
#include "usercmd.h"
#include "const.h"
#include "camera.h"
#include "in_defs.h"
#include "vgui_teamfortressviewport.h"
#include "vgui_controlconfigpanel.h"
#include "clenv.h"
#include "mslogger.h"
#include "ms/vgui_hud.h"
#include "ms/vgui_containerlist.h"

namespace
{
	class TexturePanel : public Panel, public ActionSignal
	{
	private:
		int _bindIndex;
		TextEntry *_textEntry;

	public:
		TexturePanel() : Panel(0, 0, 256, 276)
		{
			_bindIndex = 2700;
			_textEntry = new TextEntry("2700", 0, 0, 128, 20);
			_textEntry->setParent(this);
			_textEntry->addActionSignal(this);
		}

	public:
		virtual bool isWithin(int x, int y)
		{
			return _textEntry->isWithin(x, y);
		}

	public:
		virtual void actionPerformed(Panel *panel)
		{
			char buf[256];
			_textEntry->getText(0, buf, 256);
			sscanf(buf, "%d", &_bindIndex);
		}

	protected:
		virtual void paintBackground()
		{
			Panel::paintBackground();

			int wide, tall;
			getPaintSize(wide, tall);

			drawSetColor(0, 0, 255, 0);
			drawSetTexture(_bindIndex);
			drawTexturedRect(0, 19, 257, 257);
		}
	};

}

using namespace vgui;

void VGui_ViewportPaintBackground(int extents[4])
{
	gEngfuncs.VGui_ViewportPaintBackground(extents);
}

void *VGui_GetPanel()
{
	return (Panel *)gEngfuncs.VGui_GetPanel();
}

void VGui_Startup()
{
	if (!CRender::CheckOpenGL()) //This exits if not in OpenGL mode
		return;

	Panel *root = (Panel *)VGui_GetPanel();
	root->setBgColor(128, 128, 0, 0);
	//root->setNonPainted(false);
	//root->setBorder(new LineBorder());
	root->setLayout(new BorderLayout(0));

	//root->getSurfaceBase()->setEmulatedCursorVisible(true);

	if (gViewPort != NULL)
	{
		// VidInit also runs when changing fullscreen mode or resolution.
		// Keep the current menus and HUD flags; InitHUD resets them on map entry.
		gViewPort->setParent(root);
		gViewPort->setBounds(0, 0, root->getWide(), root->getTall());
		gViewPort->UpdateCursorState();
		MS_INFO("[VGui_Startup: Preserved UI, hideHUD=%d, viewport=%dx%d]",
			gHUD.m_iHideHUDDisplay, root->getWide(), root->getTall());
	}
	else
	{
		gViewPort = new TeamFortressViewport(0, 0, root->getWide(), root->getTall());
		gViewPort->setParent(root);
		gViewPort->Initialize(); //Master Sword - call Initialize the first time the viewport is created
	}

	HUD_ResolutionChanged();
	if (gViewPort && gViewPort->m_pContainerMenu)
	{
		gViewPort->m_pContainerMenu->CancelItemDrag();
		gViewPort->m_pContainerMenu->ApplyLayout();
	}
	MS_INFO("[VGui_Startup: HUD layout refreshed for %dx%d]", ScreenWidth(), ScreenHeight());
	MS_INFO("[VGui_Startup: Complete]");

	/*
	TexturePanel* texturePanel=new TexturePanel();
	texturePanel->setParent(gViewPort);
	*/
}

void VGui_Shutdown()
{
	delete gViewPort;
	gViewPort = NULL;
}
