"""Verify the horse's runtime orientation, saddle and animation contracts."""
from pathlib import Path
import json
import math
import struct

here=Path(__file__).resolve().parent
data=(here/'export/plains_horse.mdl').read_bytes()
assert data[:4]==b'IDST' and struct.unpack_from('<i',data,4)[0]==10
assert struct.unpack_from('<i',data,72)[0]==len(data)
bone_count,bone_base=struct.unpack_from('<2i',data,140)
heads=[]
names=[]
for i in range(bone_count):
    start=bone_base+i*112
    name=data[start:start+32].split(b'\0')[0].decode('ascii')
    parent=struct.unpack_from('<i',data,start+32)[0]
    value=struct.unpack_from('<6f',data,start+64)
    assert all(abs(v)<.00001 for v in value[3:]), 'Unexpected bind rotation'
    heads.append(tuple(value[j]+(heads[parent][j] if parent>=0 else 0) for j in range(3)))
    names.append(name)
# Forward neck/head skeleton proves the compiled model kept +X orientation.
assert heads[names.index('head')][0]>heads[names.index('neck')][0]>0
sequence_count,sequence_base=struct.unpack_from('<2i',data,164)
assert sequence_count==3
sequences=[]
for i,(expected,frames,fps) in enumerate([('idle',41,20),('walk',25,24),('gallop',21,30)]):
    start=sequence_base+i*176
    label=data[start:start+32].split(b'\0')[0].decode('ascii')
    actual_fps,flags=struct.unpack_from('<fi',data,start+32)
    actual_frames=struct.unpack_from('<i',data,start+56)[0]
    assert (label,actual_frames,actual_fps)==(expected,frames,float(fps))
    assert flags&1, 'Sequence must loop'
    sequences.append({'index':i,'name':label,'frames':actual_frames,'fps':actual_fps,'loop':True})
attachments,attachment_base=struct.unpack_from('<2i',data,212)
assert attachments==1
attachment_bone=struct.unpack_from('<i',data,attachment_base+36)[0]
local=struct.unpack_from('<3f',data,attachment_base+40)
world=tuple(heads[attachment_bone][j]+local[j] for j in range(3))
assert all(abs(a-b)<.0001 for a,b in zip(world,(-1.8,0,64.6))), world
texture_count,texture_base=struct.unpack_from('<2i',data,180)
assert texture_count==1
width,height,pixel_base=struct.unpack_from('<3i',data,texture_base+68)
assert (width,height)==(512,512)
bmp=(here/'export/horse_atlas.bmp').read_bytes()
original_palette=bytes(component for i in range(256) for component in bmp[54+i*4:57+i*4][::-1])
compiled_palette=data[pixel_base+width*height:pixel_base+width*height+768]
assert compiled_palette==original_palette, 'Compiled palette changed the authored colors'
result={'contract':'passed','forward_axis':'+X','saddle_attachment_0':world,'sequences':sequences,
        'original_texture_palette':'preserved'}
(here/'horse-runtime-contract.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
