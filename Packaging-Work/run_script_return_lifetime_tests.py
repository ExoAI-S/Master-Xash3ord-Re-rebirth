"""Build a native fixture from production code; never build or launch the game."""
from pathlib import Path
import shutil
import subprocess
import tempfile

WORK = Path(__file__).resolve().parent
SHARED = WORK.parent / 'Full-Source/msr_source/src/game/shared/ms'


def function(source, signature):
    start = source.index(signature)
    opening = source.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def main():
    compiler = shutil.which('cl.exe')
    if not compiler:
        raise SystemExit('Run from an x86 MSVC developer command prompt.')
    fixtures = WORK / '.verification'
    fixtures.mkdir(exist_ok=True)
    fixture = Path(tempfile.mkdtemp(prefix='script-return-lifetimes-', dir=fixtures))
    header = (SHARED / 'stackstring.h').read_text(encoding='utf-8-sig')
    string_class = header[header.index('constexpr int MSSTRING_SIZE'):header.index('typedef mslist<msstring>')]
    strings = (SHARED / 'stackstring.cpp').read_text(encoding='utf-8-sig')
    string_methods = strings[strings.index('msstring::msstring()'):strings.index('bool TokenizeString(')]
    (fixture / 'actual_msstring.inc').write_text(string_class + '\n' + string_methods, encoding='utf-8')
    script = (SHARED / 'script.cpp').read_text(encoding='utf-8-sig')
    start = script.index('Return = (this->*(iFunc->second.GetFunc()))', script.index('const char* CScript::GetVar('))
    end = script.index('return Return.c_str();', start) + len('return Return.c_str();')
    dispatch = script[start:end]
    format_header = (SHARED / 'iscript.h').read_text(encoding='utf-8-sig')
    signatures = ('inline char* ScriptReturnBuffer()', 'inline char * RETURN_FLOAT_PRECISION(',
                  'inline char* RETURN_FLOAT(', 'inline char* RETURN_INT(',
                  'inline char* RETURN_VECTOR(', 'inline const char* VecToString(')
    formatters = '\n\n'.join(function(format_header, signature) for signature in signatures)
    shutil.copy2(WORK / 'test_script_return_lifetimes.cpp', fixture)
    command = [compiler, '/nologo', '/std:c++20', '/EHsc', '/MT', '/Od', '/Zi', '/utf-8', '/W3',
               'test_script_return_lifetimes.cpp', '/Fe:script_return_lifetime_tests.exe']

    def run(selected_dispatch, selected_formatters):
        (fixture / 'actual_dispatch.inc').write_text(selected_dispatch, encoding='utf-8')
        (fixture / 'actual_formatters.inc').write_text(selected_formatters, encoding='utf-8')
        subprocess.run(command, cwd=fixture, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return subprocess.run([str(fixture / 'script_return_lifetime_tests.exe')], cwd=fixture, capture_output=True, text=True)

    result = run(dispatch, formatters)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    print(result.stdout.strip())
    mutations = {
        'original-getter-temporary': ('return (this->*(iFunc->second.GetFunc()))(FullName, ParserName, Params);', formatters),
        'original-stack-formatters': (dispatch, formatters.replace('char* Return = ScriptReturnBuffer();', 'msstring Return;')),
    }
    for name, values in mutations.items():
        result = run(*values)
        if result.returncode == 0:
            raise AssertionError('Harness missed mutation: ' + name)
        print('PASS: detected ' + name + ': ' + result.stderr.strip())
    (fixture / 'actual_dispatch.inc').write_text(dispatch, encoding='utf-8')
    (fixture / 'actual_formatters.inc').write_text(formatters, encoding='utf-8')
    print('Isolated fixture:', fixture)


if __name__ == '__main__':
    main()
