"""Append only original village scripts, preserving every base library entry."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import struct
import zlib
from village import ROUTES

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('plains_pak',ROOT.parent/'Daragoth-Plains/build_script_library.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
OFFSET=(1650.0473022166188,13216,2688)
PEOPLE={'innkeeper':('Mara the Innkeeper',0,2,'Welcome to Greenhollow. Follow the riding road for the bridge and northern hills.'),
    'smith':('Bren the Smith',1,3,'Good day, traveler. The workshop is beside the square, and the stables are to the east.'),
    'farmer':('Tessa the Farmer',2,1,'The new pasture has fine grass for horses. Please keep the riding paths clear.'),
    'traveler':('Oren the Traveler',1,4,'I came from the old Daragoth valley. You can walk straight back down the southern road.')}


def build(base,out):
    if base.resolve()==out.resolve():raise ValueError('Keep the original script library read-only')
    records=helper.read_library(base);known=dict(records)
    # Normalize only our own new source, so Git's Windows line endings do not
    # change the portable library. Existing base payloads remain byte-exact.
    additions={p.relative_to(ROOT/'Scripts').as_posix():p.read_text(encoding='ascii').encode('ascii')for p in (ROOT/'Scripts').rglob('*.script')}
    for role,points in ROUTES.items():
        name,head,body,greeting=PEOPLE[role]
        route=';'.join('('+','.join(f'{v:.4f}'for v in (x+OFFSET[0],y+OFFSET[1],432+OFFSET[2]))+')'for x,y in points)
        text=f'''// Original Greenhollow resident: {role}.
{{
const MEADOW_NAME "{name}"
const MEADOW_ROLE {role}
const MEADOW_HEAD {head}
const MEADOW_BODY {body}
const MEADOW_ROUTE "{route}"
const MEADOW_GREETING "{greeting}"
}}
#include daragoth_meadow/villager_base
'''
        additions['daragoth_meadow/'+role+'.script']=text.encode('ascii')
    for name,value in additions.items():
        if name in known and known[name]!=value:raise ValueError('Village script conflicts with base: '+name)
    combined=records+[(k,v)for k,v in sorted(additions.items())if k not in known]
    start=12+264*len(combined);directory=bytearray();payload=bytearray()
    for name,data in combined:
        directory.extend(struct.pack('<256sii',name.encode('ascii'),start+len(payload),len(data)));payload.extend(data)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_bytes(struct.pack('<4sii',b'PACK',12,len(combined))+directory+payload)
    actual=dict(helper.read_library(out))
    if not all(actual[k]==v for k,v in records):raise ValueError('Base content changed')
    report={'every_base_entry_preserved':True,'base_entries':len(records),'entries':len(combined),
        'base_sha256':hashlib.sha256(base.read_bytes()).hexdigest(),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),
        'crc32':zlib.crc32(out.read_bytes())&0xffffffff,'original_added_scripts':sorted(additions)}
    out.with_name('meadow-script-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();build(a.base,a.out)
