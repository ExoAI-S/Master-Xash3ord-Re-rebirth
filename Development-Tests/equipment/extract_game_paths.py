from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from package_paths import game_root, baseline_game_root, script_root, frozen_archive
import re,json,hashlib
root=game_root()
out=Path(__file__).parent/'build';out.mkdir(exist_ok=True)
sources=[]
def extract(path,marker):
    text=path.read_text(encoding='utf-8',errors='surrogateescape');start=text.index(marker)
    masked=re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',lambda m:' '*len(m.group()),text,flags=re.S)
    brace=masked.index('{',start);depth=1;end=brace+1
    while depth:
        depth+=(masked[end]=='{')-(masked[end]=='}');end+=1
    result=text[start:end]
    sources.append({'path':str(path),'line':text[:start].count('\n')+1,'marker':marker,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    return result
wear=extract(root/'shared/weapons/genericitem.cpp','bool CGenericItem::CanWearItem()')
use=extract(root/'server/client.cpp','else if (FStrEq(pcmd, "use"))')
send=extract(root/'client/ui/ms/vgui_equipmentdrag.cpp','void CContainerPanel::SendEquipmentDrop(')
handler=extract(root/'client/ui/ms/vgui_mscontrols.cpp','class CHandler_ItemButton :')+';'
detector=extract(root/'client/ui/ms/vgui_mscontrols.h','class VGUI_DoubleClickDetector')+';'
(out/'game_paths.inc').write_text(wear+'\nvoid TestUse(CBasePlayer* pPlayer, const std::vector<std::string>& args, bool bCanUseInventory=true)\n'+use[use.index('{'):]+'\n'+send+'\n',encoding='utf-8',errors='surrogateescape')
(out/'input_paths.inc').write_text(detector+'\n'+handler,encoding='utf-8',errors='surrogateescape')
initial=extract(root/'server/player/playershared.cpp','void CBasePlayer::InitialSpawn(void)')
oldinitial=extract(baseline_game_root()/'server/player/playershared.cpp','void CBasePlayer::InitialSpawn(void)').replace('CBasePlayer::InitialSpawn','CBasePlayer::LegacyInitialSpawn',1)
setwear=extract(root/'shared/ms/scriptcmds.cpp','bool CScript::ScriptCmd_SetWearPos(')
wearable=extract(root/'shared/weapons/genericitem.cpp','else if (Cmd.Name() == "wearable")')
wearable='void CGenericItem::TestWearable(msstringlist& Params)\n'+wearable[wearable.index('{'):]
readitem=extract(root/'shared/weapons/genericitem.cpp','CGenericItem* ReadGenericItem(bool')
(out/'initialization_paths.inc').write_text(initial+'\n'+oldinitial+'\n'+setwear+'\n'+wearable+'\n'+readitem,encoding='utf-8',errors='surrogateescape')
scripts=script_root()
fixtures=[]
for filename,prefix,command in [('player/player_sh_stats.script','wear','setwearpos'),('items/armor_leather.script','vest','wearable')]:
    path=scripts/filename;text=path.read_text()
    lines=[line.split()[1:] for line in text.splitlines() if line.startswith(command+' ')]
    fixtures.append(f'static const std::vector<std::vector<std::string>> {prefix}Commands = '+json.dumps(lines).replace('[','{').replace(']','}')+';')
    sources.append({'path':str(path),'command':command,'lines':lines,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(out/'authored_wear.inc').write_text('\n'.join(fixtures))
(out/'provenance.json').write_text(json.dumps(sources,indent=2),encoding='utf-8')
print('Extracted actual wear-capacity, guarded use, drop dispatch, item input, client initialization and wear metadata paths.')
