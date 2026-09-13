#ifndef MS_VGUI_WEAPONPROGRESS_H
#define MS_VGUI_WEAPONPROGRESS_H

#include "stats/stats.h"
#include <cstdio>

// One visible progression bar; the legacy storage slots never appear here.
class CWeaponProgress : public Panel
{
    MSLabel* m_Title;
    MSLabel* m_XP;
    Panel* m_Track;
    Panel* m_Fill;
public:
    explicit CWeaponProgress(Panel* parent) : Panel(0, 0, 100, 68)
    {
        setParent(parent); setBgColor(0, 0, 0, 255);
        m_Title = new MSLabel(this, "", 0, 0, 100, 24);
        m_XP = new MSLabel(this, "", 0, 24, 100, 22);
        m_Title->setFont(g_FontSml); m_XP->setFont(g_FontSml);
        m_Title->setFgColor(227, 231, 224, 0);
        m_XP->setFgColor(159, 177, 178, 0);
        m_Track = new Panel(0, 49, 100, 7); m_Track->setParent(this);
        m_Track->setBgColor(49, 62, 64, 0);
        m_Fill = new Panel(0, 0, 0, 7); m_Fill->setParent(m_Track);
        m_Fill->setBgColor(219, 183, 112, 0);
    }
    void SetSkill(const char* name, CStat& skill, int width)
    {
        width = width > 40 ? width : 40;
        setSize(width, 68);
        m_Title->setSize(width, 24); m_XP->setSize(width, 22);
        m_Track->setSize(width, 7);
        char text[256];
        snprintf(text, sizeof(text), "%s  /  Level %i", name, skill.Value());
        m_Title->setText(text);
        UnifiedWeapon::State state{};
        double ratio = 0;
        if (!skill.WeaponProgress(state))
            snprintf(text, sizeof(text), "XP updating...");
        else if (!state.required)
        {
            snprintf(text, sizeof(text), "Level cap reached");
            ratio = 1;
        }
        else
        {
            ratio = static_cast<double>(state.xp) / state.required;
            snprintf(text, sizeof(text), "%llu / %llu XP  (%.1f%%)",
                static_cast<unsigned long long>(state.xp),
                static_cast<unsigned long long>(state.required), 100.0 * ratio);
        }
        if (ratio < 0) ratio = 0; if (ratio > 1) ratio = 1;
        m_XP->setText(text); m_Fill->setSize(static_cast<int>(width * ratio), 7);
    }
};
#endif
