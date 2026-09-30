"""Original low-poly Daragoth foliage; Blender 4.5 LTS background generator.

All meshes, indexed bark/leaf/rock textures and wind animation are authored
procedurally here. No stock meshes or third-party image assets are required.
"""
from pathlib import Path
import bpy
from mathutils import Vector
import math, random, struct, json

HERE=Path(__file__).resolve().parent
EXPORT=HERE/'export'
EXPORT.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene
random.seed(2910926)
TEXTURES={}
MODELS=[]

def indexed_texture(name,width,height,pixels,palette,masked=False):
    """BMP rows and Blender texture use bottom-up texel order identically."""
    assert len(pixels)==width*height and width%4==0 and len(palette)==256
    offset=1078
    with (EXPORT/(name+'.bmp')).open('wb') as f:
        f.write(struct.pack('<2sIHHI',b'BM',offset+len(pixels),0,0,offset))
        f.write(struct.pack('<IiiHHIIiiII',40,width,height,1,8,0,len(pixels),2835,2835,256,256))
        for r,g,b in palette:
            f.write(bytes((b,g,r,0)))
        f.write(bytes(pixels))
    image=bpy.data.images.new(name,width=width,height=height,alpha=True)
    rgba=[]
    for p in pixels:
        rgba.extend([*(c/255 for c in palette[p]),0.0 if masked and p==255 else 1.0])
    image.pixels.foreach_set(rgba)
    image.filepath_raw=str(EXPORT/(name+'-preview.png'))
    image.file_format='PNG'
    image.save(); image.pack()
    mat=bpy.data.materials.new(name)
    mat.use_nodes=True
    bsdf=mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Roughness'].default_value=.93
    tex=mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex.image=image
    mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
    if masked:
        mat.node_tree.links.new(tex.outputs['Alpha'],bsdf.inputs['Alpha'])
        mat.surface_render_method='DITHERED'
        mat.use_backface_culling=True
    TEXTURES[name]={'material':mat,'masked':masked,'width':width,'height':height,
                    'transparent_pixels':sum(p==255 for p in pixels) if masked else 0}
    return name

def clamp(x): return max(0,min(255,round(x)))
def bark_texture(name,kind):
    width,height=256,512
    if kind=='birch':
        palette=[(clamp(30+i*.78),clamp(31+i*.76),clamp(27+i*.70)) for i in range(256)]
    elif kind=='rock':
        palette=[(clamp(30+i*.45),clamp(34+i*.44),clamp(29+i*.42)) for i in range(256)]
    else:
        base=(40,26,18) if kind=='pine' else (39,30,21)
        palette=[tuple(clamp(c+i*v) for c,v in zip(base,(.40,.30,.21))) for i in range(256)]
    pixels=[]
    rng=random.Random(712+len(name))
    for y in range(height):
        for x in range(width):
            if kind=='birch':
                n=220+math.sin(x*.10+y*.04)*10+rng.uniform(-8,8)
                stripe=math.sin(y*.19+math.sin(x*.033)*.8)
                if stripe>.89 and math.sin(x*.064+y*.008)>.2:
                    n=34+rng.uniform(-15,25)
                if math.sin(x*.031-y*.012)>.75 and math.sin(y*.13)>.75:
                    n=85+rng.uniform(-10,30)
            elif kind=='rock':
                n=120+math.sin(x*.047+math.sin(y*.039)*3)*30+math.sin(y*.071+x*.041)*20+rng.uniform(-19,19)
                if math.sin(x*.019+y*.031)*math.sin(y*.035-x*.03)>.76:
                    n+=55
            else:
                furrow=math.sin(x*.17+math.sin(y*.013)*.5)
                crack=math.sin(x*.57+math.sin(y*.034))
                n=140+furrow*45+crack*17+rng.uniform(-15,15)
                if furrow<-.83: n-=55
                if kind=='pine' and math.sin(y*.079+math.sin(x*.09))>.8: n-=35
            pixels.append(clamp(n))
    return indexed_texture(name,width,height,pixels,palette)

def leaf_texture(name,kind):
    # 2x2 atlas of distinct sprays. Index255 is always the one-bit alpha hole.
    width=height=512
    if kind=='birch': base=(48,75,22); slope=(.31,.36,.13)
    elif kind=='pine': base=(15,40,25); slope=(.22,.36,.23)
    elif kind=='bush': base=(20,52,19); slope=(.26,.35,.16)
    else: base=(25,52,18); slope=(.33,.39,.18)
    palette=[tuple(clamp(c+i*v) for c,v in zip(base,slope)) for i in range(160)]
    palette.extend([(54+(i-160)*2,35+(i-160),19+(i-160)//2) for i in range(160,208)])
    palette.extend([(97+(i-208)*2,116+(i-208),38+(i-208)) for i in range(208,240)])
    palette.extend([(105+(i-240)*5,35+(i-240)*2,30+(i-240)) for i in range(240,255)])
    # Index255 controls GoldSrc masking regardless of its RGB. Matching green
    # prevents bilinear filtering from producing the classic bright blue fringe.
    palette.append(tuple(clamp(c+55*v) for c,v in zip(base,slope)))
    pixels=[255]*(width*height)
    def dot(x,y,r,color):
        for iy in range(max(0,int(y-r)),min(height,int(y+r)+2)):
            for ix in range(max(0,int(x-r)),min(width,int(x+r)+2)):
                if (ix-x)**2+(iy-y)**2<=r*r:
                    pixels[iy*width+ix]=color
    def line(a,b,r,color):
        dx=b[0]-a[0]; dy=b[1]-a[1]
        steps=max(1,int(math.hypot(dx,dy)*1.6))
        for i in range(steps+1):
            t=i/steps
            dot(a[0]+dx*t,a[1]+dy*t,r,color)
    def polygon(points,color):
        ymin=max(0,int(min(p[1] for p in points)))
        ymax=min(height-1,int(max(p[1] for p in points))+1)
        for y in range(ymin,ymax+1):
            intersections=[]
            for a,b in zip(points,points[1:]+points[:1]):
                if (a[1]<=y+.5<b[1]) or (b[1]<=y+.5<a[1]):
                    intersections.append(a[0]+(y+.5-a[1])*(b[0]-a[0])/(b[1]-a[1]))
            intersections.sort()
            for xa,xb in zip(intersections[::2],intersections[1::2]):
                for x in range(max(0,int(xa)),min(width,int(xb)+1)):
                    pixels[y*width+x]=color
    for tile in range(4):
        ox=(tile%2)*256; oy=(tile//2)*256
        rng=random.Random(2711+tile*54+len(kind))
        stem=(ox+128,oy+26)
        tip=(ox+128+rng.uniform(-20,20),oy+229)
        line(stem,tip,1.7,173)
        if kind=='grass':
            for i in range(32):
                base_x=ox+128+rng.uniform(-39,39)
                top_x=base_x+rng.uniform(-66,66)
                top_y=oy+rng.uniform(135,229)
                bend=rng.uniform(-21,21)
                blade_width=rng.uniform(1.3,3.3)
                left=[]; right=[]
                for j in range(7):
                    t=j/6
                    x=base_x+(top_x-base_x)*t+bend*math.sin(t*math.pi)
                    y=oy+21+(top_y-oy-21)*t
                    radius=blade_width*(1-t)+.1
                    left.append((x-radius,y)); right.append((x+radius,y))
                polygon(left+list(reversed(right)),rng.randrange(70,151))
                if i%6==0:
                    line((top_x,top_y-26),(top_x,top_y+5),.8,219)
                    for j in range(6):
                        y=top_y-21+j*4
                        line((top_x,y),(top_x+(-1 if j%2 else 1)*4,y+3),1.0,221+j)
        elif kind=='pine':
            for i in range(22):
                t=.12+i*.035
                center=(stem[0]+(tip[0]-stem[0])*t,stem[1]+(tip[1]-stem[1])*t)
                spread=80*(1-t)+10
                for sign in (-1,1):
                    end=(center[0]+spread*sign,center[1]+rng.uniform(11,31))
                    line(center,end,1.15,rng.randrange(50,125))
                    for j in range(7):
                        q=(j+.2)/7
                        anchor=(center[0]+(end[0]-center[0])*q,center[1]+(end[1]-center[1])*q)
                        for side in (-1,1):
                            needle=(anchor[0]+sign*rng.uniform(5,10),anchor[1]+side*rng.uniform(6,14))
                            line(anchor,needle,.7,rng.randrange(45,145))
        else:
            for i in range(23):
                t=.12+(i//2)*.067
                sign=-1 if i%2 else 1
                anchor=(stem[0]+(tip[0]-stem[0])*t,stem[1]+(tip[1]-stem[1])*t)
                cx=anchor[0]+sign*rng.uniform(16,64)*(1-.4*t)
                cy=anchor[1]+rng.uniform(9,24)
                line(anchor,(cx,cy),.9,174)
                angle=math.atan2(cy-anchor[1],cx-anchor[0])
                length=rng.uniform(19,30) if kind=='oak' else rng.uniform(16,25)
                halfwidth=length*(.45 if kind=='oak' else .38)
                axis=(math.cos(angle),math.sin(angle)); cross=(-axis[1],axis[0])
                points=[]
                for j in range(20):
                    a=j*2*math.pi/20
                    ripple=(1+.18*math.cos(a*6)) if kind=='oak' else (1+.035*math.cos(a*10))
                    u=math.cos(a)*length*.65
                    v=math.sin(a)*halfwidth*ripple
                    points.append((cx+axis[0]*u+cross[0]*v,cy+axis[1]*u+cross[1]*v))
                shade=rng.randrange(62,149)
                polygon(points,shade)
                line((cx-axis[0]*length*.60,cy-axis[1]*length*.60),
                     (cx+axis[0]*length*.53,cy+axis[1]*length*.53),.65,min(159,shade+15))
            if kind=='bush':
                for i in range(6):
                    dot(ox+rng.uniform(65,190),oy+rng.uniform(70,200),3.6,243+rng.randrange(7))
    return indexed_texture(name,width,height,pixels,palette,masked=True)

oak_bark=bark_texture('oak_bark','oak')
birch_bark=bark_texture('birch_bark','birch')
pine_bark=bark_texture('pine_bark','pine')
stone=bark_texture('plains_stone','rock')
oak_leaf=leaf_texture('oak_leaves','oak')
birch_leaf=leaf_texture('birch_leaves','birch')
pine_leaf=leaf_texture('pine_needles','pine')
bush_leaf=leaf_texture('bush_leaves','bush')
grass_leaf=leaf_texture('plains_grass_blades','grass')

def new_model(name,height,pivot):
    collection=bpy.data.collections.new(name)
    scene.collection.children.link(collection)
    model={'name':name,'height':height,'pivot':pivot,'objects':[], 'collection':collection,
           'bones':2 if pivot else 1}
    MODELS.append(model)
    return model

def mesh(model,name,verts,faces,texture,uvs,bone=0,smooth=False):
    data=bpy.data.meshes.new(name)
    data.from_pydata(verts,[],faces); data.materials.append(TEXTURES[texture]['material']); data.update()
    obj=bpy.data.objects.new(name,data); model['collection'].objects.link(obj)
    layer=data.uv_layers.new(name='Procedural texture UV')
    for p,coords in zip(data.polygons,uvs):
        p.use_smooth=smooth
        for li,uv in zip(p.loop_indices,coords): layer.data[li].uv=uv
    model['objects'].append((obj,texture,bone,smooth))
    return obj

def tube(model,name,points,radii,texture,sides=9):
    pts=[Vector(p) for p in points]
    verts=[]; distance=0; distances=[0]
    for a,b in zip(pts,pts[1:]): distances.append(distances[-1]+(b-a).length)
    for i,p in enumerate(pts):
        tangent=(pts[min(i+1,len(pts)-1)]-pts[max(i-1,0)]).normalized()
        axis=tangent.cross(Vector((0,1,0))).normalized()
        second=tangent.cross(axis).normalized()
        for j in range(sides):
            a=j*2*math.pi/sides
            radius=radii[i]*(1+.055*math.sin(j*2.3+i*.4))
            v=p+(math.cos(a)*axis+math.sin(a)*second)*radius
            v.z=max(0,v.z)
            verts.append(tuple(v))
    faces=[]; uvs=[]
    for i in range(len(pts)-1):
        for j in range(sides):
            faces.append((i*sides+j,i*sides+(j+1)%sides,(i+1)*sides+(j+1)%sides,(i+1)*sides+j))
            u0=j/sides; u1=(j+1)/sides
            # Repeat bark vertically; compiler accepts wrapping texture UVs.
            v0=distances[i]/120; v1=distances[i+1]/120
            uvs.append([(u0,v0),(u1,v0),(u1,v1),(u0,v1)])
    faces.extend([tuple(reversed(range(sides))),tuple((len(pts)-1)*sides+j for j in range(sides))])
    uvs.extend([[(.5+.45*math.cos(j*2*math.pi/sides),.5+.45*math.sin(j*2*math.pi/sides)) for j in reversed(range(sides))],
                [(.5+.45*math.cos(j*2*math.pi/sides),.5+.45*math.sin(j*2*math.pi/sides)) for j in range(sides)]])
    return mesh(model,name,verts,faces,texture,uvs,smooth=True)

def spray(model,center,width,height,texture,rng,pine=False):
    # Two intersecting, irregularly oriented planes, explicitly double-sided.
    # One bit alpha cuts out individual leaves instead of drawing solid sheets.
    center=Vector(center)
    yaw=rng.uniform(0,2*math.pi)
    for plane in range(2):
        a=yaw+plane*math.pi/2
        u=Vector((math.cos(a),math.sin(a),0))
        tilt=rng.uniform(-.48,.48) if not pine else rng.uniform(.4,1.15)
        v=Vector((-math.sin(a)*math.sin(tilt),math.cos(a)*math.sin(tilt),math.cos(tilt)))
        if texture in ('oak_leaves','bush_leaves'):
            roll=rng.uniform(-math.pi,math.pi)
            u,v=u*math.cos(roll)+v*math.sin(roll),-u*math.sin(roll)+v*math.cos(roll)
        verts=[tuple(center-u*width/2-v*height/2),tuple(center+u*width/2-v*height/2),
               tuple(center+u*width/2+v*height/2),tuple(center-u*width/2+v*height/2)]
        tile=rng.randrange(4); tx=tile%2; ty=tile//2
        uv=[((tx+.015)/2,(ty+.015)/2),((tx+.985)/2,(ty+.015)/2),
            ((tx+.985)/2,(ty+.985)/2),((tx+.015)/2,(ty+.985)/2)]
        verts=[(x,y,max(0,z)) for x,y,z in verts]
        mesh(model,'Leaf spray',verts,[(0,1,2,3),(3,2,1,0)],texture,[uv,list(reversed(uv))],bone=1 if model['bones']==2 else 0)

oak=new_model('plains_oak',480,160)
tube(oak,'Oak trunk',[(0,0,0),(-3,1,35),(3,-4,105),(0,-6,170),(8,1,238),(12,3,280)],
     [29,24,19,16,11,5],oak_bark,12)
for j in range(6):
    a=j*2*math.pi/6
    tube(oak,'Oak buttress root',[(0,0,35),(math.cos(a)*27,math.sin(a)*27,10),
                              (math.cos(a)*49,math.sin(a)*49,0)],[11,8,.8],oak_bark,7)
rng=random.Random(400)
tips=[]
for i in range(10):
    a=i*2*math.pi/10+rng.uniform(-.18,.18)
    start=Vector((4,0,155+i*7)); r=rng.uniform(115,150)
    end=Vector((math.cos(a)*r,math.sin(a)*r,330+rng.uniform(-20,25)))
    mid=start.lerp(end,.45)+Vector((0,0,23))
    tube(oak,'Oak main branch',[start,mid,end],[11,7,2],oak_bark,8)
    for j in range(2):
        q=a+(j-.5)*.65
        tip=end+Vector((math.cos(q)*rng.uniform(24,43),math.sin(q)*rng.uniform(24,43),rng.uniform(24,54)))
        tube(oak,'Oak crown twig',[mid.lerp(end,.6),end,tip],[4,2,.8],oak_bark,6)
        tips.append(tip)
for tip in tips:
    for i in range(13):
        offset=Vector((rng.uniform(-45,45),rng.uniform(-45,45),rng.uniform(-28,48)))
        spray(oak,tip+offset,rng.uniform(53,77),rng.uniform(53,78),oak_leaf,rng)
for i in range(75):
    spray(oak,(rng.uniform(-105,105),rng.uniform(-105,105),rng.uniform(282,410)),70,70,oak_leaf,rng)

birch=new_model('plains_birch',430,170)
tube(birch,'Birch white trunk',[(0,0,0),(-2,0,70),(2,2,145),(5,0,235),(12,2,325),(9,3,407)],
     [16,12,10,8,5,1.4],birch_bark,10)
rng=random.Random(401)
for i in range(15):
    a=i*2.399+rng.uniform(-.2,.2); z=190+i*12
    radius=70*(1-abs(z-285)/250)
    start=Vector((5,1,z)); end=Vector((math.cos(a)*radius,math.sin(a)*radius,z+rng.uniform(25,51)))
    mid=start.lerp(end,.5)+Vector((0,0,6))
    tube(birch,'Birch fine branch',[start,mid,end],[3.5,2,.6],birch_bark,6)
    for j in range(9):
        offset=Vector((rng.uniform(-22,22),rng.uniform(-22,22),rng.uniform(-11,28)))
        spray(birch,end+offset,rng.uniform(28,46),rng.uniform(37,59),birch_leaf,rng)
for i in range(20):
    spray(birch,(rng.uniform(-23,23),rng.uniform(-23,23),rng.uniform(325,397)),40,54,birch_leaf,rng)

pine=new_model('plains_pine',520,160)
tube(pine,'Pine straight trunk',[(0,0,0),(3,0,65),(0,2,200),(-3,0,340),(0,0,508)],
     [21,16,11,7,1],pine_bark,10)
rng=random.Random(402)
for level in range(9):
    z=130+level*40
    radius=144*(1-level/10)
    spokes=9 if level<5 else 7
    for i in range(spokes):
        a=i*2*math.pi/spokes+level*.45+rng.uniform(-.13,.13)
        start=Vector((0,0,z+15)); end=Vector((math.cos(a)*radius,math.sin(a)*radius,z-8))
        tube(pine,'Pine layered bough',[start,start.lerp(end,.55)+Vector((0,0,-9)),end],
             [4*(1-level*.065),2,.65],pine_bark,5)
        for j in range(3):
            center=start.lerp(end,.35+j*.28)
            spray(pine,center,rng.uniform(36,57)*(1-level*.035),rng.uniform(52,72),pine_leaf,rng,pine=True)
for i in range(8):
    spray(pine,(rng.uniform(-12,12),rng.uniform(-12,12),490+rng.uniform(-5,10)),32,54,pine_leaf,rng)

bush=new_model('plains_bush',64,12)
rng=random.Random(403)
for i in range(9):
    a=i*2.399; end=Vector((math.cos(a)*rng.uniform(17,31),math.sin(a)*rng.uniform(17,31),rng.uniform(24,43)))
    tube(bush,'Bush branching stem',[(0,0,0),(end.x*.25,end.y*.25,16),end],[2.4,1.4,.5],oak_bark,5)
    for j in range(5):
        spray(bush,end+Vector((rng.uniform(-10,10),rng.uniform(-10,10),rng.uniform(-10,10))),
              rng.uniform(24,35),rng.uniform(25,36),bush_leaf,rng)

rocks=new_model('plains_rocks',54,0)
rng=random.Random(404)
for i,(position,size) in enumerate([((0,0,23),(32,29,30)),((29,8,12),(22,20,17)),
                                   ((-28,-8,10),(25,19,16)),((7,-25,9),(19,19,13))]):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=1,location=(0,0,0))
    source=bpy.context.object
    vertices=[]
    for v in source.data.vertices:
        n=rng.uniform(.85,1.14)
        vertices.append((position[0]+v.co.x*size[0]*n,position[1]+v.co.y*size[1]*n,
                         max(0,position[2]+v.co.z*size[2]*n)))
    faces=[tuple(p.vertices) for p in source.data.polygons]
    uvs=[]
    for f in faces:
        uvs.append([((vertices[v][0]*.025)%1,(vertices[v][1]*.025+vertices[v][2]*.02)%1) for v in f])
    bpy.data.objects.remove(source,do_unlink=True)
    mesh(rocks,'Weathered rock '+str(i),vertices,faces,stone,uvs)

grass=new_model('plains_grass',30,0)
rng=random.Random(405)
for i in range(6):
    a=i*2.399
    spray(grass,(math.cos(a)*10,math.sin(a)*10,13),rng.uniform(24,33),rng.uniform(25,32),grass_leaf,rng)

def write_nodes(f,model):
    f.write('version 1\nnodes\n0 "root" -1\n')
    if model['bones']==2: f.write('1 "canopy" 0\n')
    f.write('end\nskeleton\n')
def skeleton(f,model,frame,angle=0):
    f.write(f'time {frame}\n0 0 0 0 0 0 0\n')
    if model['bones']==2: f.write(f'1 0 0 {model["pivot"]:.6f} {angle:.6f} {angle*.4:.6f} 0\n')

for model in MODELS:
    # Enforce feet at the origin and an exact useful model height.
    zmax=max(v.co.z for obj,_,_,_ in model['objects'] for v in obj.data.vertices)
    factor=model['height']/zmax
    model['pivot']*=factor
    for obj,_,_,_ in model['objects']:
        for v in obj.data.vertices: v.co.z*=factor
        obj.data.update()
    vertices=[v.co for obj,_,_,_ in model['objects'] for v in obj.data.vertices]
    model['bounds']=[[min(v[a] for v in vertices) for a in range(3)],[max(v[a] for v in vertices) for a in range(3)]]
    model['radius']=max(math.hypot(v.x,v.y) for v in vertices)
    model['textures']=sorted(set(tex for _,tex,_,_ in model['objects']))
    triangles=0
    with (EXPORT/(model['name']+'_reference.smd')).open('w',newline='\n') as f:
        write_nodes(f,model); skeleton(f,model,0); f.write('end\ntriangles\n')
        for obj,texture,bone,smooth in model['objects']:
            data=obj.data; data.calc_loop_triangles(); uv=data.uv_layers.active
            for tri in data.loop_triangles:
                if tri.area<.00001: continue
                triangles+=1; f.write(texture+'.bmp\n')
                for li in tri.loops:
                    vi=data.loops[li].vertex_index; p=data.vertices[vi].co
                    normal=data.vertices[vi].normal if smooth else tri.normal
                    f.write('%d %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f\n'%(bone,*p,*normal,*uv.data[li].uv))
        f.write('end\n')
    model['triangles']=triangles
    frames=25 if model['bones']==2 else 2
    with (EXPORT/(model['name']+'_idle.smd')).open('w',newline='\n') as f:
        write_nodes(f,model)
        for frame in range(frames):
            amplitude=.006 if model['height']>100 else .018
            skeleton(f,model,frame,amplitude*math.sin(frame/(frames-1)*2*math.pi))
        f.write('end\n')
    lo,hi=model['bounds']
    bbox=' '.join('%.4f'%n for n in (*lo,*hi))
    qc=f'''// Original generated Daragoth foliage. +Z up, ground origin Z=0.
$modelname "{model['name']}.mdl"
$cd "."
$cdtexture "."
$scale 1
$gamma 1.8
$origin 0 0 0 -90
$body "prop" "{model['name']}_reference"
$sequence "idle" "{model['name']}_idle" fps 12 loop
$bbox {bbox}
$cbox {bbox}
'''
    for tex in model['textures']:
        if TEXTURES[tex]['masked']: qc+=f'$texrendermode "{tex}.bmp" masked\n'
    (EXPORT/(model['name']+'.qc')).write_text(qc,encoding='ascii')
    # The source .blend is editable with actual weights and a tiny wind action.
    arm_data=bpy.data.armatures.new(model['name']+' skeleton')
    arm=bpy.data.objects.new(model['name']+' rig',arm_data); model['collection'].objects.link(arm)
    bpy.context.view_layer.objects.active=arm; arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    root=arm_data.edit_bones.new('root'); root.head=(0,0,0); root.tail=(0,0,10)
    if model['bones']==2:
        canopy=arm_data.edit_bones.new('canopy'); canopy.head=(0,0,model['pivot']); canopy.tail=(0,0,model['pivot']+10); canopy.parent=root
    bpy.ops.object.mode_set(mode='OBJECT'); arm.select_set(False)
    for obj,_,bone,_ in model['objects']:
        group=obj.vertex_groups.new(name='canopy' if bone else 'root'); group.add(list(range(len(obj.data.vertices))),1,'REPLACE')
        modifier=obj.modifiers.new('Wind rig','ARMATURE'); modifier.object=arm; obj.parent=arm
    if model['bones']==2:
        pb=arm.pose.bones['canopy']; pb.rotation_mode='XYZ'
        # Bone local Y points upward, so local-X/ Z represent global XY sway.
        for frame in range(frames):
            angle=(.006 if model['height']>100 else .018)*math.sin(frame/(frames-1)*2*math.pi)
            pb.rotation_euler=(angle,0,-angle*.4); pb.keyframe_insert('rotation_euler',frame=frame+1)
        arm.animation_data.action.name=model['name']+' gentle wind'
    model['rig']=arm

# Arrange all five models in one studio illustration, preserving local export.
positions={'plains_oak':(-580,0,0),'plains_birch':(0,15,0),'plains_pine':(410,0,0),
           'plains_bush':(-180,-190,0),'plains_rocks':(105,-190,0),'plains_grass':(-330,-200,0)}
for model in MODELS: model['rig'].location=positions[model['name']]
scene.frame_set(1)
ground_mat=bpy.data.materials.new('Preview grass ground'); ground_mat.diffuse_color=(.13,.17,.095,1)
bpy.ops.mesh.primitive_plane_add(size=5000,location=(0,0,-.1))
ground=bpy.context.object; ground.name='Preview ground only'; ground.data.materials.append(ground_mat)
for name,loc,power,size,color in [('Sun key',(-500,-650,1000),12000000,650,(1,.96,.88)),
                                  ('Sky fill',(300,200,950),9000000,850,(.85,.92,1)),
                                  ('Rim',(600,350,700),5500000,650,(1,.98,.92))]:
    light=bpy.data.lights.new(name,'AREA'); light.energy=power; light.size=size; light.shape='DISK'; light.color=color
    obj=bpy.data.objects.new(name,light); scene.collection.objects.link(obj); obj.location=loc
    obj.rotation_euler=(Vector((0,0,200))-obj.location).to_track_quat('-Z','Y').to_euler()
camera_data=bpy.data.cameras.new('Foliage kit camera'); camera=bpy.data.objects.new('Foliage kit camera',camera_data)
scene.collection.objects.link(camera); scene.camera=camera
camera.location=(600,-1800,700); camera.rotation_euler=(Vector((-70,0,250))-camera.location).to_track_quat('-Z','Y').to_euler()
camera_data.type='ORTHO'; camera_data.ortho_scale=1500
camera_data.clip_end=10000
scene.render.engine='BLENDER_EEVEE_NEXT'; scene.render.resolution_x=1800; scene.render.resolution_y=1000
scene.render.resolution_percentage=100; scene.render.image_settings.file_format='PNG'
scene.view_settings.view_transform='AgX'; scene.world.color=(.09,.12,.16)
scene.render.filepath=str(HERE/'foliage-kit-preview.png')
bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'MSR-Daragoth-Foliage.blend'))
bpy.ops.render.render(write_still=True)
# A closer oak preview makes the original alpha leaf shapes and bark clear.
camera.location=(-140,-850,420); camera.rotation_euler=(Vector((-580,0,240))-camera.location).to_track_quat('-Z','Y').to_euler()
camera_data.ortho_scale=580
scene.render.resolution_x=1200; scene.render.resolution_y=1200
for model in MODELS:
    if model['name']!='plains_oak':
        for obj,_,_,_ in model['objects']: obj.hide_render=True
scene.render.filepath=str(HERE/'oak-detail-preview.png'); bpy.ops.render.render(write_still=True)
manifest={'origin':'ground center; +Z up; feet Z=0','idle_sequence':0,'source':'all geometry, textures and wind authored procedurally; no external assets',
          'asset_license':'CC0-1.0','script_license':'MIT','models':[]}
for model in MODELS:
    manifest['models'].append({k:model[k] for k in ('name','height','bounds','radius','textures','triangles','bones')})
(HERE/'foliage-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('FOLIAGE_EXPORT_COMPLETE '+json.dumps(manifest))
