"""Export the existing Edana apple tree into an isolated GoldSrc studio prop.

Only this exporter is suitable for source control. Its extracted texture pixels,
SMDs, previews and MDL inherit unverified upstream licensing and must remain in
the private lab. The BSP is read-only. No map, game runtime or harvest logic is
modified. Requires the existing pxstudiomdl executable; Blender is optional.
"""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import math
import os
import struct
import subprocess
import sys
import zlib

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
PRIVATE=REPO.parent/'daragoth-development/meadow-apple-tree'
ANCHOR=(-2176.,2702.,0.)
MODEL_NAME='models/plains/edana_apple_tree.mdl'
TEXTURES={'x_tree':'edana_trunk.bmp','{tree002':'edana_canopy_002.bmp'}
SELECTION=((151,'func_button','appledrop'),(152,'func_illusionary',None))


def sha(data):return hashlib.sha256(data).hexdigest()
def sub(a,b):return tuple(a[i]-b[i] for i in range(3))
def dot(a,b):return sum(a[i]*b[i] for i in range(3))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def bounds(points):return [[min(p[i] for p in points) for i in range(3)],
                          [max(p[i] for p in points) for i in range(3)]]


def quantized_point(point):
    # pxstudiomdl LookupVertex truncates float32 coordinates to 0.001 units.
    def f32(value):return struct.unpack('<f',struct.pack('<f',value))[0]
    return tuple(f32(math.trunc(f32(f32(value)*1000))/1000) for value in point)


def decode_texture(texture):
    raw=texture.raw
    if raw is None or texture.external:raise ValueError('Embedded texture required: '+texture.name)
    width,height,*offsets=struct.unpack_from('<II4I',raw,16)
    palette_at=offsets[3]+(width//8)*(height//8)
    if not width or not height or palette_at+2+768>len(raw):
        raise ValueError('Invalid miptex: '+texture.name)
    if struct.unpack_from('<H',raw,palette_at)[0]!=256:raise ValueError('256-color palette required')
    pixels=raw[offsets[0]:offsets[0]+width*height]
    palette=raw[palette_at+2:palette_at+2+768]
    if len(pixels)!=width*height:raise ValueError('Truncated miptex pixels')
    return {'name':texture.name,'width':width,'height':height,'pixels':pixels,'palette':palette,
            'masked':texture.name.startswith('{'),'miptex_sha256':sha(raw)}


def write_bmp(path,texture):
    width,height=texture['width'],texture['height'];stride=(width+3)&~3
    palette=bytes(channel for i in range(256)
                  for channel in (*texture['palette'][3*i:3*i+3][::-1],0))
    pixels=b''.join(texture['pixels'][y*width:(y+1)*width]+b'\0'*(stride-width)
                    for y in range(height-1,-1,-1))
    offset=14+40+1024
    header=struct.pack('<2sIHHI',b'BM',offset+len(pixels),0,0,offset)
    info=struct.pack('<IiiHHIIiiII',40,width,height,1,8,0,len(pixels),2835,2835,256,256)
    path.write_bytes(header+info+palette+pixels)


def write_rgba_png(path,texture):
    width,height=texture['width'],texture['height'];palette=texture['palette']
    pixels=texture['pixels'];rows=[]
    for y in range(height):
        rows.append(b'\0'+bytes(channel for index in pixels[y*width:(y+1)*width]
                     for channel in (*palette[index*3:index*3+3],
                                     0 if texture['masked'] and index==255 else 255)))
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>2I5B',width,height,8,6,0,0,0))+
                     chunk(b'IDAT',zlib.compress(b''.join(rows),9))+chunk(b'IEND',b''))


def extract(bsp):
    textures={};triangles=[];models=[];skipped=[];degenerate=0;orientation_min=1.
    quantization_slivers=[];unrelated_canopy=[]
    for index,classname,targetname in SELECTION:
        entities=[entity for entity in bsp.entities if entity.get('model')=='*'+str(index)]
        if len(entities)!=1 or entities[0].classname!=classname or (
                targetname is not None and entities[0].get('targetname')!=targetname):
            raise ValueError('Source Edana tree entity changed: *'+str(index))
        model=bsp.models[index]
        if any(abs(v)>1e-6 for v in model.origin):raise ValueError('Expected world-space brush vertices')
        entity_origin=entities[0].get('origin')
        if entity_origin and any(abs(float(v))>1e-6 for v in entity_origin.split()):
            raise ValueError('Unexpected brush entity origin')
        if entities[0].get('angles','0 0 0')!='0 0 0':raise ValueError('Unexpected source tree rotation')
        counts=collections.Counter();before=len(triangles)
        for face_index in range(model.firstface,model.firstface+model.numfaces):
            face=bsp.faces[face_index];info=bsp.texinfo[face.texinfo]
            texture=decode_texture(bsp.textures[info.miptex]);counts[texture['name']]+=1
            if texture['masked'] and all(index==255 for index in texture['pixels']):
                skipped.append({'model':index,'face':face_index,'texture':texture['name']})
                continue
            if index==152 and texture['name']=='{tree62a':
                # This brush entity groups two separate trees. The tree62a
                # crown is ~337 units north of appledrop *151 and has another
                # source trunk. Export only the tree002 crown at our anchor.
                face_points=[bsp.vertexes[bsp.edges[abs(edge)][0 if edge>=0 else 1]]
                             for edge in bsp.surfedges[face.firstedge:face.firstedge+face.numedges]]
                extent=bounds(face_points)
                if extent[0][1]<2900:raise ValueError('Unrelated canopy selection changed')
                unrelated_canopy.append({'model':index,'face':face_index,'texture':texture['name'],
                                         'bsp_bounds':extent})
                continue
            if texture['name'] not in TEXTURES:raise ValueError('Unexpected tree texture: '+texture['name'])
            textures[texture['name']]=texture
            polygon=[]
            for edge_index in bsp.surfedges[face.firstedge:face.firstedge+face.numedges]:
                edge=bsp.edges[abs(edge_index)]
                point=bsp.vertexes[edge[0] if edge_index>=0 else edge[1]]
                if not polygon or point!=polygon[-1]:polygon.append(point)
            if len(polygon)>1 and polygon[0]==polygon[-1]:polygon.pop()
            normal=tuple(v*(-1 if face.side else 1) for v in bsp.planes[face.planenum].normal)
            normal_length=math.sqrt(dot(normal,normal))
            normal=tuple(v/normal_length for v in normal)
            for i in range(1,len(polygon)-1):
                points=[polygon[0],polygon[i],polygon[i+1]]
                geometric=cross(sub(points[1],points[0]),sub(points[2],points[0]))
                area2=math.sqrt(dot(geometric,geometric))
                if area2<1e-7 or abs(dot(geometric,normal))<1e-7:
                    # BSP split polygons can contain collinear fan corners.
                    # Float-rounded off-plane coordinates make their 3D cross
                    # product nonzero even though the source face area is zero.
                    degenerate+=1;continue
                if dot(geometric,normal)<0:points[1],points[2]=points[2],points[1]
                geometric=cross(sub(points[1],points[0]),sub(points[2],points[0]))
                alignment=dot(geometric,normal)/area2
                orientation_min=min(orientation_min,alignment)
                if alignment<.99999:raise ValueError('Face normal disagrees with BSP polygon')
                vertices=[]
                for point in points:
                    s=dot(info.vecs[0],point)+info.vecs[0][3]
                    t=dot(info.vecs[1],point)+info.vecs[1][3]
                    # BSP T starts at the top; SMD V starts at the bottom.
                    vertices.append({'point':sub(point,ANCHOR),'normal':normal,
                                     'uv':(s/texture['width'],1-t/texture['height'])})
                native_points=[quantized_point(v['point']) for v in vertices]
                native_cross=cross(sub(native_points[1],native_points[0]),sub(native_points[2],native_points[0]))
                if dot(native_cross,normal)<=1e-7:
                    # One near-collinear trunk-cap fan sliver reverses under
                    # the compiler's documented 0.001-unit vertex truncation.
                    quantization_slivers.append({'model':index,'face':face_index,
                                                 'source_area':area2/2})
                    continue
                triangles.append({'texture':TEXTURES[texture['name']],
                                  'source_face':face_index,'source_model':index,'vertices':vertices})
        models.append({'index':index,'entity':entities[0].pairs,'bsp_bounds':[model.mins,model.maxs],
                       'source_faces':model.numfaces,'source_texture_faces':dict(counts),
                       'visible_triangles':len(triangles)-before})
    if set(textures)!=set(TEXTURES):raise ValueError('Source tree materials changed')
    if len(triangles)*3>16384:raise ValueError('Conservative renderer triangle-list budget exceeded')
    return triangles,textures,{'models':models,'skipped_fully_transparent_faces':skipped,
                               'skipped_degenerate_triangles':degenerate,
                               'skipped_native_quantization_slivers':quantization_slivers,
                               'excluded_unrelated_canopy_faces':unrelated_canopy,
                               'minimum_smd_normal_alignment':orientation_min}


def restore_native_uvs(path,triangles,textures):
    """Undo this compiler's 0..1 clamp using standard v10 integer texels.

    Match each command corner by its source texture, XYZ and plane normal.
    Refuse ambiguous mappings; do not introduce the compiler's floating UV
    extension. Whole-image repeats remain the BSP's original affine mapping.
    """
    data=bytearray(path.read_bytes());before=sha(data)
    def unpack(fmt,at):return struct.unpack_from(fmt,data,at)
    def name(at,size):return data[at:at+size].split(b'\0',1)[0].decode('ascii')
    def key(label,p,n):return (label,tuple(round(v,3) for v in p),tuple(round(v,4) for v in n))
    sources={};dimensions={TEXTURES[k]:(v['width'],v['height']) for k,v in textures.items()}
    for triangle in triangles:
        label=triangle['texture'];width,height=dimensions[label]
        for vertex in triangle['vertices']:
            u,v=vertex['uv']
            sources.setdefault(key(label,quantized_point(vertex['point']),vertex['normal']),[]).append((u*width,(1-v)*height))
    texture_count,texture_at=unpack('<2i',180)
    names=[name(texture_at+i*80,64) for i in range(texture_count)]
    refs,families,skin_at=unpack('<3i',192);skin=unpack('<'+str(refs)+'h',skin_at)
    body_count,body_at=unpack('<2i',204);changed=0;commands=0
    for body in range(body_count):
        model_count,_,model_at=unpack('<3i',body_at+body*76+64)
        for model in range(model_count):
            at=model_at+model*112
            meshes,mesh_at,verts,_,vert_at,normals,_,normal_at=unpack('<8i',at+72)
            for mesh in range(meshes):
                _,cursor,reference=unpack('<3i',mesh_at+mesh*20)
                label=names[skin[reference]];width,height=dimensions[label]
                while True:
                    count=unpack('<h',cursor)[0];cursor+=2
                    if not count:break
                    for i in range(abs(count)):
                        entry=cursor+i*8;vi,ni,old_s,old_t=unpack('<4h',entry)
                        p=unpack('<3f',vert_at+vi*12);n=unpack('<3f',normal_at+ni*12)
                        values=sources.get(key(label,p,n))
                        if not values:raise ValueError(f'Native UV corner has no source position/normal match: {label} {p} {n}')
                        s,t=values[0]
                        for other_s,other_t in values[1:]:
                            if max(abs((other_s-s+width/2)%width-width/2),
                                   abs((other_t-t+height/2)%height-height/2))>.001:
                                raise ValueError('Ambiguous source UV mapping at native corner')
                        s,t=round(s),round(t)
                        if not -32768<=s<=32767 or not -32768<=t<=32767:
                            raise ValueError('Source texture coordinates exceed native int16 range')
                        if (s,t)!=(old_s,old_t):changed+=1
                        struct.pack_into('<2h',data,entry+4,s,t);commands+=1
                    cursor+=abs(count)*8
    path.write_bytes(data)
    return {'compiler_clamped_sha256':before,'restored_command_corners':commands,
            'changed_command_corners':changed,'encoding':'standard signed int16 texels; no UV extension'}


def studio_audit(path,triangles,textures,expected_bounds):
    data=path.read_bytes()
    def unpack(fmt,offset):
        if offset<0 or offset+struct.calcsize(fmt)>len(data):raise ValueError('MDL field outside file')
        return struct.unpack_from(fmt,data,offset)
    def name(offset,size=32):return data[offset:offset+size].split(b'\0',1)[0].decode('ascii')
    if data[:4]!=b'IDST' or unpack('<i',4)[0]!=10 or unpack('<i',72)[0]!=len(data):
        raise ValueError('Invalid native studio v10 model')
    if unpack('<I',136)[0]&((1<<31)|(1<<29)):raise ValueError('Unexpected native extension')
    bone_count,bone_at=unpack('<2i',140)
    if bone_count!=1 or name(bone_at)!='root' or unpack('<i',bone_at+32)[0]!=-1:
        raise ValueError('Expected one root bone')
    if max(abs(v) for v in unpack('<6f',bone_at+64))>1e-5:raise ValueError('Root transform changed')
    seq_count,seq_at=unpack('<2i',164)
    if seq_count!=1 or name(seq_at)!='idle' or not unpack('<I',seq_at+36)[0]&1:
        raise ValueError('Expected one looping idle sequence')
    if unpack('<i',172)[0]!=1 or unpack('<i',seq_at+156)[0]!=0:raise ValueError('External animation group')
    frame_count=unpack('<i',seq_at+56)[0]
    blends,anim_at=unpack('<2i',seq_at+120)
    if blends!=1 or frame_count<2:raise ValueError('Invalid idle sequence')
    for frame in range(frame_count):
        for channel,offset in enumerate(unpack('<6H',anim_at)):
            sample=0
            if offset:
                cursor=anim_at+offset;remaining=frame
                while True:
                    valid,total=unpack('<2B',cursor)
                    if not 0<valid<=total:raise ValueError('Invalid animation RLE')
                    if remaining<total:
                        sample=unpack('<h',cursor+2*(min(remaining,valid-1)+1))[0];break
                    remaining-=total;cursor+=2*(valid+1)
            if sample:raise ValueError('Static tree idle unexpectedly animates')
    texture_count,texture_at=unpack('<2i',180);texture_report=[];source_by_file={TEXTURES[k]:v for k,v in textures.items()}
    if texture_count!=len(textures):raise ValueError('Unexpected compiled texture count')
    for i in range(texture_count):
        at=texture_at+i*80;label=name(at,64);source=source_by_file[label]
        flags,width,height,pixels_at=unpack('<I3i',at+64)
        if (width,height)!=(source['width'],source['height']):raise ValueError('Texture dimensions changed')
        if bool(flags&64)!=source['masked'] or flags&(4|32|(1<<31)):
            raise ValueError('Compiled texture mode changed')
        pixels=data[pixels_at:pixels_at+width*height]
        palette=data[pixels_at+width*height:pixels_at+width*height+768]
        if pixels!=source['pixels'] or palette!=source['palette']:raise ValueError('Indexed texture data changed: '+label)
        texture_report.append({'file':label,'width':width,'height':height,'masked':bool(flags&64),
                               'pixels_exact':True,'palette_exact':True,'index255_pixels':pixels.count(255)})
    skinrefs,families,skin_at=unpack('<3i',192)
    if families!=1 or skinrefs!=texture_count:raise ValueError('Unexpected skin families')
    skin=unpack('<'+str(skinrefs)+'h',skin_at)
    body_count,body_at=unpack('<2i',204)
    if body_count!=1:raise ValueError('Expected one visible tree body')
    models,body_base,model_at=unpack('<3i',body_at+64)
    if models!=1 or body_base!=1:raise ValueError('Unexpected body selection')
    mesh_count,mesh_at,vertex_count,vertex_bone_at,vertex_at,normal_count,normal_bone_at,normal_at=unpack('<8i',model_at+72)
    if not 0<vertex_count<=16384 or not 0<normal_count<=16384:raise ValueError('Native array budget exceeded')
    if any(data[vertex_bone_at:vertex_bone_at+vertex_count]) or any(data[normal_bone_at:normal_bone_at+normal_count]):
        raise ValueError('Non-root skinning')
    vertices=[unpack('<3f',vertex_at+i*12) for i in range(vertex_count)]
    normals=[unpack('<3f',normal_at+i*12) for i in range(normal_count)]
    actual_bounds=bounds(vertices)
    bound_error=max(abs(a-b) for x,y in zip(actual_bounds,expected_bounds) for a,b in zip(x,y))
    if bound_error>.001:raise ValueError('Compiled bounds differ from source geometry')
    header_bounds=[unpack('<3f',112),unpack('<3f',124)]
    if max(abs(a-b) for x,y in zip(header_bounds,expected_bounds) for a,b in zip(x,y))>.001:
        raise ValueError('Compiled culling box differs from source')
    total_triangles=0;submitted=0;normal_alignment_max=-1.;uv_error=0.;source_points={}
    native_geometry=collections.Counter()
    def triangle_key(label,points):return (label,tuple(sorted(tuple(round(v,3) for v in p) for p in points)))
    source_geometry=collections.Counter(triangle_key(t['texture'],[quantized_point(v['point']) for v in t['vertices']]) for t in triangles)
    for triangle in triangles:
        for vertex in triangle['vertices']:
            key=(triangle['texture'],tuple(round(v,3) for v in quantized_point(vertex['point'])))
            source_points.setdefault(key,[]).append(vertex['uv'])
    for i in range(mesh_count):
        count,cursor,skinref=unpack('<3i',mesh_at+i*20)
        if not 0<=skinref<skinrefs:raise ValueError('Invalid mesh texture reference')
        tex_index=skin[skinref];compiled_texture=texture_report[tex_index]
        label=compiled_texture['file'];source=source_by_file[label]
        found=0
        while True:
            command=unpack('<h',cursor)[0];cursor+=2
            if not command:break
            length=abs(command)
            if length<3:raise ValueError('Invalid studio command')
            submitted+=length;items=[]
            for j in range(length):
                vertex,normal,s,t=unpack('<4h',cursor+j*8)
                if not 0<=vertex<vertex_count or not 0<=normal<normal_count:raise ValueError('Studio command index outside arrays')
                p=vertices[vertex];key=(label,tuple(round(v,3) for v in p))
                candidates=source_points.get(key)
                if not candidates:raise ValueError('Compiled position has no source vertex')
                # UVs are integer texels in native v10. Equivalent repetitions
                # differ by whole image widths/heights and are visually equal.
                error=min(max(abs((s-u*source['width']+source['width']/2)%source['width']-source['width']/2),
                              abs((t-(1-v)*source['height']+source['height']/2)%source['height']-source['height']/2))
                          for u,v in candidates)
                uv_error=max(uv_error,error)
                if error>.501:raise ValueError(f'Native UV differs beyond texel quantization: {label} {p} {s,t} {candidates} error={error}')
                items.append((p,normals[normal]))
            cursor+=length*8
            for j in range(2,length):
                indices=(0,j-1,j) if command<0 else ((j-2,j-1,j) if j%2==0 else (j-1,j-2,j))
                a,b,c=(items[k] for k in indices)
                native_geometry[triangle_key(label,(a[0],b[0],c[0]))]+=1
                geometric=cross(sub(b[0],a[0]),sub(c[0],a[0]));area=math.sqrt(dot(geometric,geometric))
                if area<1e-7:raise ValueError('Compiled degenerate triangle')
                alignment=dot(geometric,a[1])/area
                normal_alignment_max=max(normal_alignment_max,alignment)
                # pxstudiomdl reverses outward CCW SMD triangles for GoldSrc.
                if alignment>-.9999:raise ValueError(f'Native triangle winding changed: {label} alignment={alignment} {a,b,c}')
            found+=length-2
        if found!=count:raise ValueError('Studio command triangle count mismatch')
        total_triangles+=found
    if total_triangles!=len(triangles) or submitted>16384:raise ValueError('Native triangle budget/count mismatch')
    if native_geometry!=source_geometry:raise ValueError('Native triangle geometry differs from source')
    return {'pass':True,'version':10,'bones':bone_count,'bodyparts':body_count,'meshes':mesh_count,
            'vertices':vertex_count,'normals':normal_count,'triangles':total_triangles,
            'submitted_vertices':submitted,'bounds':actual_bounds,'maximum_bound_error':bound_error,
            'maximum_native_normal_alignment':normal_alignment_max,'maximum_uv_quantization_error_texels':uv_error,
            'idle_frames':frame_count,'idle_fps':unpack('<f',seq_at+32)[0],
            'idle_rle_static':True,'native_triangles_match_source':True,
            'textures':texture_report,'bytes':len(data),'sha256':sha(data)}


PREVIEW_SCRIPT=r'''
import bpy,json,math,sys
from pathlib import Path
from mathutils import Vector
directory=Path(sys.argv[sys.argv.index('--')+1])
geometry=json.loads((directory/'geometry.json').read_text())
bpy.ops.wm.read_factory_settings(use_empty=True)
materials={}
for texture in geometry['textures']:
    material=bpy.data.materials.new(texture['file']);material.use_nodes=True
    shader=material.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Roughness'].default_value=.85
    image=material.node_tree.nodes.new('ShaderNodeTexImage')
    image.image=bpy.data.images.load(str(directory/texture['preview_png']))
    image.interpolation='Closest'
    material.node_tree.links.new(image.outputs['Color'],shader.inputs['Base Color'])
    if texture['masked']:
        material.node_tree.links.new(image.outputs['Alpha'],shader.inputs['Alpha'])
        material.surface_render_method='DITHERED'
    materials[texture['file']]=material
for label,material in materials.items():
    triangles=[t for t in geometry['triangles'] if t['texture']==label]
    vertices=[v['point'] for t in triangles for v in t['vertices']]
    mesh=bpy.data.meshes.new(label);mesh.from_pydata(vertices,[],[(i,i+1,i+2) for i in range(0,len(vertices),3)])
    mesh.materials.append(material);uv=mesh.uv_layers.new()
    for loop,vertex in zip(mesh.loops,[v for t in triangles for v in t['vertices']]):uv.data[loop.index].uv=vertex['uv']
    obj=bpy.data.objects.new(label,mesh);bpy.context.collection.objects.link(obj)
bpy.ops.mesh.primitive_plane_add(size=1800,location=(0,0,-.1))
ground=bpy.context.object;ground.name='PreviewGround';groundmat=bpy.data.materials.new('Grass ground')
groundmat.diffuse_color=(.12,.19,.035,1);ground.data.materials.append(groundmat)
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE_NEXT'
scene.render.resolution_x=1000;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.world=bpy.data.worlds.new('World');scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.45,.5,.55,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.6
sun_data=bpy.data.lights.new('Sun','SUN');sun_data.energy=3
sun=bpy.data.objects.new('Sun',sun_data);scene.collection.objects.link(sun);sun.rotation_euler=(.5,-.6,-.5)
scene.view_settings.view_transform='Standard'
camera_data=bpy.data.cameras.new('Camera');camera=bpy.data.objects.new('Camera',camera_data)
scene.collection.objects.link(camera);scene.camera=camera;camera_data.type='ORTHO';camera_data.ortho_scale=620
camera_data.clip_end=10000
camera_data.ortho_scale=350
target=Vector((0,1,128))
for name,location in [('front',(-500,-600,340)),('rear',(500,600,340))]:
    camera.location=location;camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(directory/('preview-'+name+'.png'));bpy.ops.render.render(write_still=True)
'''


def build(source,out,compiler,blender=None):
    source=source.resolve();out=out.resolve();compiler=compiler.resolve()
    if not out.is_relative_to(PRIVATE.resolve()):raise ValueError('Output must remain in private meadow-apple-tree lab')
    out.mkdir(parents=True,exist_ok=True)
    # Import the existing BSP reader without writing __pycache__ beside it.
    previous=sys.dont_write_bytecode;sys.dont_write_bytecode=True
    sys.path.insert(0,str(REPO/'Packaging-Work/BigWorld/tools'))
    try:from bsp30 import BSP
    finally:sys.dont_write_bytecode=previous
    source_sha=sha(source.read_bytes());bsp=BSP.load(source)
    triangles,textures,source_report=extract(bsp)
    all_points=[v['point'] for t in triangles for v in t['vertices']];extent=bounds(all_points)
    trunk_points=[v['point'] for t in triangles if t['source_model']==151 for v in t['vertices']]
    radius=max(math.hypot(p[0],p[1]) for p in all_points)
    texture_report=[]
    for key,texture in textures.items():
        filename=TEXTURES[key];preview=Path(filename).with_suffix('.png').name
        write_bmp(out/filename,texture);write_rgba_png(out/preview,texture)
        texture_report.append({k:v for k,v in texture.items() if k not in ('pixels','palette')})
        texture_report[-1].update(file=filename,preview_png=preview,pixels_sha256=sha(texture['pixels']),
                                 palette_sha256=sha(texture['palette']),index255_pixels=texture['pixels'].count(255),
                                 bmp_sha256=sha((out/filename).read_bytes()))
    nodes='version 1\nnodes\n0 "root" -1\nend\nskeleton\ntime 0\n0 0 0 0 0 0 0\n'
    with (out/'edana_apple_tree_reference.smd').open('w',encoding='ascii',newline='\n') as f:
        f.write(nodes+'end\ntriangles\n')
        for triangle in triangles:
            f.write(triangle['texture']+'\n')
            for vertex in triangle['vertices']:
                f.write('0 '+' '.join(f'{value:.9f}' for value in (*vertex['point'],*vertex['normal'],*vertex['uv']))+'\n')
        f.write('end\n')
    (out/'edana_apple_tree_idle.smd').write_text(nodes+'time 1\n0 0 0 0 0 0 0\nend\n',encoding='ascii')
    bbox=' '.join(f'{v:.9f}' for side in extent for v in side)
    qc=f'''// Private upstream-derived asset. Licensing unverified; do not publish.
$modelname "{MODEL_NAME}"
$cd "."
$cdtexture "."
$scale 1
$gamma 1.8
$origin 0 0 0 -90
$body "tree" "edana_apple_tree_reference"
$sequence "idle" "edana_apple_tree_idle" fps 1 loop
$bbox {bbox}
$cbox {bbox}
'''
    qc+=''.join(f'$texrendermode "{TEXTURES[name]}" masked\n' for name,texture in textures.items() if texture['masked'])
    (out/'edana_apple_tree.qc').write_text(qc,encoding='ascii')
    model=out/MODEL_NAME;model.parent.mkdir(parents=True,exist_ok=True)
    # Preserve separate BSP plane normals instead of the default 2-degree merge.
    command=[str(compiler),'-a','0','edana_apple_tree.qc']
    result=subprocess.run(command,cwd=out,capture_output=True,text=True,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    (out/'compile.log').write_text(result.stdout+result.stderr,encoding='utf8')
    if result.returncode or not model.is_file():raise RuntimeError('Native compiler failed; see private compile.log')
    restored=restore_native_uvs(model,triangles,textures)
    compiled=studio_audit(model,triangles,textures,extent)
    geometry={'triangles':triangles,'textures':texture_report,'bounds':extent,'anchor':ANCHOR}
    (out/'geometry.json').write_text(json.dumps(geometry,separators=(',',':'))+'\n',encoding='utf8')
    previews=[]
    if blender:
        (out/'preview.py').write_text(PREVIEW_SCRIPT,encoding='utf8')
        result=subprocess.run([str(blender.resolve()),'--background','--disable-autoexec','--python-exit-code','1',
                               '--python',str(out/'preview.py'),'--',str(out)],cwd=out,capture_output=True,text=True,
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        (out/'preview.log').write_text(result.stdout+result.stderr,encoding='utf8')
        if result.returncode:raise RuntimeError('Private Blender preview failed; native model is preserved')
        previews=[name for name in ('preview-front.png','preview-rear.png') if (out/name).is_file()]
    if sha(source.read_bytes())!=source_sha:raise ValueError('Source BSP changed during export')
    report={'source_bsp':str(source),'source_bsp_sha256':source_sha,'source_read_only_verified':True,
            'anchor':ANCHOR,'model_name':MODEL_NAME,'model_file':str(model),'geometry_bounds':extent,
            'horizontal_radius':radius,'source_trunk_bounds':bounds(trunk_points),
            'source_trunk_radius':max(math.hypot(p[0],p[1]) for p in trunk_points),
            'source':source_report,'textures':texture_report,'native_uv_restore':restored,
            'compiled':compiled,'previews':previews,
            'licensing':'Upstream Edana geometry and texture licensing unverified. Derived pixels, SMD, MDL and previews remain private; no publication authorization.',
            'scope':'Decorative native model only; no apple props, harvest behavior, map placements or runtime installation.',
            'compiler':str(compiler),'compiler_sha256':sha(compiler.read_bytes()),'compiler_command':command,
            'script_sha256':sha(Path(__file__).read_bytes())}
    artifact_names=['edana_apple_tree_reference.smd','edana_apple_tree_idle.smd','edana_apple_tree.qc',
                    'compile.log','geometry.json',MODEL_NAME]
    artifact_names+=[name for texture in texture_report for name in (texture['file'],texture['preview_png'])]
    if blender:artifact_names+=['preview.py','preview.log',*previews]
    report['derived_files']={name:sha((out/name).read_bytes()) for name in sorted(artifact_names)}
    (out/'apple-tree-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'pass':True,'model_file':str(model),'source_bsp_sha256':source_sha,
                      'compiled':compiled,'previews':previews},indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=Path('C:/MSR/Portable-Package/game/msr/maps/edana.bsp'))
    p.add_argument('--out',type=Path,default=PRIVATE)
    p.add_argument('--compiler',type=Path,required=True)
    p.add_argument('--blender',type=Path)
    a=p.parse_args();build(a.source,a.out,a.compiler,a.blender)
