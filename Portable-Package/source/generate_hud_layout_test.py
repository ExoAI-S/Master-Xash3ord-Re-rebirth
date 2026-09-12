"""Exercise the actual layout method bodies with geometry-only panel doubles.

The normal client build checks their integration with VGUI. This isolated check
covers anchors, image/label extents, repeated mode switches, and preserved state.
"""
from pathlib import Path
import re

base = Path(__file__).resolve().parent
ui = base / 'MasterSwordRebirth/src/game/client/ui/ms'

def method(text, signature):
    start = text.index(signature)
    brace = text.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end].replace(' override', '')

primary = (ui / 'vgui_health.h').read_text()
retro = (ui / 'vgui_healthretro.h').read_text()
util = (base / 'MasterSwordRebirth/src/game/client/cl_util.h').read_text()
source = r'''
#include <cassert>
#include <cstdio>
int width = 1280, height = 720;
int ScreenWidth() { return width; }
int ScreenHeight() { return height; }
struct Panel {
    int x=0,y=0,w=1,h=1;
    bool visible=true;
    int value=73;
    void setBounds(int a,int b,int c,int d) { x=a;y=b;w=c;h=d; }
    void setSize(int a,int b) { w=a;h=b; }
    void setPos(int a,int b) { x=a;y=b; }
    int getWide() { return w; }
    int getTall() { return h; }
};
'''
source += method(util, 'inline int XRES(') + '\n' + method(util, 'inline int YRES(') + '\n'
source += '\n'.join(re.findall(r'^#define (?:BAR_SCALE|BAR_W|BAR_H|EMBLEM_SIZE|FLASK_W|FLASK_H)\b.*', primary + retro, re.M)) + '\n'
for name, text in [('Bar', primary), ('Flask', retro)]:
    source += f'struct {name} : Panel {{ Panel m_Image, label; Panel* m_Label=&label;\n'
    source += method(text, 'void Layout(int x, int y)') + '\n};\n'
source += '''
struct Primary : Panel {
    Bar bars[4]; Bar* m_Bar[4]={&bars[0],&bars[1],&bars[2],&bars[3]};
    Panel m_HUDImage,charge[2],labels[2];
    Panel* m_Charge[2]={&charge[0],&charge[1]};
    Panel* m_ChargeLbl[2]={&labels[0],&labels[1]};
    int CHARGE_W,CHARGE_H,CHARGE_SPACER_W;
'''
source += method(primary, 'void OnResolutionChanged()') + '\n};\n'
source += '''
struct Retro : Panel {
    Flask flasks[2]; Flask* m_Flask[2]={&flasks[0],&flasks[1]};
    Panel stamina,weight,staminaLabel,weightLabel,charge[2],labels[2];
    Panel *m_pStamina=&stamina,*m_pWeight=&weight,*m_StaminaLabel=&staminaLabel,*m_WeightLabel=&weightLabel;
    Panel* m_Charge[2]={&charge[0],&charge[1]};
    Panel* m_ChargeLbl[2]={&labels[0],&labels[1]};
    int FLASK_SPACER,FLASK_START_X,FLASK_START_Y,MANA_FLASK_X;
    int STAMINA_X,STAMINA_Y,STAMINA_SIZE_X,STAMINA_SIZE_Y,STAMINA_LBL_SIZE_Y;
    int WEIGHT_SIZE_Y,WEIGHT_LBL_SIZE_Y,CHARGE_W,CHARGE_H,CHARGE_SPACER_W;
'''
source += method(retro, 'void OnResolutionChanged()') + '\n};\n'
source += r'''
void inside(Panel& p) {
    assert(p.x>=0 && p.y>=0 && p.w>0 && p.h>0);
    assert(p.x+p.w<=width && p.y+p.h<=height);
    assert(p.value==73 && p.visible);
}
int main() {
    Primary p; Retro r;
    const int modes[][2]={{1280,720},{1920,1080},{2560,1440},{1920,1440},{3440,1440},{3840,2160},{1024,768},{1280,720}};
    int firstY=0;
    for (int pass=0;pass<3;++pass) for (const auto& mode:modes) {
        width=mode[0];height=mode[1];
        p.OnResolutionChanged(); r.OnResolutionChanged();
        assert(p.w==width && p.h==height && r.w==width && r.h==height);
        for (auto& b:p.bars) {
            inside(b); assert(b.m_Image.w==b.w && b.m_Image.h==b.h);
            assert(b.label.w==b.w && b.label.y+b.label.h<=b.h);
        }
        // Lower row stays at the bottom margin, allowing integer sprite rounding.
        assert(height-(p.bars[2].y+p.bars[2].h)>=YRES(10));
        assert(height-(p.bars[2].y+p.bars[2].h)<=YRES(10)+2);
        assert(p.bars[0].y==p.bars[1].y && p.bars[2].y==p.bars[3].y);
        inside(p.m_HUDImage);
        for (auto& f:r.flasks) {
            inside(f); assert(f.m_Image.w==f.w && f.m_Image.h==f.h);
            assert(f.y+f.h==height-YRES(30));
        }
        inside(r.stamina); inside(r.weight);
        for (auto& b:p.charge) inside(b);
        for (auto& b:r.charge) inside(b);
        if(width==1280 && height==720) {
            if(!firstY) firstY=p.bars[0].y;
            assert(firstY==p.bars[0].y);
        }
        std::printf("PASS %dx%d: health y=%d bottom=%d, retro bottom=%d\n",width,height,p.bars[0].y,p.bars[2].y+p.bars[2].h,r.flasks[0].y+r.flasks[0].h);
    }
    std::puts("24 resolution transitions passed; HUD values/visibility preserved.");
}
'''
(base / 'test-hud-layout.cpp').write_text(source)
