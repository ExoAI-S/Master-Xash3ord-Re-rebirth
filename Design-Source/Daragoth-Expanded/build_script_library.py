"""Append continuous-world scripts to a private copy of an MSR library.

Every base entry is preserved byte for byte, including global character
creation. Existing identical additions are accepted; conflicting entries
are rejected. The output must differ from the input.
"""
import argparse, hashlib, importlib.util, json, struct, zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('plains_library',ROOT.parent/'Daragoth-Plains/build_script_library.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)

def build(base,out):
    if base.resolve()==out.resolve():raise ValueError('Input and output must differ')
    originals=helper.read_library(base);known=dict(originals)
    additions={p.relative_to(ROOT/'Scripts').as_posix():p.read_bytes() for p in sorted((ROOT/'Scripts').rglob('*.script'))}
    # Support an original base as well as the already expanded private library.
    for p in sorted((ROOT.parent/'Daragoth-Plains/Scripts').rglob('*.script')):
        additions[p.relative_to(ROOT.parent/'Daragoth-Plains/Scripts').as_posix()]=p.read_bytes()
    for name,value in additions.items():
        if name in known and known[name]!=value:raise ValueError('Conflicting existing script: '+name)
    records=originals+[(name,value) for name,value in additions.items() if name not in known]
    offset=12+264*len(records);directory=bytearray();payload=bytearray()
    for name,value in records:
        directory.extend(struct.pack('<256sii',name.encode('ascii'),offset+len(payload),len(value)));payload.extend(value)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_bytes(struct.pack('<4sii',b'PACK',12,len(records))+directory+payload)
    rebuilt=dict(helper.read_library(out))
    assert all(rebuilt[name]==value for name,value in originals)
    report={'base_sha256':hashlib.sha256(base.read_bytes()).hexdigest(),
        'output_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'output_crc32':zlib.crc32(out.read_bytes())&0xffffffff,
        'base_entries':len(originals),'output_entries':len(records),'every_base_entry_preserved':True,
        'added':[name for name,_ in records if name not in known],'path':str(out.resolve())}
    out.with_name('expanded-script-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();print(json.dumps(build(a.base,a.out),indent=2))
