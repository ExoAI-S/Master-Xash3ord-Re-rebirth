"""Validate renderer budgets, native masking, palette, and placement contracts."""
from pathlib import Path
import struct,json,hashlib

HERE=Path(__file__).resolve().parent
manifest=json.loads((HERE/'foliage-manifest.json').read_text())
def validate_renderer(path):
    """Check v10 mesh tables and triangle commands against the MSR GL arrays."""
    b=path.read_bytes()
    assert b[:4]==b'IDST' and struct.unpack_from('<i',b,4)[0]==10
    assert struct.unpack_from('<i',b,72)[0]==len(b)
    def integers(offset,count):
        assert 0<=offset<=len(b)-count*4
        return struct.unpack_from('<'+'i'*count,b,offset)
    bones=integers(140,1)[0]
    assert 1<=bones<=128
    body_count,body_base=integers(204,2)
    bodyparts=[]
    for i in range(body_count):
        start=body_base+76*i
        model_count,_,model_base=integers(start+64,3)
        body={'name':b[start:start+64].split(b'\0')[0].decode('ascii'),'models':[]}
        for j in range(model_count):
            m=model_base+112*j
            meshes,mesh_base,verts,vertex_bones,_,normals,_,_=integers(m+72,8)
            assert 0<=verts<=16384 and 0<=normals<=16384
            assert max(b[vertex_bones:vertex_bones+verts],default=0)<bones
            submitted=total_triangles=0
            for k in range(meshes):
                declared_triangles,commands,_,_,_=integers(mesh_base+20*k,5)
                actual_triangles=0
                while True:
                    assert commands+2<=len(b)
                    count=struct.unpack_from('<h',b,commands)[0]; commands+=2
                    if not count: break
                    count=abs(count)
                    assert 3<=count<=32767 and commands+count*8<=len(b)
                    for n in range(count):
                        vertex,normal=struct.unpack_from('<hh',b,commands+n*8)
                        assert 0<=vertex<verts and 0<=normal<normals
                    commands+=count*8; submitted+=count; actual_triangles+=count-2
                assert actual_triangles==declared_triangles
                total_triangles+=actual_triangles
            assert submitted<=16384 and total_triangles*3<=16384*6
            body['models'].append({'name':b[m:m+64].split(b'\0')[0].decode('ascii'),
                                  'vertices':verts,'normals':normals,'meshes':meshes,
                                  'triangles':total_triangles,'submitted_vertices':submitted})
        bodyparts.append(body)
    return {'path':str(path),'sha256':hashlib.sha256(b).hexdigest(),'version':10,'bytes':len(b),
            'bones':bones,'bodyparts':bodyparts}
results=[]
for model in manifest['models']:
    path=HERE/'export'/(model['name']+'.mdl')
    result=validate_renderer(path)
    b=path.read_bytes()
    seq_count,seq_base=struct.unpack_from('<2i',b,164)
    assert seq_count==1 and b[seq_base:seq_base+32].split(b'\0')[0]==b'idle'
    assert struct.unpack_from('<i',b,seq_base+36)[0]&1
    minz=struct.unpack_from('<f',b,112+8)[0]
    maxz=struct.unpack_from('<f',b,124+8)[0]
    assert abs(minz)<.001 and abs(maxz-model['height'])<.001, (minz,maxz)
    bones,bone_base=struct.unpack_from('<2i',b,140)
    assert all(abs(n)<.00001 for n in struct.unpack_from('<3f',b,bone_base+76)), 'Unexpected root rotation'
    texture_count,texture_base=struct.unpack_from('<2i',b,180)
    textures=[]
    for i in range(texture_count):
        start=texture_base+i*80
        name=b[start:start+64].split(b'\0')[0].decode('ascii')
        flags,width,height,pixel_base=struct.unpack_from('<4i',b,start+64)
        masked=any(word in name for word in ('leaves','needles','grass'))
        assert bool(flags&0x40)==masked, (name,flags)
        pixel_data=b[pixel_base:pixel_base+width*height]
        alpha_holes=pixel_data.count(255)
        if masked:
            assert .1*width*height<alpha_holes<.97*width*height, (name,alpha_holes)
        bmp=(HERE/'export'/name).read_bytes()
        original_palette=bytes(c for n in range(256) for c in bmp[54+n*4:57+n*4][::-1])
        actual_palette=b[pixel_base+width*height:pixel_base+width*height+768]
        assert actual_palette==original_palette, name+' palette changed'
        textures.append({'name':name,'flags':flags,'masked':masked,'width':width,'height':height,
                         'transparent_index':255 if masked else None,'alpha_holes':alpha_holes if masked else 0,
                         'palette_preserved':True})
    result['textures']=textures
    result['placement_bounds']=model['bounds']
    result['idle_sequence']=0
    results.append(result)
(HERE/'foliage-validation.json').write_text(json.dumps({'passed':True,'models':results},indent=2)+'\n')
for result in results:
    mesh=result['bodyparts'][0]['models'][0]
    print(Path(result['path']).name, result['bytes'],'bytes',mesh['triangles'],'tris',mesh['submitted_vertices'],'submitted verts',
          'masked textures',sum(t['masked'] for t in result['textures']))
