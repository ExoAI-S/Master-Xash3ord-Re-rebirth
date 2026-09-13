// Player-only inventory presentation. Server item commands remain in containerlist.
#include "inc_weapondefs.h"
#undef DLLEXPORT
#include "hud.h"
#include "cl_util.h"
#include "vgui_teamfortressviewport.h"
#include "vgui_containerlist.h"
#include "vgui_menudefsshared.h"
#include "stats/stats.h"
#include "vgui_weaponprogress.h"
#include "vgui_fantasyframe.h"
#include "worldmap_data.h"
#include "worldmap_atlas.h"
#include "filesystem_shared.h"
#include "vgui_defaultinputsignal.h"
#include <VGUI_SurfaceBase.h>
#include <cmath>
#include <string>
#include <cstdio>
#include <cstring>
#include <VGUI_TextImage.h>

long double GetExpNeeded(int StatValue);
extern int TestExpArray[SKILL_MAX_ATTACK][STAT_MAGIC_TOTAL];

namespace
{
int AtLeast(int a, int b) { return a > b ? a : b; }
int AtMost(int a, int b) { return a < b ? a : b; }
COLOR Ink(227, 231, 224, 0), Gold(219, 183, 112, 0), Muted(159, 177, 178, 0);

bool DuplicateMapName(int index)
{
    for (int i = 0; i < MSRWorldMap::nodeCount; ++i)
        if (i != index && !strcmp(MSRWorldMap::nodes[index].name, MSRWorldMap::nodes[i].name)) return true;
    return false;
}

std::string MapCaption(int index)
{
    std::string caption = MSRWorldMap::nodes[index].name;
    if (DuplicateMapName(index)) caption += std::string("\n") + MSRWorldMap::nodes[index].id;
    return caption;
}

void StyleButton(MSButton* button, const char* text)
{
    button->setText(text);
    button->setFont(g_FontSml);
    button->setContentAlignment(vgui::Label::a_center);
    button->SetArmedColor(Gold);
    button->SetUnArmedColor(Ink);
    button->setBorder(new LineBorder(1, Color(110, 96, 62, 0)));
}

MSLabel* LabelAt(Panel* parent, const char* text)
{
    auto* label = new MSLabel(parent, text, 0, 0, 100, 24);
    label->SetFGColorRGB(Ink);
    return label;
}

TextPanel* TextAt(Panel* parent)
{
    auto* text = new TextPanel("", 0, 0, 100, 100);
    text->setParent(parent);
    text->setFont(g_FontSml);
    text->setFgColor(204, 214, 209, 0);
    text->setBgColor(0, 0, 0, 255);
    return text;
}

void FitTextHeight(TextPanel* text, int width)
{
    text->setSize(AtLeast(40, width), 2000);
    int measuredWidth = 0, measuredHeight = 0;
    text->getTextImage()->getTextSizeWrapped(measuredWidth, measuredHeight);
    text->setSize(AtLeast(40, width), AtLeast(60, measuredHeight + 24));
}

class PageSignal : public ActionSignal
{
    CContainerPanel* owner;
    int page;
public:
    PageSignal(CContainerPanel* p, int value) : owner(p), page(value) {}
    void actionPerformed(Panel*) override { owner->ShowPage(page); }
};

class SortSignal : public ActionSignal
{
    CContainerPanel* owner;
public:
    SortSignal(CContainerPanel* p) : owner(p) {}
    void actionPerformed(Panel*) override
    {
        gEngfuncs.Cvar_SetValue("ms_alpha_inventory", gEngfuncs.pfnGetCvarFloat("ms_alpha_inventory") >= 1 ? 0 : 1);
        owner->AlphabeticChanged(gEngfuncs.pfnGetCvarFloat("ms_alpha_inventory") >= 1);
    }
};

#ifndef NDEBUG
// Debug verification uses the same page callback and requires an already-open menu.
void DebugInventoryPage()
{
    if (!gViewPort || !gViewPort->m_pContainerMenu || gEngfuncs.Cmd_Argc() != 2) return;
    if (gViewPort->m_pCurrentMenu != gViewPort->m_pContainerMenu) return;
    const char* page = gEngfuncs.Cmd_Argv(1);
    if (!page || page[0] < '0' || page[0] > '2' || page[1]) return;
    gViewPort->m_pContainerMenu->ShowPage(page[0] - '0');
}

void DebugInventoryMap()
{
    if (!gViewPort || !gViewPort->m_pContainerMenu || gEngfuncs.Cmd_Argc() != 2) return;
    if (gViewPort->m_pCurrentMenu != gViewPort->m_pContainerMenu) return;
    gViewPort->m_pContainerMenu->DebugSelectMap(gEngfuncs.Cmd_Argv(1));
}

void DebugInventoryAtlas()
{
    if (gViewPort && gViewPort->m_pContainerMenu && gEngfuncs.Cmd_Argc()==2)
        gViewPort->m_pContainerMenu->DebugAtlas(gEngfuncs.Cmd_Argv(1));
}

void DebugInventoryState()
{
    if (gViewPort && gViewPort->m_pContainerMenu)
        gViewPort->m_pContainerMenu->DebugPrintState();
}

void DebugInventoryChecks()
{
    if (!gViewPort || !gViewPort->m_pContainerMenu) return;
    if (gViewPort->m_pCurrentMenu != gViewPort->m_pContainerMenu) return;
    gViewPort->m_pContainerMenu->DebugRunChecks();
}
#endif
}

class CInventoryWorldMap : public CTransparentPanel
{
    enum AtlasAction { ToggleRoutes, ZoomIn, ZoomOut, FitAtlas };
    class AtlasSignal : public ActionSignal
    {
        CInventoryWorldMap* owner;
        AtlasAction action;
    public:
        AtlasSignal(CInventoryWorldMap* p, AtlasAction value) : owner(p), action(value) {}
        void actionPerformed(Panel*) override { owner->AtlasControl(action); }
    };
    class AtlasCanvas : public Panel
    {
        class PanSignal : public vgui::CDefaultInputSignal
        {
            AtlasCanvas* owner;
        public:
            PanSignal(AtlasCanvas* p) : owner(p) {}
            void mousePressed(MouseCode code, Panel*) override { if (code == MOUSE_LEFT) owner->BeginPan(); }
            void mouseReleased(MouseCode code, Panel*) override { if (code == MOUSE_LEFT) owner->EndPan(); }
            void cursorMoved(int, int, Panel*) override { owner->MovePan(); }
            void cursorExited(Panel*) override { owner->EndPan(); }
            void mouseWheeled(int delta, Panel*) override
            {
                int x, y; owner->scroll->getScrollValue(x, y);
                owner->scroll->setScrollValue(x, y - delta * 64);
            }
        };
        CInventoryWorldMap* owner;
        CTFScrollPanel* scroll;
        int textures[MSRWorldChart::tileCount] = {};
        bool attempted = false, available = false, dragging = false;
        int panX = 0, panY = 0, scrollX = 0, scrollY = 0;

        bool UploadTile(int index)
        {
            if (!g_pFileSystem || !getSurfaceBase()) return false;
            CFile file(MSRWorldChart::tiles[index].file, "rb");
            const size_t expected = 18u + 1024u * 1024u * 3u;
            if (!file || file.Size() != expected) return false;
            std::vector<unsigned char> bytes(expected), rgba;
            if (file.Read(bytes.data(), static_cast<int>(expected)) != static_cast<int>(expected) ||
                !MSRWorldAtlas::DecodeTile(bytes.data(), bytes.size(), rgba)) return false;
            textures[index] = getSurfaceBase()->createNewTextureID();
            if (textures[index] <= 0) return false;
            drawSetTextureRGBA(textures[index], reinterpret_cast<const char*>(rgba.data()), 1024, 1024);
            return true;
        }

        void Glow(const MSRWorldChart::Pin& pin)
        {
            const int x = MSRWorldAtlas::Pixel(pin.u, getWide()), y = MSRWorldAtlas::Pixel(pin.v, getTall());
            const float pulse = .5f + .5f * static_cast<float>(std::sin(gHUD.m_flTime * 3.0f));
            const int radius = AtMost(54, AtLeast(20, getTall() / 48)) + static_cast<int>(pulse * 5);
            // VGUI alpha is inverse: 0 is opaque. These translucent ellipses
            // illuminate the artwork around the region instead of replacing it.
            for (int layer = 0; layer < 4; ++layer)
            {
                const int r = radius - layer * radius / 6;
                drawSetColor(255, 194 + layer * 10, 69 + layer * 12, 234 - layer * 5);
                for (int dy = -r; dy <= r; ++dy)
                {
                    const int dx = static_cast<int>(std::sqrt(static_cast<float>(r * r - dy * dy)));
                    drawFilledRect(x - dx, y + dy, x + dx + 1, y + dy + 1);
                }
            }
            drawSetColor(37, 29, 12, 15); drawFilledRect(x - 4, y - 4, x + 5, y + 5);
            drawSetColor(255, 237, 164, 0); drawFilledRect(x - 2, y - 2, x + 3, y + 3);
        }
    public:
        AtlasCanvas(CInventoryWorldMap* p, CTFScrollPanel* s) : Panel(0, 0, 1, 1), owner(p), scroll(s)
        {
            setParent(s->getClient()); addInputSignal(new PanSignal(this));
        }
        bool Available() const { return available; }
        bool Attempted() const { return attempted; }
        void BeginPan()
        {
            App::getInstance()->getCursorPos(panX, panY); scroll->getScrollValue(scrollX, scrollY);
            dragging = true;
        }
        void EndPan() { dragging = false; }
        void MovePan()
        {
            if (!dragging) return;
            if (!isMouseDown(MOUSE_LEFT) || !owner->isVisible() || !owner->atlasScroll->isVisible()) { EndPan(); return; }
            int x, y; App::getInstance()->getCursorPos(x, y);
            scroll->setScrollValue(scrollX + panX - x, scrollY + panY - y);
        }
        void paintBackground() override
        {
            if (!attempted)
            {
                attempted = true; available = true;
                for (int i = 0; i < MSRWorldChart::tileCount; ++i)
                    if (!UploadTile(i)) { available = false; gEngfuncs.Con_Printf("MSR_ATLAS missing or invalid tile: %s\n", MSRWorldChart::tiles[i].file); }
                owner->UpdateLegend();
            }
            drawSetColor(9, 19, 21, 0); drawFilledRect(0, 0, getWide(), getTall());
            drawSetColor(255, 255, 255, 0);
            for (int i = 0; i < MSRWorldChart::tileCount; ++i)
            {
                if (textures[i] <= 0) continue;
                const auto& tile = MSRWorldChart::tiles[i];
                const int x0 = tile.x * getWide() / MSRWorldChart::width;
                const int y0 = tile.y * getTall() / MSRWorldChart::height;
                const int x1 = (tile.x + MSRWorldChart::tileSize) * getWide() / MSRWorldChart::width;
                const int y1 = (tile.y + MSRWorldChart::tileSize) * getTall() / MSRWorldChart::height;
                drawSetTexture(textures[i]); drawTexturedRect(x0, y0, x1, y1);
            }
            const auto* pin = MSRWorldAtlas::FindPin(owner->currentID.c_str());
            if (available && pin) Glow(*pin);
        }
    };
    class SelectSignal : public ActionSignal
    {
        CInventoryWorldMap* owner;
        int index;
    public:
        SelectSignal(CInventoryWorldMap* p, int i) : owner(p), index(i) {}
        void actionPerformed(Panel*) override { owner->Select(index); }
    };
    class Diagram : public Panel
    {
    public:
        int rows = 0, spacing = 80;
        Diagram(Panel* parent) : Panel(0, 0, 1, 1) { setParent(parent); }
        void paintBackground() override
        {
            if (!rows) return;
            const int mid = getWide() / 3;
            drawSetColor(113, 143, 138, 0);
            drawFilledRect(18, 26, mid, 28);
            drawFilledRect(mid, 26, mid + 2, 27 + (rows - 1) * spacing);
            for (int i = 0; i < rows; ++i)
            {
                const int y = 26 + i * spacing;
                drawFilledRect(mid, y, getWide() - 5, y + 2);
                drawFilledRect(getWide() - 9, y - 3, getWide() - 5, y + 5);
            }
        }
    };
    CTFScrollPanel *indexScroll, *routeScroll, *atlasScroll;
    MSLabel *heading, *currentLabel, *selectedLabel, *legend;
    TextPanel* empty;
    MSButton *currentButton, *viewButton, *zoomInButton, *zoomOutButton, *fitButton;
    AtlasCanvas* atlas;
    std::vector<MSButton*> nodeButtons, routeButtons;
    std::vector<MSLabel*> routeNotes;
    Diagram* diagram;
    int selected = -1, current = -1, routeCount = 0;
    bool showRoutes = false;
    float zoom = 1.0f;
    std::string currentID;

public:
    CInventoryWorldMap(Panel* parent) : CTransparentPanel(0, 0, 0, 1, 1)
    {
        setParent(parent);
        heading = LabelAt(this, "DARAGOTH / WORLD ATLAS"); heading->SetFGColorRGB(Gold);
        currentLabel = LabelAt(this, "");
        selectedLabel = LabelAt(this, ""); selectedLabel->SetFGColorRGB(Gold);
        legend = LabelAt(this, "Arrows show authored exits. Layout is schematic; routes may require a vote or an interaction.");
        legend->SetFGColorRGB(Muted);
        currentButton = new MSButton(this, "", 0, 0, 1, 1);
        StyleButton(currentButton, "My location"); currentButton->addActionSignal(new SelectSignal(this, -1));
        viewButton = new MSButton(this, "", 0, 0, 1, 1);
        StyleButton(viewButton, "Routes"); viewButton->addActionSignal(new AtlasSignal(this, ToggleRoutes));
        zoomInButton = new MSButton(this, "", 0, 0, 1, 1);
        StyleButton(zoomInButton, "+"); zoomInButton->addActionSignal(new AtlasSignal(this, ZoomIn));
        zoomOutButton = new MSButton(this, "", 0, 0, 1, 1);
        StyleButton(zoomOutButton, "-"); zoomOutButton->addActionSignal(new AtlasSignal(this, ZoomOut));
        fitButton = new MSButton(this, "", 0, 0, 1, 1);
        StyleButton(fitButton, "Fit"); fitButton->addActionSignal(new AtlasSignal(this, FitAtlas));
        atlasScroll = new CTFScrollPanel(0, 0, 1, 1); atlasScroll->setParent(this);
        atlasScroll->setScrollBarAutoVisible(false, false);
        atlasScroll->setScrollBarVisible(true, true);
        atlas = new AtlasCanvas(this, atlasScroll);
        indexScroll = new CTFScrollPanel(0, 0, 1, 1); indexScroll->setParent(this);
        indexScroll->setScrollBarAutoVisible(false, true);
        indexScroll->setScrollBarVisible(false, true);
        routeScroll = new CTFScrollPanel(0, 0, 1, 1); routeScroll->setParent(this);
        routeScroll->setScrollBarAutoVisible(false, true);
        routeScroll->setScrollBarVisible(false, true);
        diagram = new Diagram(routeScroll->getClient());
        empty = TextAt(routeScroll->getClient());
        for (int i = 0; i < MSRWorldMap::nodeCount; ++i)
        {
            auto* button = new MSButton(indexScroll->getClient(), "", 0, 0, 1, 1);
            StyleButton(button, MapCaption(i).c_str());
            button->setContentAlignment(vgui::Label::a_west);
            button->addActionSignal(new SelectSignal(this, i)); nodeButtons.push_back(button);
        }
        for (int i = 0; i < MSRWorldMap::edgeCount; ++i)
        {
            const auto& edge = MSRWorldMap::edges[i];
            auto* button = new MSButton(routeScroll->getClient(), "", 0, 0, 1, 1);
            StyleButton(button, MapCaption(edge.target).c_str());
            button->addActionSignal(new SelectSignal(this, edge.target)); routeButtons.push_back(button);
            auto* note = LabelAt(routeScroll->getClient(), "");
            std::string caption = edge.conditional ? "Conditional passage" : "Authored passage";
            caption += edge.oneWay ? "  |  Return route unconfirmed" : "  |  Return passage recorded";
            if (edge.arrivalUnverified) caption += "\nArrival point unverified";
            note->setText(caption.c_str()); note->SetFGColorRGB((edge.arrivalUnverified ? Gold : Muted)); routeNotes.push_back(note);
        }
        setVisible(false);
    }

    void RefreshCurrent()
    {
        const std::string map = MSRWorldAtlas::LevelID(gEngfuncs.pfnGetLevelName());
        const bool changed = map != currentID;
        currentID = map;
        current = -1;
        for (int i = 0; i < MSRWorldMap::nodeCount; ++i)
            if (map == MSRWorldMap::nodes[i].id) current = i;
        std::string location = "CURRENT REGION  /  ";
        location += current >= 0 ? MSRWorldMap::nodes[current].name : (map.empty() ? "No active map" : map);
        if (!MSRWorldAtlas::FindPin(map.c_str())) location += "  (unplaced)";
        currentLabel->setText(location.c_str());
        currentButton->setEnabled(current >= 0);
        for (int i = 0; i < MSRWorldMap::nodeCount; ++i)
        {
            std::string caption = i == current ? "[HERE]  " : "";
            caption += MapCaption(i);
            nodeButtons[i]->setText(caption.c_str());
            nodeButtons[i]->SetUnArmedColor(i == current ? Gold : Ink);
        }
        if (changed || selected < 0)
        {
            zoom = MSRWorldAtlas::FindPin(map.c_str()) ? 2.75f : 1.0f;
            Select(current >= 0 ? current : 0);
        }
        UpdateLegend();
    }

    void Select(int index)
    {
        const bool recenter = index < 0;
        if (recenter) { index = current; showRoutes = false; if (zoom < 2) zoom = 2.75f; }
        if (index < 0 || index >= MSRWorldMap::nodeCount) return;
        selected = index;
        routeScroll->setScrollValue(0, 0);
        Layout();
        CenterPin(MSRWorldAtlas::FindPin(MSRWorldMap::nodes[selected].id));
        // Bring the selected location into view without hiding it below the map index.
        indexScroll->setScrollValue(0, selected * (AtLeast(48, YRES(24)) + 4));
    }

    void UpdateLegend()
    {
        if (showRoutes)
            legend->setText("Arrows show authored exits. Routes may require a vote or an interaction.\nAtlas positions and historical artwork do not create travel routes.");
        else if (atlas->Attempted() && !atlas->Available())
            legend->setText("Atlas artwork is missing or invalid. Choose Routes to explore the recorded travel network.");
        else
            legend->setText("Gold glow: your current region. Drag or scroll to pan; + / - zoom; My location recenters.\nPins mark approximate named regions. Unplaced maps remain available in Routes.");
    }

    void ResizeAtlas()
    {
        const int viewportW = AtLeast(1, atlasScroll->getWide() - 20);
        const int viewportH = AtLeast(1, atlasScroll->getTall() - 20);
        const float horizontal = static_cast<float>(viewportW) / MSRWorldChart::width;
        const float vertical = static_cast<float>(viewportH) / MSRWorldChart::height;
        const float scale = (horizontal < vertical ? horizontal : vertical) * zoom;
        const int wide = AtLeast(1, static_cast<int>(MSRWorldChart::width * scale));
        const int tall = AtLeast(1, static_cast<int>(MSRWorldChart::height * scale));
        if (wide != atlas->getWide() || tall != atlas->getTall())
        {
            int x, y; atlasScroll->getScrollValue(x, y);
            const float u = static_cast<float>(x + viewportW / 2) / AtLeast(1, atlas->getWide());
            const float v = static_cast<float>(y + viewportH / 2) / AtLeast(1, atlas->getTall());
            atlas->setSize(wide, tall); atlasScroll->validate();
            atlasScroll->setScrollValue(AtLeast(0, static_cast<int>(u * wide) - viewportW / 2),
                                        AtLeast(0, static_cast<int>(v * tall) - viewportH / 2));
        }
        atlasScroll->validate();
    }

    void CenterPin(const MSRWorldChart::Pin* pin)
    {
        if (!pin) return;
        atlasScroll->setScrollValue(AtLeast(0, MSRWorldAtlas::Pixel(pin->u, atlas->getWide()) - (atlasScroll->getWide() - 20) / 2),
                                   AtLeast(0, MSRWorldAtlas::Pixel(pin->v, atlas->getTall()) - (atlasScroll->getTall() - 20) / 2));
    }

    void AtlasControl(AtlasAction action)
    {
        atlas->EndPan();
        if (action == ToggleRoutes) showRoutes = !showRoutes;
        else if (action == FitAtlas) zoom = 1.0f;
        else if (action == ZoomIn) zoom = zoom * 1.4f < 8.0f ? zoom * 1.4f : 8.0f;
        else if (action == ZoomOut) zoom = zoom / 1.4f > 1.0f ? zoom / 1.4f : 1.0f;
        Layout();
        if (action == FitAtlas) atlasScroll->setScrollValue(0, 0);
    }

    void paintBackground() override
    {
        // Re-evaluate level changes while open as well as on ShowPage(2).
        if (MSRWorldAtlas::LevelID(gEngfuncs.pfnGetLevelName()) != currentID) RefreshCurrent();
        CTransparentPanel::paintBackground();
    }

    void Layout()
    {
        const int w = getWide(), h = getTall(), gap = 18;
        const int indexWidth = AtMost(280, w / 3), row = AtLeast(48, YRES(24));
        heading->setBounds(0, 0, w - 124, 28);
        viewButton->setBounds(w - 114, 0, 114, 28);
        viewButton->setText(showRoutes ? "Atlas" : "Routes");
        currentLabel->setBounds(0, 30, w - 150, 30);
        currentButton->setBounds(w - 140, 29, 140, 30);
        indexScroll->setBounds(0, 76, indexWidth, AtLeast(100, h - 126));
        for (int i = 0; i < (int)nodeButtons.size(); ++i)
            nodeButtons[i]->setBounds(0, i * (row + 4), indexWidth - 22, row);
        indexScroll->validate();
        const int routeX = indexWidth + gap, routeWidth = w - routeX;
        selectedLabel->setBounds(routeX, 76, AtLeast(100, routeWidth - (showRoutes ? 0 : 152)), 42);
        std::string title = selected >= 0 ? MSRWorldMap::nodes[selected].name : "Explore Daragoth";
        if (showRoutes) title += "  /  OUTGOING ROUTES";
        else if (selected >= 0 && !MSRWorldAtlas::FindPin(MSRWorldMap::nodes[selected].id)) title += "\nNo marked region on this atlas";
        if (selected >= 0 && DuplicateMapName(selected)) title += std::string("\n") + MSRWorldMap::nodes[selected].id;
        selectedLabel->setText(title.c_str());
        zoomOutButton->setBounds(w - 144, 77, 38, 30);
        zoomInButton->setBounds(w - 100, 77, 38, 30);
        fitButton->setBounds(w - 56, 77, 56, 30);
        zoomOutButton->setVisible(!showRoutes); zoomInButton->setVisible(!showRoutes); fitButton->setVisible(!showRoutes);
        zoomOutButton->setEnabled(zoom > 1.01f); zoomInButton->setEnabled(zoom < 7.99f);
        atlasScroll->setBounds(routeX, 124, routeWidth, AtLeast(90, h - 174));
        atlasScroll->setVisible(!showRoutes); routeScroll->setVisible(showRoutes);
        if (showRoutes) atlas->EndPan();
        ResizeAtlas();
        routeScroll->setBounds(routeX, 124, routeWidth, AtLeast(90, h - 174));
        const int cardX = AtMost(110, routeWidth / 5), cardWidth = AtLeast(90, routeWidth - cardX - 26);
        const int spacing = AtLeast(108, YRES(62));
        routeCount = 0;
        for (int i = 0; i < MSRWorldMap::edgeCount; ++i)
        {
            const bool show = MSRWorldMap::edges[i].source == selected;
            routeButtons[i]->setVisible(show); routeNotes[i]->setVisible(show);
            if (!show) continue;
            routeButtons[i]->setBounds(cardX, routeCount * spacing, cardWidth, 48);
            routeNotes[i]->setBounds(cardX, routeCount * spacing + 49, cardWidth, 50);
            ++routeCount;
        }
        diagram->rows = routeCount; diagram->spacing = spacing;
        diagram->setBounds(0, 0, cardX - 3, AtLeast(50, routeCount * spacing));
        empty->setBounds(10, 12, routeWidth - 35, 120);
        empty->setText("No confirmed public outgoing passage is charted here.\n\nThis map can still have scripted exits or unfinished connections. Select another map in the list to explore its recorded routes.");
        empty->setVisible(!routeCount);
        legend->setBounds(0, h - 45, w, 44);
        routeScroll->validate();
        UpdateLegend();
    }

    CTFScrollPanel* ScrollForPoint(int x, int y)
    {
        if (!showRoutes && atlasScroll->isWithin(x, y)) return atlasScroll;
        return showRoutes && routeScroll->isWithin(x, y) ? routeScroll : indexScroll;
    }

#ifndef NDEBUG
    bool DebugControl(const char* action)
    {
        if (!strcmp(action,"fit")) AtlasControl(FitAtlas);
        else if (!strcmp(action,"in")) AtlasControl(ZoomIn);
        else if (!strcmp(action,"out")) AtlasControl(ZoomOut);
        else if (!strcmp(action,"routes")) AtlasControl(ToggleRoutes);
        else if (!strcmp(action,"current")) { RefreshCurrent();if (current<0) return false;Select(-1); }
        else return false;
        DebugCheckScroll();return true;
    }
    bool DebugCheckScroll()
    {
        auto* active = showRoutes ? routeScroll : atlasScroll;
        int x = active->getWide() / 2, y = active->getTall() / 2;
        active->localToScreen(x, y);
        const bool helpers = MSRWorldAtlas::SelfTest();
        gEngfuncs.Con_Printf("MSR_ATLAS_STATE level=%s pin=%i atlas_attempted=%i atlas_available=%i view=%s zoom=%.2f pure_checks=%i\n",
            currentID.c_str(), MSRWorldAtlas::FindPin(currentID.c_str()) != nullptr,
            atlas->Attempted(), atlas->Available(), showRoutes ? "routes" : "atlas", zoom, helpers);
        return helpers && ScrollForPoint(x, y) == active && ScrollForPoint(-1, -1) == indexScroll;
    }
#endif
};

void CContainerPanel::InitializeModernUI()
{
    m_Name = "inventory";
    m_NoMouse = false;
    m_Flags |= MENUFLAG_CLOSEONESC;
    m_Identity = LabelAt(this, "CHARACTER & INVENTORY"); m_Identity->SetFGColorRGB(Gold);
    m_Vitals = LabelAt(this, ""); m_Vitals->SetFGColorRGB(Muted);
    m_GearHeading = LabelAt(this, "EQUIPMENT & BAGS"); m_GearHeading->SetFGColorRGB(Gold);
    m_DetailHeading = LabelAt(this, "ITEM DETAILS"); m_DetailHeading->SetFGColorRGB(Gold);
    m_DetailScroll = new CTFScrollPanel(0, 0, 1, 1); m_DetailScroll->setParent(this);
    m_DetailScroll->setScrollBarAutoVisible(false, true);
    m_DetailScroll->setScrollBarVisible(false, true);
    m_DetailText = TextAt(m_DetailScroll->getClient());
    m_DetailText->setText("Select or point to an item to inspect it.\n\nYour hands, equipped gear, and bags are listed on the left.");
    m_StatsScroll = new CTFScrollPanel(0, 0, 1, 1); m_StatsScroll->setParent(this);
    m_StatsScroll->setScrollBarAutoVisible(false, true);
    m_StatsScroll->setScrollBarVisible(false, true);
    m_StatsText = TextAt(m_StatsScroll->getClient());
    InitializeEquipmentUI();
    m_OtherSkillsText = TextAt(m_StatsScroll->getClient());
    for (int i = 0; i < SKILL_MAX_STATS; ++i)
    {
        m_WeaponBars[i] = new CWeaponProgress(m_StatsScroll->getClient());
        m_WeaponBars[i]->setVisible(false);
    }
    m_WorldMap = new CInventoryWorldMap(this);
    const char* captions[] = {"Inventory", "Character", "World Map"};
    for (int i = 0; i < 3; ++i)
    {
        m_PageButtons[i] = new MSButton(this, "", 0, 0, 1, 1);
        StyleButton(m_PageButtons[i], captions[i]);
        m_PageButtons[i]->addActionSignal(new PageSignal(this, i));
    }
    StyleButton(m_pCancelButton, "Close");
    StyleButton(m_ActButton, "Remove");
    m_SortButton = new MSButton(this, "", 0, 0, 1, 1);
    StyleButton(m_SortButton, "A-Z"); m_SortButton->addActionSignal(new SortSignal(this));
    m_ModernReady = true;
#ifndef NDEBUG
    gEngfuncs.pfnAddCommand("msr_ui_page", DebugInventoryPage);
    gEngfuncs.pfnAddCommand("msr_ui_map", DebugInventoryMap);
    gEngfuncs.pfnAddCommand("msr_ui_state", DebugInventoryState);
    gEngfuncs.pfnAddCommand("msr_ui_checks", DebugInventoryChecks);
    gEngfuncs.pfnAddCommand("msr_ui_atlas", DebugInventoryAtlas);
#endif
    ApplyLayout();
}

void CContainerPanel::RefreshCharacterInfo()
{
    if (!m_ModernReady || player.m_CharacterState == CHARSTATE_UNLOADED) return;
#ifndef NDEBUG
    ++m_InfoRefreshSerial;
#endif
    char line[512];
    snprintf(line, sizeof(line), "%s  /  %s", player.DisplayName(), player.GetTitle());
    m_Identity->setText(line);
    snprintf(line, sizeof(line), "Health %.0f / %.0f     Mana %.0f / %.0f     Gold %i", (double)player.m_HP, (double)player.m_MaxHP, (double)player.m_MP, (double)player.m_MaxMP, player.m_Gold);
    m_Vitals->setText(line);
    std::string stats = "CHARACTER\n\n";
    stats += player.DisplayName(); stats += "\nHuman  /  "; stats += player.m_Gender == 0 ? "Male" : "Female";
    stats += "\n"; stats += player.GetTitle(); stats += "\n\nATTRIBUTES\n\n";
    for (int i = 0; i < NATURAL_MAX_STATS; ++i)
    {
        snprintf(line, sizeof(line), "%s    %i\n", NatStatList[i].Name, player.GetNatStat(i)); stats += line;
    }
    stats += "\nWEAPON SKILLS\n";
    const int width = m_StatsScroll->getWide() - 55;
    m_StatsText->setText(stats.c_str());
    FitTextHeight(m_StatsText, width);
    int nextY = 16 + m_StatsText->getTall();
    for (int i = 0; i < SKILL_MAX_STATS; ++i)
    {
        auto* skill = player.FindStat(SKILL_FIRSTSKILL + i);
        const bool weapon = skill && skill->IsUnifiedWeapon();
        m_WeaponBars[i]->setVisible(weapon);
        if (!weapon) continue;
        m_WeaponBars[i]->setPos(16, nextY);
        m_WeaponBars[i]->SetSkill(SkillStatList[i].Name, *skill, width);
        nextY += m_WeaponBars[i]->getTall();
    }
    stats = "\nSPELLCASTING & PARRY\n\n";
    for (int i = 0; i < SKILL_MAX_STATS; ++i)
    {
        auto* skill = player.FindStat(SKILL_FIRSTSKILL + i);
        if (!skill || skill->IsUnifiedWeapon()) continue;
        snprintf(line, sizeof(line), "%s    %i\n", SkillStatList[i].Name, player.GetSkillStat(SKILL_FIRSTSKILL + i)); stats += line;
        const unsigned count = skill->m_SubStats.size();
        const unsigned limit = count < STAT_MAGIC_TOTAL ? count : STAT_MAGIC_TOTAL;
        for (unsigned part = 0; part < limit; ++part)
        {
            const auto& value = skill->m_SubStats[part];
            const char* name = count <= STAT_PROP_TOTAL ? SkillTypeList[part] : SpellTypeList[part];
            if (!strcmp(name, "unused")) continue;
            const double needed = (double)GetExpNeeded(value.Value);
            const double exp = value.Value > 25 ? (double)TestExpArray[i][part] : (double)value.Exp;
            double percent = needed > 0 && value.Value > 0 ? 100.0 * exp / needed : 0.0;
            if (percent < 0) percent = 0; if (percent > 100) percent = 100;
            snprintf(line, sizeof(line), "    %s %i   /   %.1f%% trained\n", name, value.Value, percent); stats += line;
        }
        stats += "\n";
    }
    stats += "\nEquipment and bags remain available on the left.\nChanging characters uses the existing character-selection menu.";
    m_OtherSkillsText->setPos(16, nextY);
    m_OtherSkillsText->setText(stats.c_str());
    FitTextHeight(m_OtherSkillsText, width);
    m_StatsScroll->validate();
}

void CContainerPanel::ShowPage(int page)
{
    CancelItemDrag();
    if (page < 0 || page > 2 || !m_ModernReady) return;
    mpMoveItemPanel->setVisible(false);
    // Gear remains interactive on Character; never transfer an invisible selection.
    if (page != m_Page) UnSelectAllItems();
    m_Page = page;
    if (page == 2) m_WorldMap->RefreshCurrent();
    RefreshCharacterInfo();
    ApplyLayout();
}

#ifndef NDEBUG
void CContainerPanel::DebugAtlas(const char* action)
{
    if (!action || !m_AllowUpdate || !isVisible() || m_Rebuilding || m_Page!=2 || gViewPort->m_pCurrentMenu!=this)
    { gEngfuncs.Con_Printf("MSR_ATLAS_QA rejected=context\n");return; }
    m_WorldMap->DebugCheckScroll();
    const bool accepted=m_WorldMap->DebugControl(action);
    gEngfuncs.Con_Printf("MSR_ATLAS_QA action=%s accepted=%i callback_test=1 physical_input=0\n",action,accepted);
}

void CContainerPanel::DebugSelectMap(const char* id)
{
    if (!id || !m_ModernReady) return;
    for (int i = 0; i < MSRWorldMap::nodeCount; ++i)
        if (!strcmp(id, MSRWorldMap::nodes[i].id)) { ShowPage(2); m_WorldMap->Select(i); return; }
}

void CContainerPanel::DebugPrintState()
{
    gEngfuncs.Con_Printf("MSR_UI_STATE visible=%i page=%i selected=%i refresh=%u split=%i\n",
        isVisible(), m_Page, HasSelectedItems(), m_InfoRefreshSerial, mpMoveItemPanel->isVisible());
}

void CContainerPanel::DebugRunChecks()
{
    // Exercises actual UI callbacks only. No item-transfer/drop/equip callback is dispatched.
    VGUI_ItemButton* item = nullptr;
    for (unsigned i = 0; i < m_GearPanel->GearItemButtonTotal && !item; ++i)
    {
        auto* container = m_GearPanel->GearItemButtons[i]->m_ItemContainer;
        if (container->m_ItemButtonTotal) item = container->m_ItemButtons[0];
    }
    ShowPage(0);
    if (item) item->Select(true);
    const bool selectedBefore = HasSelectedItems();
    ShowPage(1);
    const bool characterClear = !HasSelectedItems() && !mpMoveItemPanel->isVisible();
    const bool characterScroll = ScrollForPoint(-1, -1) == m_StatsScroll;
    if (item) item->Select(true);
    ShowPage(2);
    const bool mapClear = !HasSelectedItems() && !mpMoveItemPanel->isVisible();
    const bool mapScroll = m_WorldMap->DebugCheckScroll();
    ShowPage(0);
    int x = m_DetailScroll->getWide() / 2, y = m_DetailScroll->getTall() / 2;
    m_DetailScroll->localToScreen(x, y);
    const bool detailScroll = ScrollForPoint(x, y) == m_DetailScroll;
    gEngfuncs.Con_Printf("MSR_UI_CHECKS item_fixture=%i selected_before=%i character_clear=%i map_clear=%i character_scroll=%i map_scroll=%i detail_scroll=%i\n",
        item != nullptr, selectedBefore, characterClear, mapClear, characterScroll, mapScroll, detailScroll);
    DebugPrintState();
}
#endif

CTFScrollPanel* CContainerPanel::ScrollForPoint(int x, int y)
{
    if (!m_ModernReady || !m_AllowUpdate || !isVisible()) return nullptr;
    if (m_Page == 2) return m_WorldMap->ScrollForPoint(x, y);
    if (m_EquipmentScroll && m_EquipmentScroll->isVisible() && m_EquipmentScroll->isWithin(x, y)) return m_EquipmentScroll;
    if (m_GearPanel->isVisible() && m_GearPanel->isWithin(x, y)) return m_GearPanel->m_Scroll;
    if (m_Page == 1) return m_StatsScroll;
    if (m_DetailScroll->isWithin(x, y)) return m_DetailScroll;
    const int selected = m_GearPanel->m_Selected;
    if (selected >= 0 && (unsigned)selected < m_GearPanel->GearItemButtonTotal)
    {
        auto* container = m_GearPanel->GearItemButtons[selected]->m_ItemContainer;
        if (container->isVisible()) return container->m_pScrollPanel;
    }
    return m_DetailScroll;
}

CTFScrollPanel* CContainerPanel::GetScrollForStepInput()
{
    int x, y;
    App::getInstance()->getCursorPos(x, y);
    return ScrollForPoint(x, y);
}

void CContainerPanel::ItemHighlighted(void* data)
{
    auto* item = static_cast<VGUI_ItemButton*>(data);
    // Exit/reset events may refer to a button whose underlying item was just deleted.
    if (!item || !m_ModernReady || m_Rebuilding || !m_AllowUpdate || !item->m_Highlighted) return;
    InspectItem(item->m_Data);
}

void CContainerPanel::InspectItem(containeritem_t& item)
{
    if (!m_ModernReady) return;
    m_DetailItemID = item.ID;
    char line[256];
    std::string detail = item.getFullName().c_str();
    snprintf(line, sizeof(line), "\n\nQuantity  %i\nWeight  %.2f\n", item.Quantity, item.Weight); detail += line;
    if (item.Desc.len()) { detail += "\n"; detail += item.Desc.c_str(); }
    detail += "\n\nSelect an item, then choose a bag to move it. Double-click an item in a bag to move it to your hands. Right-click a stack for split options.";
    m_DetailText->setText(detail.c_str());
    FitTextHeight(m_DetailText, m_DetailScroll->getWide() - 38);
    m_DetailScroll->validate();
}

void CContainerPanel::Update()
{
    CancelItemDrag();
    if (!m_AllowUpdate) return;
    mpMoveItemPanel->setVisible(false); // Updates can replace the split panel's item pointer.
    const ulong previousGear = m_GearPanel->m_Selected >= 0 && (unsigned)m_GearPanel->m_Selected < m_GearPanel->GearItemButtonTotal
        ? m_GearPanel->GearItemButtons[m_GearPanel->m_Selected]->m_GearItemID : 0;
    m_Rebuilding = true;
    VGUI_ContainerPanel::Update();
    for (unsigned i = 0; i < m_GearPanel->GearItemButtonTotal; ++i)
        if ((ulong)m_GearPanel->GearItemButtons[i]->m_GearItemID == previousGear) { m_GearPanel->Select(i); break; }
    m_Rebuilding = false;
    bool found = false;
    for (unsigned i = 0; i < m_GearPanel->GearItemButtonTotal; ++i)
    {
        auto* container = m_GearPanel->GearItemButtons[i]->m_ItemContainer;
        for (unsigned j = 0; j < container->m_ItemButtonTotal; ++j)
            if (container->m_ItemButtons[j]->m_Data.ID == m_DetailItemID) { InspectItem(container->m_ItemButtons[j]->m_Data); found = true; }
    }
    if (!found && m_ModernReady)
    {
        if (auto* gear = player.GetGearItem(m_DetailItemID))
        {
            containeritem_t data(gear); InspectItem(data);
        }
        else
        {
            m_DetailItemID = 0;
            m_DetailText->setText("Select or point to an item to inspect it.\n\nChoose equipment or a bag on the left.");
        }
    }
    RefreshCharacterInfo();
    ApplyLayout();
}

void CContainerPanel::Think()
{
    if (!isVisible()) { CancelItemDrag(); return; }
    MoveItemDrag();
    if (m_LastWidth != ScreenWidth() || m_LastHeight != ScreenHeight()) ApplyLayout();
    if (gHUD.m_flTime >= m_NextInfoRefresh || gHUD.m_flTime < m_NextInfoRefresh - 2)
    {
        RefreshCharacterInfo(); RefreshEquipment(); m_NextInfoRefresh = gHUD.m_flTime + .5f;
    }
}

void CContainerPanel::ApplyLayout()
{
    // Closed menus retain buttons, but their pOrig items can be deleted immediately.
    // Open() rebuilds those caches before showing the menu and applying its layout.
    if (!m_ModernReady || m_Rebuilding || !m_AllowUpdate || !isVisible()) return;
    const int w = ScreenWidth(), h = ScreenHeight();
    if (m_LastWidth != w || m_LastHeight != h) CancelItemDrag();
    m_LastWidth = w; m_LastHeight = h;
    setBounds(0, 0, w, h);
    const int margin = AtLeast(16, h / 35), gap = AtLeast(12, h / 60);
    const int top = AtLeast(margin + 154, h / 5), bottom = h - margin - 66;
    const int left = AtMost(320, w / 4), right = AtMost(350, w / 4);
    const int itemX = margin + left + gap, detailX = w - margin - right;
    const int itemW = AtLeast(130, detailX - gap - itemX), bodyH = AtLeast(100, bottom - top);
    m_Identity->setBounds(margin, margin, w - margin * 2 - 180, 32);
    m_Vitals->setBounds(margin, margin + 37, w - margin * 2, 28);
    m_pCancelButton->setBounds(w - margin - 160, margin, 160, 34);
    m_pCancelButton->setContentFitted(false);
    m_pCancelButton->setTextAlignment(vgui::Label::a_center);
    m_pCancelButton->setContentAlignment(vgui::Label::a_center);
    m_pCancelButton->setFont(g_FontSml);
    m_pCancelButton->setText("Close");
    for (int i = 0; i < 3; ++i)
    {
        m_PageButtons[i]->setBounds(margin + i * 150, margin + 74, 138, 34);
        m_PageButtons[i]->SetUnArmedColor(m_Page == i ? Gold : Ink);
    }
    m_GearHeading->setBounds(margin, top - 27, left, 24);
    m_GearPanel->m_iTransparency = 0;
    const int gearHeight = AtLeast(90, bodyH * 42 / 100);
    m_GearPanel->setBounds(margin, top, left, gearHeight);
    m_GearPanel->m_Scroll->setBounds(0, 0, left, gearHeight);
    LayoutEquipment(margin, top + gearHeight + 30, left, AtLeast(60, bodyH - gearHeight - 30));
    m_pTitle->setBounds(itemX, top - 28, AtLeast(50, itemW - 92), 26);
    m_SortButton->setBounds(itemX + itemW - 86, top - 28, 86, 25);
    m_SortButton->setText(gEngfuncs.pfnGetCvarFloat("ms_alpha_inventory") >= 1 ? "Sort: A-Z" : "Sort: found");
    m_SortButton->setVisible(m_Page == 0);
    m_pTitle->setFont(g_FontSml); m_pTitle->setFgColor(219, 183, 112, 0);
    m_pSubtitle->setBounds(margin, h - margin - 18, w - margin * 2, 18);
    m_pSubtitle->setFont(g_FontSml);
    m_pSubtitle->setText(m_Page == 0 ? (EquipmentDragAvailable() ? "Drag wearable to a free slot: equip    Select + bag: move    Double-click: to hands    Right-click: split" : "Select + bag: move    Double-click: to hands    Right-click: split    Equipment slots: view only") : (m_Page == 1 ? "Equipment slots reflect your worn items. Press P or Escape to return to the game." : "Press P or Escape to return to the game."));
    m_InfoPanel->setVisible(false); m_GoldLabel->setVisible(false);
    m_DetailHeading->setBounds(detailX, top - 28, right, 26);
    m_DetailScroll->setBounds(detailX, top, right, bodyH);
    m_DetailText->setPos(10, 12);
    FitTextHeight(m_DetailText, right - 38);
    m_DetailScroll->validate();
    m_ActButton->setBounds(detailX, bottom + 10, right, 34);
    const int gearRow = AtLeast(38, YRES(23));
    for (unsigned i = 0; i < m_GearPanel->GearItemButtonTotal; ++i)
    {
        auto* gear = m_GearPanel->GearItemButtons[i];
        gear->setBounds(0, i * (gearRow + 7), left - 22, gearRow);
        gear->m_iTransparency = 0;
        gear->m_Name->setBounds(9, 2, left - 43, gearRow - 4);
        gear->m_Name->setContentAlignment(vgui::Label::a_west);
        gear->m_Name->SetFGColorRGB(((int)i == m_GearPanel->m_Selected ? Gold : Ink));
        std::string caption = i == 0 ? "HANDS  /  " : (gear->m_GearItem.IsContainer ? "BAG  /  " : "WORN  /  ");
        caption += gear->m_GearItem.Name.c_str(); gear->m_Name->setText(caption.c_str());
        auto* container = gear->m_ItemContainer;
        container->m_iTransparency = 0;
        container->setBounds(itemX, top, itemW, bodyH);
        container->m_pScrollPanel->setBounds(0, 0, itemW, bodyH);
        const bool show = m_Page == 0 && (int)i == m_GearPanel->m_Selected && gear->m_GearItem.IsContainer;
        container->setVisible(show);
        auto* modes = container->m_pInvTypePanel;
        modes->setBounds(itemX, bottom + 8, itemW, 38);
        modes->pAlphaCheckBox->setVisible(false);
        const int modeW = AtLeast(45, (itemW - 14) / 3);
        for (int mode = 0; mode < 3; ++mode)
        {
            modes->InvTypeButtons[mode]->setBounds(mode * (modeW + 4), 0, modeW, 32);
            modes->InvTypeButtons[mode]->setText(mode == 0 ? "Grid" : (mode == 1 ? "Compact" : "List"));
        }
        modes->setVisible(show);
        for (unsigned j = 0; j < container->m_ItemButtonTotal; ++j)
            container->m_ItemButtons[j]->m_PanelMaxWidth = AtLeast(50, itemW - 24);
        container->Update();
        // Empty/missing sprites must never make an owned item unclickable.
        for (unsigned j = 0; j < container->m_ItemButtonTotal; ++j)
        {
            auto* button = container->m_ItemButtons[j];
            if (button->getWide() <= 0 || button->getTall() <= 0)
            {
                button->setSize(AtLeast(70, itemW - 25), 48);
                button->m_Labels[0]->setText(button->m_Data.getFullName());
                button->m_Labels[0]->setBounds(6, 0, button->getWide() - 12, 48);
                button->m_Button->setSize(button->getWide(), button->getTall());
            }
        }
        for (unsigned j = 0; j < container->m_ItemButtonTotal; ++j)
            container->UpdatePosition(j, (int)gEngfuncs.pfnGetCvarFloat("ms_invtype"));
        container->m_pScrollPanel->validate();
    }
    m_GearPanel->m_Scroll->validate();
    m_GearPanel->setVisible(m_Page != 2); m_GearHeading->setVisible(m_Page != 2);
    m_pTitle->setVisible(m_Page == 0); m_DetailHeading->setVisible(m_Page == 0); m_DetailScroll->setVisible(m_Page == 0);
    m_ActButton->setVisible(m_Page == 0 && m_GearPanel->m_Selected != 0);
    m_StatsScroll->setBounds(itemX, top - 20, w - margin - itemX, bodyH + 40);
    m_StatsText->setPos(16, 16);
    FitTextHeight(m_StatsText, w - margin - itemX - 55);
    m_StatsScroll->setVisible(m_Page == 1); m_StatsScroll->validate();
    m_WorldMap->setBounds(margin, top - 14, w - margin * 2, h - top - margin - 30);
    m_WorldMap->setVisible(m_Page == 2); m_WorldMap->Layout();
}

void CContainerPanel::paintBackground()
{
    const int w = getWide(), h = getTall(), m = AtLeast(16, h / 35);
    drawSetColor(17, 23, 19, 5); drawFilledRect(0, 0, w, h);
    drawSetColor(34, 42, 31, 0); drawFilledRect(m - 5, m - 5, w - m + 5, m + 66);
    drawSetColor(137, 117, 77, 0); drawFilledRect(m, m + 64, w - m, m + 66);
    if (m_Page == 0)
    {
        const int top = AtLeast(m + 154, h / 5), bottom = h - m - 66;
        int x, y, width, height;
        m_GearPanel->getBounds(x, y, width, height);
        drawSetColor(25, 32, 25, 0); drawFilledRect(x - 5, top - 4, x + width + 3, bottom + 3);
        drawSetColor(69, 66, 43, 0); drawOutlinedRect(x - 5, top - 4, x + width + 3, bottom + 3);
        m_DetailScroll->getBounds(x, y, width, height);
        drawSetColor(29, 36, 27, 0); drawFilledRect(x, top, x + width, bottom);
        drawSetColor(69, 66, 43, 0); drawOutlinedRect(x, top, x + width, bottom);
    }
    for (const auto& span : MSRFantasyFrame::Cached(w, h))
    {
        drawSetColor(span.color.r, span.color.g, span.color.b, span.color.a);
        drawFilledRect(span.x0, span.y0, span.x1, span.y1);
    }
}
