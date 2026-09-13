"""Compile actual bounded game entrypoints with inert engine I/O in a test host."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from package_paths import game_root, baseline_game_root, script_root, frozen_archive
import re, hashlib, json
root = game_root()
baseline = baseline_game_root()
out = Path(__file__).parent / 'build'
out.mkdir(exist_ok=True)
evidence = []
def extract(path, marker):
    text = path.read_text(encoding='utf-8', errors='surrogateescape')
    start = text.index(marker)
    masked = re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
        lambda m: ' ' * len(m.group()), text, flags=re.S)
    brace = masked.index('{', start)
    depth = 1; end = brace + 1
    while depth:
        depth += (masked[end] == '{') - (masked[end] == '}'); end += 1
    result = text[start:end]
    evidence.append({'path': str(path), 'marker':marker, 'line': text[:start].count('\n')+1,
        'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'extract_sha256': hashlib.sha256(result.encode('utf-8',errors='surrogateescape')).hexdigest()})
    return result
parts=[]
for marker in ['int CMSMonster::GetSkillStat(const char*', 'int CMSMonster::GetSkillStat(int iStatIdx,']:
    parts.append(extract(root/'shared/ms/msmonstershared.cpp',marker))
parts.append(extract(root/'shared/ms/msmonstershared.cpp','long double GetExpNeeded(int'))
parts.append(extract(root/'server/monsters/msmonsterserver.cpp','std::tuple<bool, int> CMSMonster::LearnSkill('))
parts.append(extract(baseline/'server/monsters/msmonsterserver.cpp','std::tuple<bool, int> CMSMonster::LearnSkill(').replace('CMSMonster::LearnSkill','LegacyMonster::LearnSkill',1))
parts.append(extract(root/'server/player/playerstats.cpp','std::tuple<bool, int> CBasePlayer::LearnSkill('))
parts.append(extract(root/'server/player/playerstats.cpp','bool CBasePlayer::LearnSkill('))
setter=extract(root/'server/monsters/npcscript.cpp','else if (Cmd.Name() == "setstat")')
parts.append('void CMSMonster::TestSetStat(msstringlist& Params)\n' + setter[setter.index('{'):])
getter=extract(root/'shared/ms/scriptcmds.cpp','else if (Prop.starts_with("skill."))')
parts.append('msstring TestSkillGet(CBasePlayer* pPlayer, msstring Prop)\n' + getter[getter.index('{'): -1] + '\nreturn "-NA-";\n}')
parts.append(extract(baseline/'shared/stats/stats.cpp','int CStat::Value()').replace('CStat::Value','LegacyStatProxy::Value',1))
getter=extract(baseline/'shared/ms/scriptcmds.cpp','else if (Prop.starts_with("skill."))')
parts.append('msstring LegacySkillGet(LegacySkillPlayer* pPlayer, msstring Prop)\n' + getter[getter.index('{'): -1] + '\nreturn "-NA-";\n}')

# Translate only the two arithmetic slices under review, refusing unsupported
# syntax. The getter and constants are copied from the unchanged script inputs;
# this is a bounded formula adapter, not execution of the script engine/events.
scripts=script_root()
consumers=[]
for function,filename,variable in [('TorchDamage','items/item_torch.script','L_DMG'),
                                 ('DemonClawsDamage','items/blunt_gauntlets_demon.script','DMG_SET')]:
    path=scripts/filename
    text=path.read_text(encoding='utf-8',errors='surrogateescape')
    lines=text.splitlines()
    constants=dict(re.findall(r'^const\s+(\w+)\s+([\d.]+)\s*$',text,re.M))
    start=next(i for i,l in enumerate(lines) if l.startswith(f'local {variable} '))
    end=start+1
    while end<len(lines) and lines[end].startswith(f'multiply {variable} '):end+=1
    properties=[]
    def expression(token):
        match=re.fullmatch(r'\$get\(ent_owner,(skill\.[\w.]+)\)',token)
        if match:
            properties.append(match[1])
            return 'std::atof(get(player,"'+match[1]+'").c_str())'
        if re.fullmatch(r'[\d.]+',token):return token
        if token in constants:return constants[token]
        raise ValueError(f'Unsupported formula token {token} in {filename}')
    body=['template<class Player,class Getter> double '+function+'(Player* player,Getter get) {']
    for line in lines[start:end]:
        command,name,token=line.split()
        assert name==variable and command in ('local','multiply')
        body.append(('double result = ' if command=='local' else 'result *= ')+expression(token)+';')
    body.append('return result;\n}')
    consumers.append('\n'.join(body))
    evidence.append({'path':str(path),'marker':f'local {variable}', 'line':start+1,
        'end_line':end, 'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'script_lines':lines[start:end], 'numeric_constants':constants, 'properties':properties,
        'adapter_scope':'arithmetic slice only; no conditions, events, engine, damage application or script VM'})
(out/'entrypoints.inc').write_text('\n\n'.join(parts),encoding='utf-8',errors='surrogateescape')
(out/'script_consumers.inc').write_text('\n\n'.join(consumers),encoding='utf-8')
(out/'entrypoints-provenance.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
print(f'Extracted {len(parts)} actual entrypoint bodies and {len(consumers)} script arithmetic slices; baseline class names adapted for differential tests.')
