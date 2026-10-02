"""Compile the real Use geometry helper with extracted, unchanged engine math.

Requires the x86 MSVC environment. Writes only the specified test output folder.
Does not launch any game, contact FN, or install a DLL.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def extract(text, signature):
    start = text.index(signature)
    opening = text.index('{', start)
    depth = 1
    cursor = opening + 1
    while depth:
        depth += (text[cursor] == '{') - (text[cursor] == '}')
        cursor += 1
    return text[start:cursor]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parent.parent
    game = repo / 'Full-Source/msr_source/src/game'
    cpp = repo / 'Development-Tests/test_rotating_door_use.cpp'
    angle = game / 'shared/movement/pm_math.cpp'
    clamp = game / 'server/hl/util.cpp'
    helper = game / 'server/player/rotating_door_use.h'
    player = game / 'server/player/player.cpp'
    wrapper = game / 'shared/ms/global.cpp'
    sources = [cpp, Path(__file__).resolve(), angle, clamp, helper, player, wrapper, game/'shared/hl/vector.h']
    before = {str(path):sha(path) for path in sources}
    # This also guards the actual integration: the mount hook precedes selection,
    # legacy selection stays in the else, and no view-global MakeVectors is added.
    body = extract(player.read_text(), 'void CBasePlayer::PlayerUse(void)')
    branch = body[body.index('if (pObject->pev->solid == SOLID_BSP'):body.index('flDot = DotProduct')]
    assert 'FClassnameIs(pObject->pev, "func_door_rotating")' in branch
    assert 'MSRRotatingDoorUse::AimDirection' in branch
    assert branch.count('EngineFunc::MakeVectors(') == 1 and 'UTIL_MakeVectors' not in branch
    assert 'else' in branch and 'VecBModelOrigin' in branch and 'UTIL_ClampVectorToBox' in branch
    assert body.index('MSRMounts::PlayerUse(this)') < body.index('UTIL_MakeVectors(pev->v_angle)')
    wrapper_body = extract(wrapper.read_text(), 'void EngineFunc::MakeVectors(')
    wrapper_code = re.sub(r'//[^\n]*', '', wrapper_body)
    assert wrapper_code.count('AngleVectors(') == 1 and 'gpGlobals' not in wrapper_code and 'UTIL_MakeVectors' not in wrapper_code
    args.output.mkdir(parents=True, exist_ok=True)
    generated = args.output/'production-door-math.cpp'
    prefix = '#include "'+str(game/'shared/hl/vector.h').replace('\\','/')+'"\n#include <cmath>\n#define M_PI 3.14159265358979323846\nenum { PITCH=0,YAW=1,ROLL=2 };\n'
    generated.write_text(prefix + extract(angle.read_text(), 'void AngleVectors(') + '\n' + extract(clamp.read_text(), 'Vector UTIL_ClampVectorToBox(') + '\n')
    exe = args.output/'rotating-door-use.exe'
    cmd = ['cl.exe','/nologo','/std:c++20','/EHsc','/MDd','/Od','/Zi',str(cpp),str(generated),f'/Fe:{exe}',f'/Fo:{args.output}\\',f'/Fd:{args.output / "rotating-door-use.pdb"}']
    compiled = subprocess.run(cmd, capture_output=True, text=True)
    (args.output/'compile.log').write_text(compiled.stdout+compiled.stderr)
    if compiled.returncode:
        raise RuntimeError(compiled.stdout+compiled.stderr)
    ran = subprocess.run([str(exe)], capture_output=True, text=True)
    (args.output/'test.log').write_text(ran.stdout+ran.stderr)
    if ran.returncode:
        raise RuntimeError(ran.stdout+ran.stderr)
    assert before == {str(path):sha(path) for path in sources}, 'Source changed during verification'
    count = int(re.search(r'(\d+) deterministic',ran.stdout).group(1))
    receipt = {'pass':True,'deterministic_checks':count,'player_use_integration_checks':True,'source_sha256':before,
               'generated_math_sha256':sha(generated),'test_exe_sha256':sha(exe),'stdout':ran.stdout.strip(),
               'scope':'Production geometry and exact AngleVectors/UTIL_ClampVectorToBox; no native Use, save or service claim.',
               'native_repeated_use_acceptance_pending':True}
    (args.output/'test-report.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(ran.stdout.strip())
    print('Receipt:',args.output/'test-report.json')

if __name__ == '__main__':
    main()
