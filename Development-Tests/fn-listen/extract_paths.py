from pathlib import Path
import hashlib,json,sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from package_paths import game_root
root=Path(__file__).resolve().parent
source=game_root()/'server'
old=root.parent/'reference/candidate08-game/server'
out=root/'build'
out.mkdir(exist_ok=True)
def body(text, signature):
    start=text.index(signature); brace=text.index('{',start); level=1; end=brace+1
    while level:
        level+=(text[end]=='{')-(text[end]=='}'); end+=1
    return text[start:end]
def strip_includes(text):
    return '\n'.join(line for line in text.splitlines() if not line.startswith('#include'))+'\n'
for label,base in [('baseline',old),('candidate',source)]:
    (out/f'{label}_manager.inc').write_text(strip_includes((base/'fn/RequestManager.cpp').read_text()))
(out/'manager_declaration.inc').write_text(strip_includes((source/'fn/RequestManager.h').read_text()))
shared=(source/'fn/FNSharedDefs.cpp').read_text()
(out/'load_paths.inc').write_text('\n'.join(body(shared,s) for s in [
    'static bool QueueSlotRequest(', 'void FNShared::LoadCharacter(CBasePlayer* pPlayer)']))
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [
    source/'fn/RequestManager.cpp',source/'fn/RequestManager.h',source/'fn/FNSharedDefs.cpp',old/'fn/RequestManager.cpp']}
(out/'source-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
print('Extracted complete actual baseline/candidate manager and actual character-load/rollback bodies.')
