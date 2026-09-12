"""Compile the actual FN enable predicate in standalone and original modes."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'Full-Source/msr_source/src/game/server/fn/FNSharedDefs.cpp').read_text()
start = source.index('bool FNShared::IsEnabled(void)')
end = source.index('\n}', start) + 2
function = source[start:end]
harness = '''
#include <cassert>
namespace MSGlobals { bool CentralEnabled, IsLanGame, ServerSideChar; }
class FNShared { public: static bool IsEnabled(); };
''' + function + '''
int main() {
    for (bool central : {false, true})
        for (bool serverCharacters : {false, true})
            for (bool lan : {false, true}) {
                MSGlobals::CentralEnabled = central;
                MSGlobals::ServerSideChar = serverCharacters;
                MSGlobals::IsLanGame = lan;
#ifdef MSR_STANDALONE
                assert(FNShared::IsEnabled() == (central && serverCharacters));
#else
                assert(FNShared::IsEnabled() == (central && serverCharacters && !lan));
#endif
            }
}
'''
with tempfile.TemporaryDirectory(prefix='msr-fn-lan-') as folder:
    work = Path(folder)
    cpp = work / 'fn_lan.cpp'
    cpp.write_text('#include <initializer_list>\n' + harness)
    for mode in ('standalone', 'original'):
        executable = work / (mode + '.exe')
        args = ['cl.exe', '/nologo', '/EHsc', '/std:c++20', '/Od', '/RTC1', str(cpp), '/Fe:' + str(executable)]
        if mode == 'standalone':
            args.append('/DMSR_STANDALONE')
        subprocess.run(args, cwd=work, check=True)
        subprocess.run([str(executable)], check=True, timeout=10)
        print(mode + ': all eight FN/LAN/server-character combinations passed')
