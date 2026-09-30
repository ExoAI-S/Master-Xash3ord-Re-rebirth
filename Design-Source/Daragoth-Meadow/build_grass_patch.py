"""Group 36 compact CC0 grass tufts into a slope-placeable studio prop.

Inputs are our Daragoth-Foliage export, not any original game mesh/bitmap.
The private output contains editable SMD/QC/BMP and a native GoldSrc MDL.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import random
import struct
import subprocess

ROOT=Path(__file__).resolve().parent


def build(source,out,compiler):
    out.mkdir(parents=True,exist_ok=True)
    lines=(source/'plains_grass_reference.smd').read_text().splitlines()
    start=lines.index('triangles')+1;body=lines[start:lines.index('end',start)]
    if len(body)%4:raise ValueError('Invalid original grass SMD triangles')
    # One crossed, two-sided spray is enough per tuft in a dense patch.
    # Retain the original card geometry/UVs but avoid drawing all six sprays.
    body=body[:32]
    if len(body)!=32:raise ValueError('Expected eight triangles for one crossed spray')
    rng=random.Random(403930);output=lines[:start];vertices=[]
    centers=[((x-2.5)*34+rng.uniform(-5,5),(y-2.5)*34+rng.uniform(-5,5))
        for y in range(6) for x in range(6)]
    for ox,oy in centers:
        angle=rng.random()*math.tau;scale=rng.uniform(.90,1.20);c=math.cos(angle);s=math.sin(angle)
        for j in range(0,len(body),4):
            output.append('meadow_grass_blades.bmp')
            for line in body[j+1:j+4]:
                values=line.split();x,y,z,nx,ny,nz,u,v=map(float,values[1:9])
                x-=10
                p=(ox+scale*1.4*(x*c-y*s),oy+scale*1.4*(x*s+y*c),z*scale)
                n=(nx*c-ny*s,nx*s+ny*c,nz);vertices.append(p)
                output.append('0 '+' '.join(f'{value:.6f}' for value in (*p,*n,u,v)))
    output.append('end')
    (out/'meadow_grass_patch_reference.smd').write_text('\n'.join(output)+'\n')
    (out/'meadow_grass_patch_idle.smd').write_text((source/'plains_grass_idle.smd').read_text())
    bitmap=bytearray((source/'plains_grass_blades.bmp').read_bytes())
    if bitmap[:2]!=b'BM' or struct.unpack_from('<H',bitmap,28)[0]!=8:raise ValueError('Expected original indexed BMP')
    palette_at=14+struct.unpack_from('<I',bitmap,14)[0]
    for i in range(160):
        rgb=(round(40+i*.50),round(65+i*.40),round(2+i*.03))
        bitmap[palette_at+4*i:palette_at+4*i+4]=bytes((*reversed(rgb),0))
    bitmap[palette_at+4*255:palette_at+4*255+4]=bytes((4,73,61,0))
    (out/'meadow_grass_blades.bmp').write_bytes(bitmap)
    lo=[min(p[k]for p in vertices)for k in range(3)];hi=[max(p[k]for p in vertices)for k in range(3)]
    bounds=' '.join(f'{v:.6f}'for v in (*lo,*hi))
    qc=f'''// 36 compact original CC0 tufts; masked, two-sided crossed cards.
$modelname "meadow_grass_patch.mdl"
$cd "."
$cdtexture "."
$scale 1
$gamma 1.8
$origin 0 0 0 -90
$body "prop" "meadow_grass_patch_reference"
$sequence "idle" "meadow_grass_patch_idle" fps 12 loop
$bbox {bounds}
$cbox {bounds}
$texrendermode "meadow_grass_blades.bmp" masked
// Scene-lit flatshade is set in the native v10 texture table below.
'''
    (out/'meadow_grass_patch.qc').write_text(qc)
    result=subprocess.run([str(compiler.resolve()),'meadow_grass_patch.qc'],cwd=out,capture_output=True,text=True)
    (out/'compile.log').write_text(result.stdout+result.stderr)
    if result.returncode or not(out/'meadow_grass_patch.mdl').exists():raise RuntimeError('Grass patch compiler failed; see compile.log')
    mdl=bytearray((out/'meadow_grass_patch.mdl').read_bytes())
    if mdl[:4]!=b'IDST' or struct.unpack_from('<i',mdl,4)[0]!=10:raise ValueError('Expected GoldSrc studio v10')
    texture_count,texture_offset,data_offset=struct.unpack_from('<3i',mdl,180)
    if texture_count!=1:raise ValueError('Grass patch must use one masked texture')
    flags,width,height,pixels_at=struct.unpack_from('<4i',mdl,texture_offset+64)
    if not flags&64 or 255 not in mdl[pixels_at:pixels_at+width*height]:raise ValueError('Masked grass alpha not preserved')
    # This compiler does not implement a QC flatshade keyword. The v10 flag
    # uses the scene's ambient + 0.8 * shade light, avoiding dark card backs;
    # it does not enable fullbright or bypass outdoor lighting.
    flags|=1
    if flags&4:raise ValueError('Grass must remain scene-lit')
    struct.pack_into('<i',mdl,texture_offset+64,flags)
    (out/'meadow_grass_patch.mdl').write_bytes(mdl)
    report={'asset_license':'CC0-1.0','source':'Original Daragoth-Foliage grass, grouped procedurally',
        'tufts':len(centers),'triangles':len(vertices)//3,'triangles_per_tuft':len(body)//4,'bounds':[lo,hi],
        'radius':max(math.hypot(p[0],p[1])for p in vertices),'texture_size':[width,height],
        'masked_alpha_preserved':True,'scene_lit_flatshade':bool(flags&1),'studio_version':10,'bytes':len(mdl),
        'sha256':hashlib.sha256(mdl).hexdigest()}
    (out/'grass-patch-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=ROOT/'SourceAssets')
    p.add_argument('--out',type=Path,required=True);p.add_argument('--compiler',type=Path,required=True)
    a=p.parse_args();build(a.source,a.out,a.compiler)
