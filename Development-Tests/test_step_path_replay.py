"""Compile/replay the actual PM_WalkMove body against deterministic trace results.

Run in a Visual Studio x86 developer environment. This tests path selection;
engine hull tracing is deliberately supplied as a fixture rather than replaced.
The extracted production function is compiled unchanged, then its former guard
is compiled as a baseline so the missed-floor regression must be reproduced.
"""
from pathlib import Path
import argparse,json,re,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'Full-Source/msr_source/src/game/shared/movement/pm_shared.cpp'

PRELUDE=r'''
#include <cassert>
#include <cmath>
#include <cstdio>
#include <string>
#include <vector>
struct Vector { float v[3]{}; Vector()=default; Vector(float x,float y,float z):v{x,y,z}{}; float& operator[](int i){return v[i];} const float& operator[](int i)const{return v[i];} };
void VectorCopy(const Vector&a,Vector&b){b=a;} void VectorClear(Vector&a){a=Vector();}
void VectorAdd(const Vector&a,const Vector&b,Vector&c){for(int i=0;i<3;i++)c[i]=a[i]+b[i];}
void VectorScale(const Vector&a,float f,Vector&b){for(int i=0;i<3;i++)b[i]=a[i]*f;}
float Length(const Vector&a){return std::sqrt(a[0]*a[0]+a[1]*a[1]+a[2]*a[2]);}
float VectorNormalize(Vector&a){float f=Length(a);if(f)for(int i=0;i<3;i++)a[i]/=f;return f;}
struct Plane{Vector normal;}; struct pmtrace_t{float fraction=1;bool startsolid=false,allsolid=false;Vector endpos;Plane plane;};
struct MoveVars{float accelerate=10,stepsize=18;};
struct Command{float forwardmove=320,sidemove=0;};
struct PMove{Command cmd;Vector forward{0,1,0},right{1,0,0},velocity,basevelocity,origin{0,0,100},up;float maxspeed=320,frametime=.02f,waterjumptime=0;int onground=0,waterlevel=0;MoveVars*movevars;pmtrace_t (*PM_PlayerTrace)(Vector,Vector,int,int);};
constexpr int PM_NORMAL=0; PMove state; PMove*pmove=&state; MoveVars vars;
struct TraceFixture{float fraction;bool startsolid,allsolid;Vector end,normal;};
std::vector<TraceFixture> traces;std::vector<Vector> fly;size_t traceIndex=0,flyIndex=0;
pmtrace_t TestTrace(Vector,Vector,int,int){assert(traceIndex<traces.size());auto f=traces[traceIndex++];return {f.fraction,f.startsolid,f.allsolid,f.end,{f.normal}};}
void PM_Accelerate(Vector wish,float speed,float){VectorScale(wish,speed,pmove->velocity);}
int PM_FlyMove(){assert(flyIndex<fly.size());pmove->origin=fly[flyIndex++];return 0;}
void Reset(){state=PMove();state.movevars=&vars;state.PM_PlayerTrace=TestTrace;traces.clear();fly.clear();traceIndex=flyIndex=0;}
TraceFixture T(float fraction,Vector end,Vector normal=Vector(),bool start=false,bool all=false){return{fraction,start,all,end,normal};}
'''

TESTS=r'''
bool Near(float a,float b){return std::fabs(a-b)<.001f;}
int main(){
const Vector p(0,0,100),end(0,6.4f,100),raised(0,0,118),raisedEnd(0,6.4f,118);
Reset(); traces={T(0,p,Vector(0,-.118087f,-.993003f)),T(1,raised),T(1,end)};fly={p,raisedEnd};PM_WalkMove();
#ifdef FORMER_GUARD
assert(Near(state.origin[1],0));std::puts("former guard reproduces clear-downhill rejection");
#else
assert(Near(state.origin[1],6.4f)&&Near(state.origin[2],100));std::puts("clear downhill step endpoint accepted without artificial lift");
#endif
Reset(); const Vector wallEnd(0,2,100),wallUp(0,2,118);traces={T(.3125f,wallEnd,Vector(0,-1,0)),T(1,raised),T(1,wallEnd,Vector(0,0,1))};fly={wallEnd,wallUp};PM_WalkMove();assert(Near(state.origin[1],2)&&Near(state.origin[2],100));std::puts("solid wall still blocks full movement");
Reset();traces={T(0,p,Vector(0,-1,0)),T(1,raised),T(.5f,Vector(0,6.4f,109),Vector(0,-.8f,.6f))};fly={p,raisedEnd};PM_WalkMove();assert(Near(state.origin[1],0)&&Near(state.origin[2],100));std::puts("real steep surface hit still rejects raised path");
Reset();traces={T(0,p,Vector(0,-1,0)),T(1,raised),T(2.f/18.f,Vector(0,6.4f,116),Vector(0,0,1))};fly={p,raisedEnd};PM_WalkMove();assert(Near(state.origin[1],6.4f)&&Near(state.origin[2],116));std::puts("valid16-unit step remains walkable");
Reset();traces={T(1,end)};PM_WalkMove();assert(Near(state.origin[1],6.4f)&&Near(state.origin[2],100)&&flyIndex==0);std::puts("clear ledge/drop movement does not invent a floor or raise the player");
Reset();state.onground=-1;traces={T(0,p,Vector(0,-1,0))};PM_WalkMove();assert(Near(state.origin[1],0)&&traceIndex==1&&flyIndex==0);std::puts("airborne collision cannot invoke step movement");
// Actual float32 final-BSP trace fixture at(-1700,-6281.5,388.160919):
// horizontal and upward traces both report the same false ceiling. The guard
// cannot manufacture clearance when the engine never permits the raised path.
Reset();state.origin=Vector(-1700,-6281.5f,388.160919f);state.forward=Vector(0,1,0);Vector seam=state.origin;
traces={T(0,seam,Vector(0,-.118087f,-.993003f)),T(0,seam,Vector(0,-.118087f,-.993003f)),T(0,seam,Vector(0,.086049f,.996291f))};fly={seam,seam};PM_WalkMove();assert(Near(state.origin[1],seam[1]));std::puts("exact false-ceiling fixture remains blocked: guard-only seam cure not claimed");
assert(traceIndex==3&&flyIndex==2);return 0;
}
'''

def function_body(text):
    start=text.index('void PM_WalkMove()');brace=text.index('{',start);depth=1;end=brace+1
    while depth:
        if text[end]=='{':depth+=1
        elif text[end]=='}':depth-=1
        end+=1
    return text[start:end]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path);args=parser.parse_args()
    body=function_body(SOURCE.read_text())
    new='if (trace.fraction < 1.0f && trace.plane.normal[2] < 0.7)'
    assert new in body,'Expected production guard missing'
    report={'production_source':str(SOURCE),'scope':'Actual production PM_WalkMove path selection with deterministic trace/fly fixtures; engine tracing separately replayed against final BSP','runs':[],'limitations':['Exact native false-ceiling coordinate also blocks upward trace; this guard alone cannot be claimed to cure it.']}
    with tempfile.TemporaryDirectory(prefix='msr-step-replay-') as folder:
        td=Path(folder)
        for baseline in (True,False):
            label='former-guard-baseline' if baseline else 'production-guard'
            code=body.replace(new,'if (trace.plane.normal[2] < 0.7)') if baseline else body
            cpp=td/(label+'.cpp');exe=td/(label+'.exe');cpp.write_text(PRELUDE+'\n'+code+'\n'+TESTS)
            cmd=['cl.exe','/nologo','/std:c++17','/EHsc','/Od','/Zi','/RTC1','/UNDEBUG',str(cpp),'/Fe:'+str(exe)]
            if baseline:cmd.append('/DFORMER_GUARD')
            build=subprocess.run(cmd,cwd=td,text=True,capture_output=True);assert build.returncode==0,build.stdout+build.stderr
            run=subprocess.run([str(exe)],cwd=td,text=True,capture_output=True);assert run.returncode==0,run.stdout+run.stderr
            report['runs'].append({'variant':label,'pass':True,'output':run.stdout.strip().splitlines()});print(label+': PASS\n'+run.stdout)
    if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
