"""Package authored PNGs as lossless TGA replacements understood by Xash3D.

This is format conversion only: no resizing, filtering, atlas rearrangement,
normal-map synthesis or modification of model meshes/rigs.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from PIL import Image

BINDINGS = [
    ('models/monsters/Orc.mdl', 'Orcface.bmp', 'orcface-hd-v1.png'),
    ('models/human/male1/male1.mdl', 'BODY.bmp', 'player-body-hd-v1.png'),
    ('models/human/reference.mdl', 'body.bmp', 'reference-body-hd-v1.png'),
    ('models/npc/guard1.mdl', 'leatherarmor.bmp', 'guard-armor-hd-v1.png'),
]

def stage(game: Path):
    records=[]
    for model, texture, art in BINDINGS:
        blob=(game/model).read_bytes()
        if blob[:4]!=b'IDST' or struct.unpack_from('<i',blob,4)[0]!=10:
            raise ValueError(f'Unsupported model: {model}')
        count,table=struct.unpack_from('<ii',blob,180)
        names=[blob[table+i*80:table+i*80+64].split(b'\0')[0].decode('latin1') for i in range(count)]
        index=names.index(texture)
        flags,w,h=struct.unpack_from('<iii',blob,table+index*80+64)
        if flags & (0x40 | 0x100):
            raise ValueError('Masked/remapped skins need separate alpha/palette handling')
        source=Path(__file__).parent/'art'/art
        target=game/'materials'/Path(model).with_suffix('')/(Path(texture).stem+'.tga')
        target.parent.mkdir(parents=True,exist_ok=True)
        with Image.open(source) as image:
            if abs(image.width/image.height-w/h) > 0.015:
                raise ValueError(f'Atlas aspect ratio differs: {source}')
            image.save(target,format='TGA')
            dimensions=image.size
        records.append(dict(model=model,texture=texture,original_dimensions=[w,h],
            replacement=str(target.relative_to(game)).replace('\\','/'),dimensions=dimensions,
            source=art,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
            model_sha256=hashlib.sha256(blob).hexdigest()))
    manifest=game/'materials'/'msr-hd-manifest.json'
    manifest.write_text(json.dumps({'version':1,'bindings':records},indent=2)+'\n')
    print(f'Staged and validated {len(records)} HD model materials into {game}')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('game',type=Path)
    stage(parser.parse_args().game)
