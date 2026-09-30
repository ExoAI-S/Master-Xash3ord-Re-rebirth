"""Original MSR horse asset; run with Blender 4.5 --background --python this_file.

All geometry, textures and animation are generated here without external assets.
Exports the GoldSrc SMD files directly (one rigid bone per mesh component), and
keeps the corresponding editable rig and preview scene in the .blend file.
"""
from pathlib import Path
import bpy
import math
import random
import struct
import json
from mathutils import Vector, Matrix

HERE = Path(__file__).resolve().parent
EXPORT = HERE / 'export'
EXPORT.mkdir(parents=True, exist_ok=True)
random.seed(20260929)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for collection in list(bpy.data.collections):
    if collection.name != 'Collection':
        bpy.data.collections.remove(collection)
scene = bpy.context.scene

# A 512px, 8-bit indexed atlas compatible with GoldSrc's studio texture format.
# Sixteen original swatches, each with sixteen subtle value variations.
BASE = [(135,66,35), (114,49,26), (154,81,43), (38,26,23),
        (36,30,28), (81,47,29), (107,72,41), (71,93,68),
        (175,147,74), (27,20,17), (219,209,183), (76,43,24),
        (151,87,46), (45,40,37), (142,49,38), (105,100,84)]
PALETTE=[]
for base in BASE:
    for shade in range(16):
        scale=.75 + shade*.033
        PALETTE.append(tuple(max(0,min(255,round(c*scale))) for c in base))
pixels=bytearray()
for y in range(512):
    for x in range(512):
        tile=(y//128)*4+x//128
        # Broad hide mottling and fine pores; leather has a directional grain.
        noise=(math.sin(x*.16+math.sin(y*.063)*2)+math.sin(y*.12+x*.035))*.8
        grain=random.random()*2-1
        shade=round(8+noise+grain)
        if tile in (3,4,9,13):
            shade=round(6+grain+math.sin(y*.37)*1.1)
        pixels.append(tile*16+max(0,min(15,shade)))
offset=14+40+256*4
with (EXPORT/'horse_atlas.bmp').open('wb') as f:
    f.write(struct.pack('<2sIHHI',b'BM',offset+len(pixels),0,0,offset))
    f.write(struct.pack('<IiiHHIIiiII',40,512,512,1,8,0,len(pixels),2835,2835,256,256))
    for r,g,b in PALETTE:
        f.write(bytes((b,g,r,0)))
    f.write(pixels)
atlas=bpy.data.images.load(str(EXPORT/'horse_atlas.bmp'),check_existing=False)
mat=bpy.data.materials.new('Original chestnut hide and leather atlas')
mat.use_nodes=True
bsdf=mat.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Roughness'].default_value=.72
tex=mat.node_tree.nodes.new('ShaderNodeTexImage')
tex.image=atlas
tex.interpolation='Linear'
mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])

BONES=[]
def bone(name,parent,head,tail):
    BONES.append({'name':name,'parent':parent,'head':Vector(head),'tail':Vector(tail)})
    return len(BONES)-1
root=bone('root',-1,(0,0,0),(0,0,10))
body=bone('body',root,(0,0,65),(0,0,76))
neck=bone('neck',body,(27,0,74),(48,0,95))
head=bone('head',neck,(48,0,96),(77,0,85))
tail=bone('tail',body,(-39,0,72),(-52,0,53))
tail_tip=bone('tail_tip',tail,(-52,0,53),(-58,0,27))
LEGS={}
for side,y in [('L',-13),('R',13)]:
    for front in (True,False):
        prefix=('front_' if front else 'hind_')+side
        points=([(24,y,62),(23,y,40),(25,y,25),(26,y,7),(30,y,2)] if front else
                [(-29,y,64),(-17,y,43),(-31,y,25),(-28,y,7),(-24,y,2)])
        chain=[]
        parent=body
        for i in range(4):
            idx=bone(prefix+('_upper','_lower','_cannon','_hoof')[i],parent,points[i],points[i+1])
            chain.append(idx)
            parent=idx
        LEGS[prefix]=(chain,points)

OBJECTS=[]
def mesh(name,verts,faces,tile,bone_id,smooth=True):
    data=bpy.data.meshes.new(name)
    data.from_pydata(verts,[],faces)
    data.materials.append(mat)
    data.update()
    obj=bpy.data.objects.new(name,data)
    scene.collection.objects.link(obj)
    OBJECTS.append((obj,bone_id))
    uv=data.uv_layers.new(name='Original atlas')
    # Projection chosen per normal; each piece stays inside its material tile.
    tx=tile%4
    ty=tile//4
    for poly in data.polygons:
        poly.use_smooth=smooth
        normal=poly.normal
        axis=max(range(3),key=lambda a:abs(normal[a]))
        axes=[a for a in range(3) if a!=axis]
        for li in poly.loop_indices:
            p=data.vertices[data.loops[li].vertex_index].co
            u=.1 + ((p[axes[0]]*.017+tile*.13)%1)*.8
            v=.1 + ((p[axes[1]]*.017+tile*.07)%1)*.8
            uv.data[li].uv=((tx+u)/4,(ty+v)/4)
    return obj

def sweep(name,centers,radii,tile,bone_id,sides=10):
    """Elliptical ring sweep with y as the transverse direction."""
    verts=[]
    for i,(p,rr) in enumerate(zip(centers,radii)):
        p=Vector(p)
        tangent=Vector(centers[min(i+1,len(centers)-1)])-Vector(centers[max(i-1,0)])
        tangent.normalize()
        transverse=Vector((0,1,0))
        other=tangent.cross(transverse).normalized()
        for j in range(sides):
            a=2*math.pi*j/sides
            verts.append(tuple(p+transverse*(math.cos(a)*rr[0])+other*(math.sin(a)*rr[1])))
    faces=[]
    for i in range(len(centers)-1):
        for j in range(sides):
            faces.append((i*sides+j,i*sides+(j+1)%sides,(i+1)*sides+(j+1)%sides,(i+1)*sides+j))
    faces.append(tuple(reversed(range(sides))))
    faces.append(tuple((len(centers)-1)*sides+j for j in range(sides)))
    return mesh(name,verts,faces,tile,bone_id)

def ellipsoid(name,center,size,tile,bone_id,segments=12,rings=7):
    verts=[]
    for i in range(rings+1):
        phi=-math.pi/2+math.pi*i/rings
        for j in range(segments):
            a=2*math.pi*j/segments
            verts.append((center[0]+size[0]*math.cos(phi)*math.cos(a),
                          center[1]+size[1]*math.cos(phi)*math.sin(a),
                          center[2]+size[2]*math.sin(phi)))
    faces=[]
    for i in range(rings):
        for j in range(segments):
            faces.append((i*segments+j,i*segments+(j+1)%segments,(i+1)*segments+(j+1)%segments,(i+1)*segments+j))
    return mesh(name,verts,faces,tile,bone_id)

def rope(name,path,radius,tile,bone_id,sides=5):
    pts=[Vector(p) for p in path]
    verts=[]
    for i,p in enumerate(pts):
        tangent=(pts[min(i+1,len(pts)-1)]-pts[max(0,i-1)]).normalized()
        cross=tangent.cross(Vector((0,0,1)))
        if cross.length<.01:
            cross=tangent.cross(Vector((0,1,0)))
        cross.normalize()
        up=tangent.cross(cross).normalized()
        for j in range(sides):
            a=j*2*math.pi/sides
            verts.append(tuple(p+radius*(math.cos(a)*cross+math.sin(a)*up)))
    faces=[]
    for i in range(len(pts)-1):
        for j in range(sides):
            faces.append((i*sides+j,i*sides+(j+1)%sides,(i+1)*sides+(j+1)%sides,(i+1)*sides+j))
    return mesh(name,verts,faces,tile,bone_id)

# The back is deliberately shaped rather than assembled from visible primitives.
sweep('Barrel, shoulders and rump',
      [(-42,0,64),(-35,0,66),(-24,0,64),(-7,0,64),(12,0,66),(25,0,68),(34,0,68)],
      [(4,10),(15,17),(18,18),(17,17),(16,18),(15,19),(8,14)],0,body,16)
sweep('Rising neck',[(27,0,67),(31,0,80),(39,0,90),(47,0,99)],
      [(12,16),(12,13),(10,12),(7.8,10)],2,neck,12)
sweep('Long head and muzzle',[(48,0,99),(57,0,99),(66,0,94),(75,0,87),(80,0,84)],
      [(7,9),(8,10),(7,8),(5.5,6),(4.8,4.5)],0,head,12)
ellipsoid('Lower jaw',(56,0,91),(10,6.8,6),1,head,12,5)
ellipsoid('Soft dark muzzle',(79.5,0,83.7),(7,5.7,4.7),11,head,12,5)
for side in (-1,1):
    y=side*6.7
    sweep('Ear '+str(side),[(48,y,106),(47,y*1.05,114),(48,y*1.07,119)],
          [(2.8,3.4),(1.8,2.4),(.15,.25)],1,head,7)
    mesh('Ear inner '+str(side),[(49.1,y-1,109),(48.9,y-1,115),(49.1,y+1,114),(50,y+1,109)],[(0,1,2,3)],11,head)
    ellipsoid('Eye '+str(side),(55.5,side*8.5,99.8),(2.3,1.2,1.9),9,head,10,5)
    ellipsoid('Eye glint '+str(side),(56.1,side*9.55,100.45),(.4,.18,.4),10,head,6,3)
    ellipsoid('Nostril '+str(side),(81,side*5.2,85.1),(1.8,.35,1.1),9,head,8,4)
    # Narrow nose band and the headstall encircle the long horse face.
    rope('Noseband '+str(side),[(78,-5.5,89),(78,-6,84),(79,0,79.5),(78,6,84),(78,5.5,89)],.5,5,head)
    rope('Bridle cheek '+str(side),[(77,side*5.7,84),(67,side*7.5,95),(56,side*8.7,103),(48,side*8.1,108)],.52,5,head)
    rope('Rein '+str(side),[(77,side*6.1,84),(66,side*11,80),(51,side*15,75),(31,side*16,76),(12,side*13,84)],.35,5,neck)
    rope('Bit '+str(side),[(77,side*6,82.9),(78,side*7.6,83.7),(79,side*6,85),(77,side*6,82.9)],.45,8,head)
mesh('Pale forehead blaze',[(52,-1.4,109),(52,1.4,109),(60,1.8,107),(60,-1.8,107),
                            (69,-1.5,99.2),(69,1.5,99.2),(75,1,93),(75,-1,93)],
     [(0,1,2,3),(3,2,5,4),(4,5,6,7)],10,head)

# Layered tapered mane locks; their silhouette remains visible at game distance.
for i in range(8):
    x=18+i*3
    z=89+i*3
    mesh('Mane lock %02d'%i,[(x-2,-1,z),(x+3,-1,z+4),(x+2,-5,z+1),
                           (x-1,-8,z-7),(x-4,-7,z-9),(x-3,-3,z-1)],
         [(0,1,2),(0,2,5),(5,2,3,4),(0,5,4)],3,neck)
sweep('Forelock',[(46,-1,112),(53,-2,109),(57,-3,104)],[(3.4,2),(3.2,1.8),(.1,.2)],3,head,8)
sweep('Tail upper', [(-39,0,72),(-46,0,67),(-52,0,53)],[(3,3.8),(4.3,4.7),(4.2,4)],3,tail,10)
sweep('Tail flowing tip',[(-52,0,53),(-55,0,41),(-58,0,29),(-60,0,22)],[(4.4,4),(4.8,4),(3.8,3),(.5,1)],3,tail_tip,10)

for prefix,(chain,points) in LEGS.items():
    front=prefix.startswith('front')
    for i in range(3):
        start,end=Vector(points[i]),Vector(points[i+1])
        thickness=[(5.9,7.2),(3.6,4.4),(2.4,2.8)][i] if front else [(8,8),(4,5),(2.4,2.8)][i]
        mids=(start*.45+end*.55)
        end_radius=([(3.8,4.3),(2.7,3),(2.7,3.2)][i])
        tile=0
        if i==2 and prefix in ('front_L','hind_R'):
            tile=10
        sweep(prefix+' segment '+str(i),[tuple(start),tuple(mids),tuple(end)],
              [thickness,tuple(v*.9 for v in thickness),end_radius],tile,chain[i],8)
        ellipsoid(prefix+' joint '+str(i),tuple(end),(3.4,3.2,3.5),tile,chain[i+1],8,4)
    hx,hy,_=points[3]
    sweep(prefix+' hoof',[(hx+2,hy,6),(hx+2.5,hy,1.8),(hx+2.5,hy,.7)],
          [(3.9,4.7),(4.5,5.7),(4.6,5.8)],4,chain[3],10)

# Sage saddle blanket, a deep leather seat, raised cantle and brass fittings.
sweep('Wool saddle blanket',[(-19,0,78),(-14,0,81),(-3,0,82),(10,0,81),(15,0,78)],
      [(18,.8),(20,1),(20,1),(19,1),(17,.8)],7,body,12)
sweep('Saddle seat',[(-15,0,84),(-10,0,84),(-2,0,83),(7,0,84),(12,0,85)],
      [(9,3),(10,2),(9.5,2),(8.5,2),(5.5,3)],5,body,12)
rope('Raised cantle',[(-16,-9,86),(-16,-6,90),(-16,0,92),(-16,6,90),(-16,9,86)],1.5,6,body,7)
rope('Pommel arch',[(11,-7,86),(12,-4,89),(12,0,90),(12,4,89),(11,7,86)],1.3,6,body,7)
for side in (-1,1):
    mesh('Saddle skirt '+str(side),[(-14,side*9,83),(11,side*9,83),(9,side*18,69),(-14,side*18,69)],[(0,1,2,3)],5,body)
    rope('Girth '+str(side),[(0,side*12,82),(0,side*18,69),(0,side*16,52),(0,side*7,47)],1.5,5,body,5)
    rope('Stirrup leather '+str(side),[(5,side*10,84),(6,side*19,70),(6,side*21,61)],.9,6,body)
    rope('Stirrup iron '+str(side),[(6,side*21,62),(3,side*22,59),(3,side*22,54),
                                 (10,side*22,54),(10,side*22,59),(6,side*21,62)],.7,13,body)
    rope('Breast collar '+str(side),[(11,side*14,80),(24,side*16,73),(34,side*11,67),(35,0,65)],1.1,5,body)
    ellipsoid('Brass saddle rivet '+str(side),(-11,side*18.3,76),(1,.4,1),8,body,8,4)

# Match the first mount implementation's saddle height (64.6 above feet).
# Uniformly apply the proportion adjustment to geometry and the skeleton.
for obj,idx in OBJECTS:
    for vertex in obj.data.vertices:
        vertex.co.x*=.9
        vertex.co.z*=.76
    obj.data.update()
for b in BONES:
    for key in ('head','tail'):
        b[key].x*=.9
        b[key].z*=.76

# Create the editable armature. Reference SMD coordinates have identity axes;
# Blender's bones align local Y to their tails, so the pose matrices include
# each bone's rest rotation after the SMD world transform.
arm_data=bpy.data.armatures.new('MSR horse skeleton')
arm=bpy.data.objects.new('MSR horse rig',arm_data)
scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active=arm
arm.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
for i,b in enumerate(BONES):
    edit=arm_data.edit_bones.new(b['name'])
    edit.head=b['head']; edit.tail=b['tail']
    if b['parent']>=0:
        edit.parent=arm_data.edit_bones[BONES[b['parent']]['name']]
bpy.ops.object.mode_set(mode='OBJECT')
arm.show_in_front=True
for obj,idx in OBJECTS:
    vg=obj.vertex_groups.new(name=BONES[idx]['name'])
    vg.add(list(range(len(obj.data.vertices))),1,'REPLACE')
    modifier=obj.modifiers.new('Horse rig','ARMATURE')
    modifier.object=arm
    obj.parent=arm

def pose(kind,frame,count):
    t=frame/(count-1)*2*math.pi
    angles=[(0.,0.,0.) for _ in BONES]
    offsets=[Vector((0,0,0)) for _ in BONES]
    if kind=='idle':
        offsets[body].z=.35*math.sin(t)
        angles[neck]=(0,.014*math.sin(t),0)
        angles[head]=(0,.018*math.sin(t+.7),0)
        angles[tail]=(.08*math.sin(t),0,0)
        angles[tail_tip]=(.09*math.sin(t+.8),0,0)
    elif kind=='walk':
        offsets[body].z=.6*math.sin(t*2)
        angles[neck]=(0,.035*math.sin(t),0)
        angles[head]=(0,-.028*math.sin(t),0)
        for name,(chain,pts) in LEGS.items():
            phase={'front_L':0,'hind_R':math.pi/2,'front_R':math.pi,'hind_L':math.pi*1.5}[name]
            q=t+phase
            swing=.29*math.sin(q)
            lift=max(0,math.cos(q))
            angles[chain[0]]=(0,swing,0)
            angles[chain[1]]=(0,-.28*lift,0)
            angles[chain[2]]=(0,.32*lift,0)
            angles[chain[3]]=(0,-.12*lift,0)
        angles[tail]=(.04*math.sin(t),0,0)
    elif kind=='gallop':
        offsets[body].z=2.3*math.sin(t)
        angles[body]=(0,.045*math.sin(t),0)
        angles[neck]=(0,.095*math.sin(t+.4),0)
        angles[head]=(0,-.055*math.sin(t+.4),0)
        for name,(chain,pts) in LEGS.items():
            phase={'front_L':0,'front_R':.6,'hind_L':math.pi,'hind_R':math.pi+.6}[name]
            q=t+phase
            lift=max(0,math.cos(q))
            angles[chain[0]]=(0,.64*math.sin(q),0)
            angles[chain[1]]=(0,-.68*lift,0)
            angles[chain[2]]=(0,.68*lift,0)
            angles[chain[3]]=(0,-.3*lift,0)
        angles[tail]=(0,-.18+.08*math.sin(t),0)
        angles[tail_tip]=(.05*math.sin(t),-.1,0)
    # Keep a supporting hoof on the floor in walk, and prevent penetration in
    # the other loops. Gallop may have airborne frames. This also compensates
    # for the prototype's rigid segment skinning at each hoof joint.
    transforms=global_matrices(angles,offsets)
    low=min((transforms[idx]@(v.co-BONES[idx]['head'])).z
            for obj,idx in OBJECTS if obj.name.endswith(' hoof')
            for v in obj.data.vertices)
    if kind=='walk' or low<.2:
        offsets[body].z+=.2-low
    return angles,offsets

def global_matrices(angles,offsets):
    result=[]
    for i,b in enumerate(BONES):
        parent=b['parent']
        translation=b['head']-(BONES[parent]['head'] if parent>=0 else Vector((0,0,0)))+offsets[i]
        a=angles[i]
        rotation=Matrix.Rotation(a[2],4,'Z')@Matrix.Rotation(a[1],4,'Y')@Matrix.Rotation(a[0],4,'X')
        local=Matrix.Translation(translation)@rotation
        result.append(result[parent]@local if parent>=0 else local)
    return result

def nodes(f):
    f.write('version 1\nnodes\n')
    for i,b in enumerate(BONES):
        f.write(f'{i} "{b["name"]}" {b["parent"]}\n')
    f.write('end\nskeleton\n')
def skeleton_frame(f,kind,frame,count):
    angles,offsets=pose(kind,frame,count)
    f.write(f'time {frame}\n')
    for i,b in enumerate(BONES):
        parent=b['parent']
        p=b['head']-(BONES[parent]['head'] if parent>=0 else Vector((0,0,0)))+offsets[i]
        a=angles[i]
        f.write('%d %.6f %.6f %.6f %.6f %.6f %.6f\n'%(i,*p,*a))

with (EXPORT/'horse_reference.smd').open('w',newline='\n') as f:
    nodes(f)
    # The bind pose has no idle offsets or rotations.
    f.write('time 0\n')
    for i,b in enumerate(BONES):
        p=b['head']-(BONES[b['parent']]['head'] if b['parent']>=0 else Vector((0,0,0)))
        f.write('%d %.6f %.6f %.6f 0 0 0\n'%(i,*p))
    f.write('end\ntriangles\n')
    triangle_count=0
    for obj,idx in OBJECTS:
        data=obj.data
        data.calc_loop_triangles()
        uv=data.uv_layers.active
        for triangle in data.loop_triangles:
            if triangle.area < .000001:
                continue
            triangle_count+=1
            f.write('horse_atlas.bmp\n')
            for li in triangle.loops:
                loop=data.loops[li]
                p=data.vertices[loop.vertex_index].co
                normal=data.vertices[loop.vertex_index].normal
                texcoord=uv.data[li].uv
                f.write('%d %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f\n'%(idx,*p,*normal,*texcoord))
    f.write('end\n')

for kind,count,fps in [('idle',41,20),('walk',25,24),('gallop',21,30)]:
    with (EXPORT/f'horse_{kind}.smd').open('w',newline='\n') as f:
        nodes(f)
        for frame in range(count):
            skeleton_frame(f,kind,frame,count)
        f.write('end\n')
    arm.animation_data_create()
    action=bpy.data.actions.new('Horse '+kind)
    arm.animation_data.action=action
    for frame in range(count):
        angles,offsets=pose(kind,frame,count)
        transforms=global_matrices(angles,offsets)
        for i,b in enumerate(BONES):
            pb=arm.pose.bones[b['name']]
            rest=arm_data.bones[b['name']].matrix_local.to_3x3().to_4x4()
            pb.matrix=transforms[i]@rest
            pb.keyframe_insert('location',frame=frame+1)
            pb.keyframe_insert('rotation_quaternion',frame=frame+1)
            pb.keyframe_insert('scale',frame=frame+1)
    action['fps']=fps
    action['loop']=True
arm.animation_data.action=bpy.data.actions.get('Horse idle')
scene.frame_set(1)

(EXPORT/'horse.qc').write_text('''// Original procedural MSR horse, +X forward, feet at Z=0.
$modelname "plains_horse.mdl"
$cd "."
$cdtexture "."
$scale 1.0
$gamma 1.8
$origin 0 0 0 -90
$body "horse" "horse_reference"
$attachment 0 "body" -1.8 0 15.2
$sequence "idle" "horse_idle" fps 20 loop
$sequence "walk" "horse_walk" fps 24 loop
$sequence "gallop" "horse_gallop" fps 30 loop
$bbox -58 -23 0 80 23 92
$cbox -58 -23 0 80 23 92
''',encoding='ascii')

# Studio preview: uncluttered ground, three soft area lights and a long lens.
groundmat=bpy.data.materials.new('Preview ground')
groundmat.diffuse_color=(.095,.13,.105,1)
bpy.ops.mesh.primitive_plane_add(size=2000,location=(0,0,-.08))
ground=bpy.context.object
ground.name='Preview ground (not exported)'
ground.data.materials.append(groundmat)
for name,loc,power,size,color in [
    ('Key',(95,-130,205),380000,120,(1,.85,.69)),
    ('Fill',(15,150,145),280000,110,(.74,.86,1)),
    ('Rim',(-115,10,155),340000,90,(1,.94,.82))]:
    lamp=bpy.data.lights.new(name,'AREA')
    lamp.energy=power; lamp.shape='DISK'; lamp.size=size; lamp.color=color
    obj=bpy.data.objects.new(name,lamp); scene.collection.objects.link(obj); obj.location=loc
    obj.rotation_euler=(Vector((0,0,65))-obj.location).to_track_quat('-Z','Y').to_euler()
cam_data=bpy.data.cameras.new('Horse preview camera')
cam=bpy.data.objects.new('Horse preview camera',cam_data)
scene.collection.objects.link(cam)
cam.location=(150,-230,139)
cam.rotation_euler=(Vector((8,0,45))-cam.location).to_track_quat('-Z','Y').to_euler()
cam_data.type='ORTHO'; cam_data.ortho_scale=172
scene.camera=cam
scene.render.engine='BLENDER_EEVEE_NEXT'
scene.render.resolution_x=1440; scene.render.resolution_y=1080; scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.world.color=(.035,.045,.06)
scene.view_settings.view_transform='AgX'
scene.render.filepath=str(HERE/'horse-preview.png')
scene.render.film_transparent=False
atlas.pack()
bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'MSR-Daragoth-Horse.blend'))
bpy.ops.render.render(write_still=True)
cam.location=(3,-260,86)
cam.rotation_euler=(Vector((8,0,45))-cam.location).to_track_quat('-Z','Y').to_euler()
cam_data.ortho_scale=173
scene.render.filepath=str(HERE/'horse-side-preview.png')
bpy.ops.render.render(write_still=True)
metadata={'asset':'Original Daragoth chestnut horse prototype','triangle_count':triangle_count,
          'bones':len(BONES),'texture':'512x512 indexed BMP, 256 colors',
          'sequences':{'idle':{'frames':41,'fps':20},'walk':{'frames':25,'fps':24},'gallop':{'frames':21,'fps':30}},
          'coordinate_system':'+X forward, +Z up, feet Z=0','saddle_attachment':0,
          'saddle_anchor':[-1.8,0,64.6],
          'stage':'mount development prototype; rider pose and gameplay collision are separate',
          'source_assets':'None; procedural geometry, palette, and animation generated here',
          'license':'CC0-1.0 for generated model, texture and animation; MIT for generating script'}
(HERE/'horse-manifest.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
print('HORSE_EXPORT_COMPLETE '+json.dumps(metadata))
