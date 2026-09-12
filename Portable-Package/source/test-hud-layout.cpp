
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
inline int XRES(const int x) {
	return (int)(float(x) * ((float)ScreenWidth() / 640.0f) + 0.5f);
}
inline int YRES(const int y) {
	return (int)(float(y) * ((float)ScreenHeight() / 480.0f) + 0.5f);
}
#define BAR_SCALE (1.0f - ((730 - (ScreenWidth() * 0.40f)) / ScreenHeight()))
#define BAR_W (320 * BAR_SCALE)
#define BAR_H (40 * BAR_SCALE)
#define EMBLEM_SIZE (90 * BAR_SCALE)
#define FLASK_W YRES(64 * 0.625) //I want 64x104 in 1024x768 res, and smaller in lower res
#define FLASK_H YRES(104 * 0.625)
struct Bar : Panel { Panel m_Image, label; Panel* m_Label=&label;
void Layout(int x, int y)
		{
			setBounds(x, y, BAR_W, BAR_H);
			m_Image.setSize(getWide(), getTall());
			m_Label->setBounds(0, getTall() / 5, getWide(), YRES(8));
		}
};
struct Flask : Panel { Panel m_Image, label; Panel* m_Label=&label;
void Layout(int x, int y)
		{
			setBounds(x, y, FLASK_W, FLASK_H);
			m_Image.setSize(getWide(), getTall());
			m_Label->setBounds(0, getTall() / 1.5, getWide(), YRES(8));
		}
};

struct Primary : Panel {
    Bar bars[4]; Bar* m_Bar[4]={&bars[0],&bars[1],&bars[2],&bars[3]};
    Panel m_HUDImage,charge[2],labels[2];
    Panel* m_Charge[2]={&charge[0],&charge[1]};
    Panel* m_ChargeLbl[2]={&labels[0],&labels[1]};
    int CHARGE_W,CHARGE_H,CHARGE_SPACER_W;
void OnResolutionChanged()
		{
			setBounds(0, 0, ScreenWidth(), ScreenHeight());
			const int x = 10;
			const int y = ScreenHeight() - 2 * BAR_H - YRES(10);
			m_Bar[0]->Layout(x, y);
			m_Bar[2]->Layout(x, y + BAR_H);
			m_Bar[1]->Layout(x + BAR_W + EMBLEM_SIZE - 1, y);
			m_Bar[3]->Layout(x + BAR_W + EMBLEM_SIZE - 1, y + BAR_H);
			m_HUDImage.setSize(EMBLEM_SIZE, EMBLEM_SIZE);
			m_HUDImage.setPos(x + BAR_W, y - 7 * BAR_SCALE);
			CHARGE_W = XRES(30);
			CHARGE_H = YRES(6);
			CHARGE_SPACER_W = XRES(2);
			for (int i = 0; i < 2; ++i)
			{
				const int chargeX = XRES(304) + (i == 0 ? -CHARGE_W - CHARGE_SPACER_W : CHARGE_SPACER_W);
				m_Charge[i]->setBounds(chargeX, YRES(408), CHARGE_W, CHARGE_H);
				m_ChargeLbl[i]->setBounds(chargeX, YRES(408), CHARGE_W, CHARGE_H);
			}
		}
};

struct Retro : Panel {
    Flask flasks[2]; Flask* m_Flask[2]={&flasks[0],&flasks[1]};
    Panel stamina,weight,staminaLabel,weightLabel,charge[2],labels[2];
    Panel *m_pStamina=&stamina,*m_pWeight=&weight,*m_StaminaLabel=&staminaLabel,*m_WeightLabel=&weightLabel;
    Panel* m_Charge[2]={&charge[0],&charge[1]};
    Panel* m_ChargeLbl[2]={&labels[0],&labels[1]};
    int FLASK_SPACER,FLASK_START_X,FLASK_START_Y,MANA_FLASK_X;
    int STAMINA_X,STAMINA_Y,STAMINA_SIZE_X,STAMINA_SIZE_Y,STAMINA_LBL_SIZE_Y;
    int WEIGHT_SIZE_Y,WEIGHT_LBL_SIZE_Y,CHARGE_W,CHARGE_H,CHARGE_SPACER_W;
void OnResolutionChanged()
		{
			setBounds(0, 0, ScreenWidth(), ScreenHeight());
			FLASK_SPACER = XRES(10);
			FLASK_START_X = XRES(30);
			FLASK_START_Y = ScreenHeight() - YRES(30) - FLASK_H;
			MANA_FLASK_X = FLASK_START_X + FLASK_W + FLASK_SPACER;
			m_Flask[0]->Layout(FLASK_START_X, FLASK_START_Y);
			m_Flask[1]->Layout(MANA_FLASK_X, FLASK_START_Y);
			STAMINA_X = FLASK_START_X;
			STAMINA_Y = YRES(453);
			STAMINA_SIZE_X = 2 * FLASK_W + FLASK_SPACER;
			STAMINA_SIZE_Y = YRES(12);
			STAMINA_LBL_SIZE_Y = YRES(10);
			WEIGHT_SIZE_Y = YRES(10);
			WEIGHT_LBL_SIZE_Y = WEIGHT_SIZE_Y;
			m_pStamina->setBounds(STAMINA_X, STAMINA_Y, STAMINA_SIZE_X, STAMINA_SIZE_Y);
			m_pWeight->setBounds(STAMINA_X, STAMINA_Y + STAMINA_SIZE_Y, STAMINA_SIZE_X, WEIGHT_SIZE_Y);
			m_StaminaLabel->setBounds(0, (STAMINA_SIZE_Y - STAMINA_LBL_SIZE_Y) / 2, STAMINA_SIZE_X, STAMINA_LBL_SIZE_Y);
			m_WeightLabel->setBounds(0, (WEIGHT_SIZE_Y - WEIGHT_LBL_SIZE_Y) / 2, STAMINA_SIZE_X, WEIGHT_LBL_SIZE_Y);
			CHARGE_W = XRES(30);
			CHARGE_H = YRES(6);
			CHARGE_SPACER_W = XRES(2);
			for (int i = 0; i < 2; ++i)
			{
				const int chargeX = XRES(320) + (i == 0 ? -CHARGE_W - CHARGE_SPACER_W : CHARGE_SPACER_W);
				m_Charge[i]->setBounds(chargeX, STAMINA_Y, CHARGE_W, CHARGE_H);
				m_ChargeLbl[i]->setBounds(chargeX, STAMINA_Y, CHARGE_W, CHARGE_H);
			}
		}
};

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
