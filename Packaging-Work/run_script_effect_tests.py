"""Compile and exercise the production light/frameent branches with strict mocks.

Requires an x86 MSVC developer command prompt. Only an isolated fixture under
Packaging-Work/.verification is built; no SDK binary or running game is touched.
"""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

WORK = Path(__file__).resolve().parent
SOURCE = WORK.parent / 'Full-Source/msr_source/src/game/client/entity.cpp'


def branch(source, name):
    start = source.index('\telse if (Params[0] == "' + name + '")', source.index('void CScript::CLScriptedEffect'))
    end = source.index('\n\telse if (Params[0] == ', start + 1)
    return source[start:end]


def main():
    compiler = shutil.which('cl.exe')
    if not compiler:
        raise SystemExit('Run this from an x86 MSVC developer command prompt.')
    fixture_root = WORK / '.verification'
    fixture_root.mkdir(exist_ok=True)
    fixture = Path(tempfile.mkdtemp(prefix='script-effects-', dir=fixture_root))
    source = SOURCE.read_text(encoding='utf-8-sig')
    selected = branch(source, 'frameent') + '\n' + branch(source, 'light')
    (fixture / 'actual_effect_branches.inc').write_text(selected, encoding='utf-8')
    shutil.copy2(WORK / 'test_script_effects.cpp', fixture / 'test_script_effects.cpp')
    command = [compiler, '/nologo', '/std:c++20', '/EHsc', '/MT', '/utf-8', '/W3', 'test_script_effects.cpp', '/Fe:script_effect_tests.exe']
    subprocess.run(command, cwd=fixture, check=True)
    subprocess.run([str(fixture / 'script_effect_tests.exe')], cwd=fixture, check=True)
    # Mutation checks demonstrate that the harness detects both original bugs.
    mutations = {
        'original-light-guard': selected.replace('if( NextParm < Params.size())', 'if( NextParm >= Params.size())'),
        'enqueue-without-model': selected.replace('if (!IsPerm && !gEngfuncs.CL_CreateVisibleEntity', 'RenderEnt.model = nullptr;\n\t\t\t\tif (!IsPerm && !gEngfuncs.CL_CreateVisibleEntity'),
    }
    for name, changed in mutations.items():
        if changed == selected:
            raise AssertionError('Mutation did not match: ' + name)
        (fixture / 'actual_effect_branches.inc').write_text(changed, encoding='utf-8')
        subprocess.run(command, cwd=fixture, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        result = subprocess.run([str(fixture / 'script_effect_tests.exe')], cwd=fixture, capture_output=True, text=True)
        if result.returncode == 0:
            raise AssertionError('Regression harness missed: ' + name)
        print('PASS: detected mutation ' + name + ': ' + result.stderr.strip())
    (fixture / 'actual_effect_branches.inc').write_text(selected, encoding='utf-8')
    print('Isolated fixture:', fixture)


if __name__ == '__main__':
    main()
