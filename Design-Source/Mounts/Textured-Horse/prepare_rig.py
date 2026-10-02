"""Repair the CC0 Lyndon/ChadM horse, add original tack and native gait loops.

Run Blender --background --disable-autoexec --python this_file --
    --source downloaded.blend --output prepared-horse.blend
The input is hash-checked and never overwritten. Native single-bone weights
are also used in the editable preview so its deformation matches the export.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

SOURCE_SHA = '9cca670b93a74d50e89263e50d55ab035a6c46aa7d2b21e354bdac6987037f4a'
NAMES = {'Bone': 'body', 'Bone.001': 'neck', 'Bone.002': 'head',
         'Bone.001_L': 'ear_R', 'Bone.001_R': 'ear_L',
         'Bone_L': 'front_R_upper', 'Bone_L.001': 'front_R_mid', 'Bone_L.002': 'front_R_lower',
         'Bone_R': 'front_L_upper', 'Bone_R.001': 'front_L_mid', 'Bone_R.002': 'front_L_lower',
         'Bone_L.003': 'hind_L_upper', 'Bone_L.004': 'hind_L_mid', 'Bone_L.005': 'hind_L_lower',
         'Bone_R.003': 'hind_R_upper', 'Bone_R.004': 'hind_R_mid', 'Bone_R.005': 'hind_R_lower',
         'Bone.003': 'tail', 'Bone.004': 'tail_tip'}
SEQUENCES = [('idle', 41, 20), ('walk', 25, 24), ('gallop', 21, 30)]


def args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    return parser.parse_args(sys.argv[sys.argv.index('--')+1:])


def material(name, color, image=None, alpha=False):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = .83
    if image:
        tex = nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images[image]
        links.new(tex.outputs['Color'], shader.inputs['Base Color'])
        if alpha:
            links.new(tex.outputs['Alpha'], shader.inputs['Alpha'])
            mat.surface_render_method = 'DITHERED'
    return mat


def main(options):
    source, output = options.source.resolve(), options.output.resolve()
    assert source != output
    assert hashlib.sha256(source.read_bytes()).hexdigest() == SOURCE_SHA, 'Changed source'
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    arm = bpy.data.objects['Armature']
    old_world = {o.name: o.matrix_world.copy() for o in [arm, *meshes]}
    for obj in list(bpy.data.objects):
        if obj.type not in ('MESH', 'ARMATURE'):
            bpy.data.objects.remove(obj, do_unlink=True)
    bottom = min((old_world[o.name] @ v.co).z for o in meshes for v in o.data.vertices)
    transform = Matrix.Translation((0, 0, -bottom*8)) @ Matrix.Scale(8, 4) @ Matrix.Rotation(math.pi/2, 4, 'Z')
    arm.data.transform(transform @ old_world[arm.name])
    arm.matrix_world = Matrix.Identity(4)
    arm.name = 'MSR_Textured_Horse_Rig'
    arm['msr_export'], arm['msr_body_bone'] = True, 'body'
    for obj in meshes:
        obj.data.transform(transform @ old_world[obj.name])
        obj.parent = arm
        obj.matrix_parent_inverse = Matrix.Identity(4)
        obj.matrix_basis = Matrix.Identity(4)
        obj['msr_export'] = True
    for old, new in NAMES.items():
        arm.data.bones[old].name = new
    # Parent/armature rename generally propagates automatically. Explicitly
    # repair any groups left using the downloaded file's old bone names.
    for obj in meshes:
        for group in obj.vertex_groups:
            if group.name in NAMES:
                group.name = NAMES[group.name]
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    for name in ('hind_L_upper', 'hind_R_upper', 'tail'):
        arm.data.edit_bones[name].parent = arm.data.edit_bones['body']
        arm.data.edit_bones[name].use_connect = False
    bpy.ops.object.mode_set(mode='OBJECT')
    for bone in arm.pose.bones:
        for constraint in list(bone.constraints):
            bone.constraints.remove(constraint)
        bone.rotation_mode = 'QUATERNION'

    # Object names are misleading: BezierCurve occupies the neck/head, while
    # BezierCurve.005 is the rear tail. Check anatomical bounds after transform.
    body, mane, tail = bpy.data.objects['Plane'], bpy.data.objects['BezierCurve'], bpy.data.objects['BezierCurve.005']
    assert min(v.co.x for v in mane.data.vertices)>0, 'Mane must be on the forward neck'
    assert max(v.co.x for v in tail.data.vertices)<0, 'Tail must be at the rear'
    eyes = [bpy.data.objects['Sphere'], bpy.data.objects['Sphere.002']]
    body.name, mane.name, tail.name = 'Horse_body', 'Horse_mane', 'Horse_tail'
    body_mat = material('Horse body original diffuse', (.3,.2,.1), 'HorseMain4k00.png')
    hair_mat = material('Horse hair original diffuse', (.2,.13,.05), 'Hair12Main2k.png', True)
    eye_mat = material('Original dark brown eye swatch', (.018,.009,.003))
    for obj, mat in [(body,body_mat), (mane,hair_mat), (tail,hair_mat), *[(o,eye_mat) for o in eyes]]:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        for polygon in obj.data.polygons:
            polygon.material_index = 0
            polygon.use_smooth = True
        if not any(m.type == 'ARMATURE' for m in obj.modifiers):
            obj.modifiers.new('Native horse attachment', 'ARMATURE').object = arm

    def rigid(obj, assignments):
        obj.vertex_groups.clear()
        groups = {name: obj.vertex_groups.new(name=name) for name in sorted(set(assignments))}
        for i, name in enumerate(assignments):
            groups[name].add([i], 1.0, 'REPLACE')
    # Dominant source weights are necessary for the deployed v10 renderer.
    weights = {g.index:g.name for g in body.vertex_groups}
    chosen, retained = [], []
    for vertex in body.data.vertices:
        candidates = sorted(((g.weight, weights[g.group]) for g in vertex.groups
                             if weights[g.group] in arm.data.bones), reverse=True)
        assert candidates, 'Unweighted original body vertex'
        chosen.append(candidates[0][1])
        retained.append(candidates[0][0]/sum(w for w,_ in candidates))
    rigid(body, chosen)
    def nearest(point, names):
        def distance(name):
            bone = arm.data.bones[name]
            a, b = bone.head_local, bone.tail_local
            direction = b-a
            t = max(0, min(1, (point-a).dot(direction)/direction.length_squared))
            return (point-(a+t*direction)).length_squared
        return min(names, key=distance)
    skin = [(v.co, chosen[v.index]) for v in body.data.vertices
            if chosen[v.index] in ('neck','head','body')]
    tree = KDTree(len(skin))
    for i,(point,_) in enumerate(skin):
        tree.insert(point,i)
    tree.balance()
    # Hair follows the nearest authored skin segment, including the source
    # head/neck weight boundary; proximity to a long bone is insufficient.
    rigid(mane, [skin[tree.find(v.co)[1]][1] for v in mane.data.vertices])
    rigid(tail, [nearest(v.co, ('tail','tail_tip')) for v in tail.data.vertices])
    for eye in eyes:
        rigid(eye, ['head']*len(eye.data.vertices))
        # Original eye spheres have 960 triangles each. A conservative collapse
        # leaves their silhouette intact while reducing tiny runtime geometry.
        dec = eye.modifiers.new('Eye geometry economy', 'DECIMATE')
        dec.ratio = .18
        bpy.context.view_layer.objects.active = eye
        while eye.modifiers[0] != dec:
            bpy.ops.object.modifier_move_up(modifier=dec.name)
        bpy.ops.object.modifier_apply(modifier=dec.name)

    leather = material('Original saddle brown leather', (.095,.035,.013))
    leather_edge = material('Original saddle dark edging', (.035,.016,.007))
    cloth = material('Original sage wool saddlecloth', (.11,.155,.065))
    iron = material('Original tack iron', (.14,.14,.12))
    brass = material('Original tack brass', (.35,.20,.055))
    tack = []
    def mesh(name, points, faces, mat, bone='body', smooth=False):
        data = bpy.data.meshes.new(name)
        data.from_pydata(points, [], faces)
        data.update()
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.data.materials.append(mat)
        obj.parent = arm
        obj.matrix_parent_inverse = Matrix.Identity(4)
        obj['msr_export'] = True
        rigid(obj, [bone]*len(points))
        obj.modifiers.new('Horse tack attachment', 'ARMATURE').object = arm
        for poly in data.polygons:
            poly.use_smooth = smooth
        tack.append(obj)
        return obj
    def tube(name, points, radius, mat, bone='body', sides=6):
        p = [Vector(v) for v in points]
        verts, faces = [], []
        for i, center in enumerate(p):
            tangent = (p[min(i+1,len(p)-1)]-p[max(0,i-1)]).normalized()
            side = tangent.cross(Vector((0,1,0)))
            if side.length < .01:
                side = tangent.cross(Vector((1,0,0)))
            side.normalize()
            other = tangent.cross(side).normalized()
            for j in range(sides):
                t = j*math.tau/sides
                verts.append(tuple(center+radius*(math.cos(t)*side+math.sin(t)*other)))
        for i in range(len(p)-1):
            for j in range(sides):
                k = i*sides+j
                faces.append((k, i*sides+(j+1)%sides, (i+1)*sides+(j+1)%sides, k+sides))
        faces += [tuple(reversed(range(sides))), tuple((len(p)-1)*sides+j for j in range(sides))]
        return mesh(name, verts, faces, mat, bone, True)
    def panel(name, points, mat, thickness=.4):
        p = [tuple(v) for v in points]
        n = len(p)
        verts = p+[(x,y,z-thickness) for x,y,z in p]
        faces = [tuple(range(n)), tuple(reversed(range(n,2*n)))]
        faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
        return mesh(name, verts, faces, mat)
    surface = BVHTree.FromPolygons([v.co for v in body.data.vertices],
                                  [list(p.vertices) for p in body.data.polygons])
    def blanket_z(x,y):
        hit = surface.ray_cast(Vector((x,y,100)), Vector((0,0,-1)), 100)[0]
        if hit and hit.z>40:
            return hit.z+1.15
        # At a narrow flank, drape beyond the nearest supported edge rather
        # than cutting a flat panel through the body or making a wing.
        for offset in (.5,1,1.5,2,3,4,5):
            inner_y = math.copysign(max(0,abs(y)-offset),y)
            hit = surface.ray_cast(Vector((x,inner_y,100)),Vector((0,0,-1)),100)[0]
            if hit and hit.z>40:
                return hit.z+1.15-offset*1.7
        raise ValueError('No body support beneath saddlecloth')
    xs = list(range(-18,17))
    ys = [i*1.0 for i in range(-13,14)]
    def cloth_y(y):
        # The lower flank normals are almost horizontal: vertical clearance
        # alone can still cut a triangle through the body between sample rays.
        return y+math.copysign(.6*max(0,min(1,(abs(y)-9)/3)),y)
    points = [(x,cloth_y(y),blanket_z(x,y)) for x in xs for y in ys]
    faces = []
    for i in range(len(xs)-1):
        for j in range(len(ys)-1):
            k=i*len(ys)+j
            faces.append((k,k+len(ys),k+len(ys)+1,k+1))
    mesh('Original contoured saddle blanket', points, faces, cloth, smooth=True)
    for y in (-13,13):
        tube('Wool blanket edge', [(x,cloth_y(y),blanket_z(x,y)+.12) for x in xs], .25, leather_edge)
    seat_profile = [(-14,67.1),(-10,65.6),(-4,64.65),(2,64.65),(8,65.3),(12,67.1)]
    def seat_height(x,y):
        for (a,za),(b,zb) in zip(seat_profile,seat_profile[1:]):
            if a<=x<=b:
                z=za+(zb-za)*(x-a)/(b-a)+.6*(abs(y)/8)**2
                return max(z,blanket_z(x,y)+.8)
        raise ValueError('Seat coordinate outside profile')
    # A closed padded tree fills the gap between the seat and contoured cloth.
    # The former open seat surface and arch outlines looked suspended in air.
    seat_x=list(range(-14,13)); seat_y=list(range(-8,9,2)); row=len(seat_y)
    upper=[(x,y,seat_height(x,y)) for x in seat_x for y in seat_y]
    lower=[(x,y,blanket_z(x,y)+.25) for x in seat_x for y in seat_y]
    n=len(upper); verts=upper+lower
    quads=[(i*row+j,(i+1)*row+j,(i+1)*row+j+1,i*row+j+1)
           for i in range(len(seat_x)-1) for j in range(row-1)]
    faces=quads+[tuple(n+k for k in reversed(q)) for q in quads]
    perimeter=([i*row for i in range(len(seat_x))]+
               [(len(seat_x)-1)*row+j for j in range(1,row)]+
               [i*row+row-1 for i in range(len(seat_x)-2,-1,-1)]+
               [j for j in range(row-2,0,-1)])
    faces += [(a,a+n,b+n,b) for a,b in zip(perimeter,perimeter[1:]+perimeter[:1])]
    mesh('Original padded leather seat and tree',verts,faces,leather,smooth=True)
    def raised_seat(name,arc,base_x,radius):
        lower=[(base_x,y,seat_height(base_x,y)-.9) for _,y,_ in arc]
        strip=lower+arc; count=len(arc); size=len(strip)
        points=[(x+dx,y,z) for dx in (-.6,.6) for x,y,z in strip]
        quads=[(i,i+1,count+i+1,count+i) for i in range(count-1)]
        faces=[tuple(reversed(q)) for q in quads]+[tuple(size+k for k in q) for q in quads]
        perimeter=list(range(count))+list(range(size-1,count-1,-1))
        faces += [(a,b,b+size,a+size) for a,b in zip(perimeter,perimeter[1:]+perimeter[:1])]
        mesh(name+' leather support',points,faces,leather,smooth=True)
        tube(name,arc,radius,leather)
    raised_seat('Raised rear cantle',[(-14,-8,67),(-15,-5,70),(-15,0,71),(-15,5,70),(-14,8,67)],-14,1.1)
    raised_seat('Front saddle pommel',[(12,-7,67),(13,-4,69.5),(13,0,70.5),(13,4,69.5),(12,7,67)],12,.9)
    for sign in (-1,1):
        skirt_x, skirt_y = list(range(-12,11)), [6+i*.5 for i in range(13)]
        skirt = [(x,sign*y,blanket_z(x,sign*y)+.65) for x in skirt_x for y in skirt_y]
        row=len(skirt_y)
        mesh('Original curved saddle skirt',skirt,
             [(i*row+j,(i+1)*row+j,(i+1)*row+j+1,i*row+j+1)
              for i in range(len(skirt_x)-1) for j in range(row-1)],leather,smooth=True)
        tube('Girth strap', [(0,sign*12,61),(0,sign*15.7,48),(0,sign*12,36),(0,0,34.5)], .75, leather_edge)
        tube('Stirrup leather', [(3,sign*10,65),(4,sign*18,52),(4,sign*21,38)], .65, leather)
        tube('Stirrup iron', [(4,sign*21,39),(1,sign*22,35),(1,sign*22,31),
                              (8,sign*22,31),(8,sign*22,35),(4,sign*21,39)], .55, iron)
        tube('Small saddle brass fitting', [(-10,sign*y,blanket_z(-10,sign*y)+.9)
                                           for y in (8.3,9)], .75, brass)
    tube('Bridle noseband', [(60,-4.5,48.5),(63,-3,47),(64,0,46.5),(63,3,47),(60,4.5,48.5),
                            (59.5,0,51.5),(60,-4.5,48.5)], .45, leather_edge, 'head')
    for sign in (-1,1):
        tube('Bridle headstall', [(60,sign*4.5,48.5),(56,sign*5,61),(53,sign*4.5,71.5)], .4, leather, 'head')

    bones = []
    def add(b):
        if b.name in [v.name for v in bones]:
            return
        if b.parent:
            add(b.parent)
        bones.append(b)
    for b in arm.data.bones:
        add(b)
    rest = {b.name:b.matrix_local.copy() for b in bones}
    foot_points = [(v.co.copy(), chosen[v.index]) for v in body.data.vertices
                   if v.co.z<8 and chosen[v.index].endswith('_lower')]
    assert len(foot_points)>20
    arm.animation_data_clear()
    arm.animation_data_create()
    root_offsets = {}
    pose_errors = {}
    def pose(kind, frame, count):
        t = frame/(count-1)*math.tau
        angles = {b.name:0. for b in bones}
        offsets = Vector((0,0,0))
        if kind == 'idle':
            angles.update(neck=.012*math.sin(t),head=.012*math.sin(t+.5),tail=.025*math.sin(t),tail_tip=.04*math.sin(t+.4))
        else:
            gallop = kind == 'gallop'
            angles['body'] = .018*math.sin(t) if gallop else .004*math.sin(t*2)
            angles['neck'] = (.045 if gallop else .022)*math.sin(t+.4)
            angles['head'] = -.7*angles['neck']
            angles['tail'] = -.12+.045*math.sin(t) if gallop else .025*math.sin(t)
            angles['tail_tip'] = -.08 if gallop else .025*math.sin(t+.5)
            phases = {'front_L':0,'hind_R':math.pi/2,'front_R':math.pi,'hind_L':math.pi*1.5}
            if gallop:
                phases = {'front_L':0,'front_R':.55,'hind_L':math.pi,'hind_R':math.pi+.55}
            for prefix, phase in phases.items():
                q=t+phase
                lift=max(0, math.cos(q))
                angles[prefix+'_upper']=(.44 if gallop else .23)*math.sin(q)
                angles[prefix+'_mid']=(-.62 if gallop else -.34)*lift
                angles[prefix+'_lower']=(.52 if gallop else .28)*lift
        matrices = {}
        for bone in bones:
            r = rest[bone.name]
            if bone.parent:
                p = rest[bone.parent.name]
                local = p.inverted() @ r
                basis = p.to_quaternion().to_matrix().to_4x4()
                delta = basis.inverted() @ Matrix.Rotation(angles[bone.name],4,'Y') @ basis
                matrices[bone.name] = matrices[bone.parent.name] @ Matrix.Translation(local.translation) @ delta @ local.to_quaternion().to_matrix().to_4x4()
            else:
                matrices[bone.name] = Matrix.Translation(r.translation+offsets) @ Matrix.Rotation(angles[bone.name],4,'Y') @ r.to_quaternion().to_matrix().to_4x4()
        floor = min((matrices[name] @ rest[name].inverted() @ p).z for p,name in foot_points)
        adjust = .12-floor if kind == 'walk' or floor<.12 else 0
        for name in matrices:
            matrices[name].translation.z += adjust
        return matrices, adjust
    for kind, count, fps in SEQUENCES:
        action = bpy.data.actions.new(kind)
        action.use_fake_user = True
        arm.animation_data.action = action
        action['fps'], action['loop'] = fps, True
        corrections = []
        max_pose_error = 0
        for frame in range(count):
            scene = bpy.context.scene
            scene.frame_set(frame+1)
            matrices, adjust = pose(kind, frame, count)
            corrections.append(adjust)
            for bone in bones:
                pb = arm.pose.bones[bone.name]
                if bone.parent:
                    local_rest = rest[bone.parent.name].inverted() @ rest[bone.name]
                    local_pose = matrices[bone.parent.name].inverted() @ matrices[bone.name]
                else:
                    local_rest, local_pose = rest[bone.name], matrices[bone.name]
                pb.matrix_basis = local_rest.inverted() @ local_pose
                pb.keyframe_insert('location',frame=frame+1)
                pb.keyframe_insert('rotation_quaternion',frame=frame+1)
            bpy.context.view_layer.update()
            for bone in bones:
                actual = arm.pose.bones[bone.name].matrix
                expected = matrices[bone.name]
                max_pose_error = max(max_pose_error,max(abs(actual[r][c]-expected[r][c]) for r in range(4) for c in range(4)))
        assert max_pose_error < .002, ('Baked pose differs from intended transforms',kind,max_pose_error)
        pose_errors[kind] = max_pose_error
        root_offsets[kind] = [min(corrections),max(corrections)]
        # Bake frame-exact native poses, with linear interpolation between them.
        if action.slots:
            for layer in action.layers:
                for strip in layer.strips:
                    for channelbag in strip.channelbags:
                        for curve in channelbag.fcurves:
                            for key in curve.keyframe_points:
                                key.interpolation = 'LINEAR'
    arm.animation_data.action = bpy.data.actions['idle']
    scene = bpy.context.scene
    scene.frame_set(1)
    scene.render.fps = 20
    scene.frame_start, scene.frame_end = 1, 41
    # Keep a small original studio setup in the editable file, excluded by tags.
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.resolution_x, scene.render.resolution_y = 1280, 960
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    world = bpy.data.worlds.new('Horse preview neutral world')
    world.use_nodes=True
    world.node_tree.nodes['Background'].inputs['Color'].default_value=(.23,.25,.28,1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value=.65
    scene.world = world
    target=Vector((5,0,39))
    for name, p, energy, size in [('Key',(70,-120,170),260000,100),('Fill',(-100,-40,100),150000,100),('Rim',(20,100,150),200000,90)]:
        light=bpy.data.lights.new(name,'AREA')
        light.energy, light.size = energy, size
        obj=bpy.data.objects.new(name,light)
        scene.collection.objects.link(obj)
        obj.location=p
        obj.rotation_euler=(target-obj.location).to_track_quat('-Z','Y').to_euler()
    camera_data=bpy.data.cameras.new('Converted horse preview')
    camera=bpy.data.objects.new('Converted horse preview',camera_data)
    scene.collection.objects.link(camera)
    scene.camera=camera
    camera_data.type, camera_data.ortho_scale='ORTHO',148
    camera.location=(130,-170,91)
    camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
    # The old file also references unavailable photographic work references;
    # they are unused by the rebuilt materials and must not break packaging.
    for image in list(bpy.data.images):
        if image.name != 'Render Result' and not image.size[0]:
            bpy.data.images.remove(image, do_unlink=True)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(output), compress=True)
    scene.render.filepath=str(output.with_name('prepared-horse-preview.png'))
    bpy.ops.render.render(write_still=True)
    # Read-only in-memory side frames make rigid limb deformation reviewable.
    camera.location=(5,-190,48)
    camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
    for kind, frames in [('walk',(1,7,13,19)),('gallop',(1,6,11,16))]:
        arm.animation_data.action=bpy.data.actions[kind]
        for frame in frames:
            scene.frame_set(frame)
            scene.render.filepath=str(output.with_name(f'{kind}-{frame:02}.png'))
            bpy.ops.render.render(write_still=True)
    report={'source_sha256':SOURCE_SHA,'source_saved':False,'prepared_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            'blender':bpy.app.version_string,'forward_axis':'+X','scale':8,'feet_base':0,
            'bones':len(bones),'source_to_native_names':NAMES,'dominant_body_weight_mean':sum(retained)/len(retained),
            'mane_tail_eyes_attached':True,'original_tack_objects':len(tack),'root_floor_correction_ranges':root_offsets,
            'max_baked_pose_matrix_errors':pose_errors,
            'sequences':[{'index':i,'name':name,'frames':count,'fps':fps,'loop':True} for i,(name,count,fps) in enumerate(SEQUENCES)],
            'limitations':['Original authored procedural gait loops, not motion capture.','Native rigid weights reduce the source soft-skin deformation.','The seated rider follows existing game code; native fit requires inspection.']}
    output.with_name('rig-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    assert hashlib.sha256(source.read_bytes()).hexdigest()==SOURCE_SHA
    print('HORSE_PREPARED '+json.dumps(report))


if __name__ == '__main__':
    main(args())
