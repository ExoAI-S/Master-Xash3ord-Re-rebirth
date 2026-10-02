"""Native Debug production mouse mapping and real mount/dismount transitions."""
from pathlib import Path
import hashlib, json, os, re, shutil, time
import argparse, sys
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--lab',type=Path,required=True,help='Prepared synthetic daragoth-development folder')
args=parser.parse_args()
sys.path.insert(0,str(args.lab.resolve()))
import mount_audit as audit
from read_client_mouse_state import snapshot

game = audit.ROOT/'primary/game'
def replace(source, dest):
    tmp=dest.with_name(dest.name+'.input-candidate')
    shutil.copy2(source,tmp); os.replace(tmp,dest)
for name in ('client.dll','client.pdb'):
    source=audit.LAB/'build-game/Debug/msr/bin'/name
    if source.exists(): replace(source,game/'msr/cl_dlls'/name)
replace(audit.LAB/'runtime/game/msr/maps/daragoth.bsp',game/'msr/maps/daragoth.bsp')
# Start/restart the detached server after installing the current meadow; do not
# launch a second sign-on while a previous map reload/client is still pending.
cfg_before=(game/'msr/config.cfg').read_bytes()
config_sha=hashlib.sha256(cfg_before).hexdigest()
control=game/'msr/input_control.cfg'; control.write_text('// idle\n')
startup=f'''exec masterpiece.cfg
developer 1
fps_max 60
gl_vsync 0
rcon_password "{audit.key}"
connect 127.0.0.1:27249
wait 1800
cmd char canjoin
wait 180
cmd char 2
wait 600
god
firstperson
alias input_loop "exec input_control.cfg; wait 120; input_loop"
echo INPUT_TEST_READY
input_loop
'''
(game/'msr/mouse_mount_test.cfg').write_text(startup)
log=game/'mousemounttest.log'
if log.exists(): log.replace(game/'mousemounttest.previous.log')
p=audit.launch([str(game/'xash3d.exe'),'-game','msr','-log','mousemounttest','-window',
    '-width','1280','-height','720','-nointro','-nosound','-nomouse','+exec','mouse_mount_test.cfg'],game,'primary')
def wait_until(predicate,seconds=120):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        result=predicate()
        if result: return result
        time.sleep(.3)
    raise RuntimeError('Native mouse test timed out')
def logtext(): return log.read_text(errors='replace') if log.exists() else ''
def cmd(commands,label):
    control.write_text(commands+'\necho INPUT_ACK_'+label+'\n')
    wait_until(lambda:'INPUT_ACK_'+label in logtext(),12)
    control.write_text('// idle\n')
def probe(label):
    cmd(f'ms_mouse_probe {label} 32\nms_mouse_probe {label}_up -32',label)
    return snapshot(p.pid)
report={'scope':'Detached Debug realm 27249 / synthetic FN 5842; exact production mouse mapping with synthetic deltas. No OS mouse injection.',
        'checks':{},'states':{},'server_states':{},'config_before_sha256':config_sha}
try:
    wait_until(lambda:'INPUT_TEST_READY' in logtext())
    baseline=probe('baseline'); report['states']['baseline']=baseline['buttons']
    # Repair the absent setting, without changing any sensitivity or other preference.
    cmd('+mlook','enable')
    report['states']['restored']=probe('restored')['buttons']
    for index in range(3):
        audit.rcon('ms_mount_place 1 -499.9527 5164 3158 270')
        time.sleep(.7)
        mounted=audit.rcon('ms_stable_audit 1 ride')
        report['server_states'][f'mount{index}']=mounted
        report['checks'][f'cycle{index} mounted']='Stable audit: ride PASS.' in mounted
        time.sleep(.5)
        report['states'][f'mounted{index}']=probe(f'mounted{index}')['buttons']
        cmd('+use\nwait 30\n-use\nwait 120',f'use{index}')
        state=audit.rcon('ms_stable_audit 1 state')
        report['server_states'][f'dismount{index}']=state
        report['checks'][f'cycle{index} ordinary Use dismount']='mount=0 loans=1' in state and 'view=28.0' in state
        report['states'][f'dismounted{index}']=probe(f'dismounted{index}')['buttons']
    # An intentional inverted/custom sensitivity and intentional mlook-off mode
    # must survive a ride too; do not forcibly enable mlook on mount or release.
    cmd('sensitivity 4.7\nm_pitch -0.031\n-mlook','custom')
    probe('custom_before')
    audit.rcon('ms_mount_place 1 -499.9527 5164 3158 270'); time.sleep(.7)
    report['server_states']['custom_mount']=audit.rcon('ms_stable_audit 1 ride')
    probe('custom_mounted')
    cmd('+use\nwait 30\n-use\nwait 120','custom_use')
    report['server_states']['custom_dismount']=audit.rcon('ms_stable_audit 1 state')
    probe('custom_after')
    cmd('+mlook','invert_enable'); probe('inverted')
    # Toggle first/third person through the actual client commands.
    cmd('thirdperson','third'); probe('thirdperson')
    cmd('firstperson','first'); probe('firstperson')
    control.write_text('disconnect\nwait 60\nquit\n')
    wait_until(lambda:p.poll() is not None,15)
    raw=logtext().replace(audit.key,'[redacted]')
    lines=[line for line in raw.splitlines() if 'Mouse probe ' in line]
    pattern=r'Mouse probe (\w+): mlook=(\d) strafe=(\d) pitch=([-\d.]+) forward=([-\d.]+) side=([-\d.]+) up=([-\d.]+) sensitivity=([-\d.]+) m_pitch=([-\d.]+)'
    probes={m[0]:dict(zip(('mlook','strafe','pitch','forward','side','up','sensitivity','m_pitch'),map(float,m[1:]))) for m in re.findall(pattern,raw)}
    report['probes']=probes
    base=probes['baseline']
    report['checks']['baseline reproduces missing mlook and vertical mouse movement']=base['mlook']==0 and base['pitch']==0 and base['forward']<0
    for label in ['restored']+[f'{phase}{i}' for i in range(3) for phase in ('mounted','dismounted')]+['inverted','thirdperson','firstperson']:
        for direction in ('','_up'):
            v=probes[label+direction]
            report['checks'][f'{label+direction} vertical look without movement']=v['mlook']==1 and v['pitch']!=0 and v['forward']==v['side']==v['up']==0
    for label in ('custom_before','custom_mounted','custom_after'):
        v=probes[label]
        report['checks'][label+' retains intentional preferences']=v['mlook']==0 and v['sensitivity']==4.7 and v['m_pitch']==-.031 and v['pitch']==0 and v['forward']<0
    report['checks']['custom settings ride and ordinary dismount confirmed']='Stable audit: ride PASS.' in report['server_states']['custom_mount'] and 'mount=0 loans=1' in report['server_states']['custom_dismount']
    report['checks']['inverted mouse preserved']=probes['inverted']['pitch']<0 and probes['inverted_up']['pitch']>0
    original=probes['baseline']
    report['checks']['normal ride cycles preserve sensitivity and pitch']=all(probes[f'dismounted{i}'][k]==original[k] for i in range(3) for k in ('sensitivity','m_pitch'))
    report['checks']['automated client leaves saved config byte-identical']=hashlib.sha256((game/'msr/config.cfg').read_bytes()).hexdigest()==config_sha
    report['checks']['no snapshot overflow']='datagram overflow' not in raw.lower() and 'buffer overflow' not in raw.lower()
    report['client_sha256']=hashlib.sha256((game/'msr/cl_dlls/client.dll').read_bytes()).hexdigest()
    report['server_sha256']=hashlib.sha256((game/'msr/dlls/ms.dll').read_bytes()).hexdigest()
    report['map_sha256']=hashlib.sha256((game/'msr/maps/daragoth.bsp').read_bytes()).hexdigest()
    report['limitations']=['Synthetic deltas call the exact production native mouse mapping, without OS cursor injection.','Mounts use the Debug ride fixture; dismounts use the normal client Use command.']
    report['pass']=all(report['checks'].values())
finally:
    report['native_lines']=[line for line in logtext().replace(audit.key,'[redacted]').splitlines() if 'Mouse probe' in line]
    (audit.ROOT/'mouse-mount-check.json').write_text(json.dumps(report,indent=2)+'\n')
    if p.poll() is None:
        control.write_text('disconnect\nwait 60\nquit\n')
print(json.dumps({'pass':report['pass'],'checks':report['checks']},indent=2),flush=True)
if not report['pass']: raise SystemExit(1)
