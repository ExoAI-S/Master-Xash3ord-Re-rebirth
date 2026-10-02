"""Export the repaired CC0 horse to conservative GoldSrc v10 SMD sources.

Run in Blender with downloaded scripts disabled. Pillow is only used by a
separate, explicitly selected Python interpreter to quantize original diffuse
pixels into indexed BMPs. This script never saves or modifies the input .blend.

blender --background --disable-autoexec --python export_horse.py -- \
    --input prepared-horse.blend --output export --texture-python python.exe

Compile export/horse.qc with pxstudiomdl. Every permanent $body submodel has at
most 4096 triangles: even an unoptimized triangle list submits at most 12288
vertices, below the old renderer's 16384-entry arrays. No weighted/PBR extension
is required. The dominant source bone is used for native one-influence skinning.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys


MAX_TRIANGLES_PER_SUBMODEL = 4096
MAX_UNIQUE_VERTICES_PER_SUBMODEL = 4000
SEQUENCES = (("idle", 41, 20), ("walk", 25, 24), ("gallop", 21, 30))
SADDLE_WORLD = (-1.8, 0.0, 64.6)


def palette_worker(spec_path):
    """Preserve encoded diffuse colors; reserve palette index255 for alpha."""
    from PIL import Image, ImageChops, ImageStat
    specs = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    results = []
    for spec in specs:
        output = Path(spec["output"])
        if "source" in spec:
            original = Image.open(spec["source"]).convert("RGBA")
        else:
            original = Image.new("RGBA", (16, 16), tuple(spec["color"]) + (255,))
        original_size = list(original.size)
        limit = spec.get("size", 1024)
        if max(original.size) > limit:
            original.thumbnail((limit, limit), Image.Resampling.LANCZOS)
        # Studio textures use powers of two. Eye/solid swatches remain small.
        size = tuple(min(limit, 2 ** math.ceil(math.log2(max(1, n)))) for n in original.size)
        original = original.resize(size, Image.Resampling.LANCZOS)
        rgb = original.convert("RGB")
        masked = spec.get("masked", False)
        mask = original.getchannel("A").point(lambda x: 255 if x >= 128 else 0)
        opaque_count = sum(mask.histogram()[128:])
        if not opaque_count:
            raise ValueError("Texture has no opaque pixels: " + spec["name"])
        if masked:
            average = tuple(round(v) for v in ImageStat.Stat(rgb, mask).mean)
            palette_source = Image.composite(rgb, Image.new("RGB", size, average), mask)
        else:
            palette_source = rgb
        indexed = palette_source.quantize(colors=255 if masked else 256,
                                         method=Image.Quantize.MEDIANCUT,
                                         dither=Image.Dither.NONE)
        palette = (indexed.getpalette() or [])[:768]
        palette += [0] * (768 - len(palette))
        if masked:
            palette[765:768] = [0, 0, 255]
        # Pillow otherwise emits a one-entry palette for solid tack swatches;
        # native texture palettes always contain all 256 entries.
        indexed.putpalette(palette)
        if masked:
            indexed.paste(255, mask=ImageChops.invert(mask))
        indexed.save(output, format="BMP")
        difference = ImageChops.difference(rgb, indexed.convert("RGB"))
        stats = ImageStat.Stat(difference, mask if masked else None)
        results.append({"name": spec["name"], "file": output.name,
                        "original_size": original_size, "size": list(size),
                        "indexed_colors": 256, "masked": masked,
                        "opaque_pixels": opaque_count,
                        "transparent_pixels": size[0]*size[1]-opaque_count if masked else 0,
                        "mean_absolute_rgb_error": [round(v, 4) for v in stats.mean],
                        "rms_rgb_error": [round(v, 4) for v in stats.rms],
                        "sha256": hashlib.sha256(output.read_bytes()).hexdigest()})
    Path(spec_path).with_name("texture-report.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8")


def arguments():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--texture-python", default=shutil.which("python.exe") or shutil.which("python"))
    parser.add_argument("--model-name", default="plains_horse.mdl")
    return parser.parse_args(argv)


def export(args):
    import bpy
    from mathutils import Vector
    args.input = args.input.resolve()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    texture_sources = args.output / "texture-sources"
    texture_sources.mkdir(exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(args.input), load_ui=False, use_scripts=False)
    arms = [ob for ob in bpy.data.objects if ob.type == "ARMATURE" and ob.get("msr_export", True)]
    if len(arms) != 1:
        raise ValueError("Expected one export armature")
    arm = arms[0]
    objects = sorted((ob for ob in bpy.data.objects if ob.type == "MESH" and ob.get("msr_export", False)),
                     key=lambda ob: ob.name)
    if not objects:
        raise ValueError("No meshes tagged msr_export=True")
    bones = []
    def add_bone(bone):
        if bone in bones:
            return
        if bone.parent:
            add_bone(bone.parent)
        bones.append(bone)
    for bone in arm.data.bones:
        add_bone(bone)
    if len(bones) > 128:
        raise ValueError("Native renderer supports at most 128 bones")
    ids = {b.name: i for i, b in enumerate(bones)}
    rest = [arm.matrix_world @ b.matrix_local for b in bones]
    for matrix in rest:
        if max(abs(v-1) for v in matrix.to_scale()) > .0001:
            raise ValueError("Apply armature scale before exporting")
    for bone in bones:
        if len(bone.name.encode("ascii")) > 31:
            raise ValueError("Native bone name exceeds 31 bytes: " + bone.name)
    body_bone = arm.get("msr_body_bone", "body")
    if body_bone not in ids:
        raise ValueError("Missing body bone " + body_bone)
    materials = {}
    texture_specs = []
    def texture_for(material):
        key = material.name if material else "unassigned"
        if key in materials:
            return materials[key]
        image = None
        color = (.1, .045, .02, 1)
        alpha_link = False
        if material and material.use_nodes:
            shader = next((n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if shader:
                color = tuple(shader.inputs["Base Color"].default_value)
                for link in shader.inputs["Base Color"].links:
                    if link.from_node.type == "TEX_IMAGE":
                        image = link.from_node.image
                alpha_link = bool(shader.inputs["Alpha"].links)
        elif material:
            color = tuple(material.diffuse_color)
        index = len(texture_specs)
        stem = "horse_tex_%02d" % index
        spec = {"name": key, "output": str(args.output / (stem + ".bmp")),
                "size": 1024 if image else 16, "masked": alpha_link}
        if image:
            if not image.size[0] or not image.size[1]:
                raise ValueError("Missing diffuse image " + image.name)
            if image.packed_file:
                # Packed PNG/BMP bytes preserve source sRGB values exactly.
                encoded = bytes(image.packed_file.data)
                extension = ".png" if encoded[:8] == b"\x89PNG\r\n\x1a\n" else ".bmp" if encoded[:2] == b"BM" else ".bin"
                source = texture_sources / (stem + extension)
                source.write_bytes(encoded)
            else:
                source = Path(bpy.path.abspath(image.filepath))
                if not source.is_file():
                    raise ValueError("Unpacked image does not exist: " + image.name)
            spec["source"] = str(source)
            spec["source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        else:
            def srgb(v):
                v = max(0, min(1, v))
                return round(255 * (12.92*v if v <= .0031308 else 1.055*v**(1/2.4)-.055))
            spec["color"] = [srgb(v) for v in color[:3]]
        texture_specs.append(spec)
        materials[key] = stem + ".bmp"
        return materials[key]
    def write_nodes(f):
        f.write("version 1\nnodes\n")
        for i, b in enumerate(bones):
            f.write('%d "%s" %d\n' % (i, b.name, ids[b.parent.name] if b.parent else -1))
        f.write("end\nskeleton\n")
    def write_frame(f, frame, matrices):
        f.write("time %d\n" % frame)
        for i, b in enumerate(bones):
            local = matrices[ids[b.parent.name]].inverted() @ matrices[i] if b.parent else matrices[i]
            translation, rotation, scale = local.decompose()
            if max(abs(v-1) for v in scale) > .0005:
                raise ValueError("Native animation contains unsupported bone scale")
            angles = rotation.to_euler("XYZ")
            f.write("%d %.8f %.8f %.8f %.8f %.8f %.8f\n" % (i, *translation, *angles))
    previous_pose = arm.data.pose_position
    arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    bodyparts = []
    bounds = []
    rigid_weights = {"vertices": 0, "multi_influence_vertices": 0,
                     "unweighted_vertices": 0, "retained_weight_sum": 0.0}
    for obj in objects:
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
        try:
            mesh.calc_loop_triangles()
            normal_matrix = obj.matrix_world.to_3x3().inverted().transposed()
            group_names = {group.index: group.name for group in obj.vertex_groups}
            vertex_bones = []
            for vertex in mesh.vertices:
                weights = [(g.weight, ids[group_names[g.group]]) for g in vertex.groups
                           if group_names.get(g.group) in ids and g.weight > .00001]
                rigid_weights["vertices"] += 1
                if not weights:
                    rigid_weights["unweighted_vertices"] += 1
                    raise ValueError("Unweighted export vertex in " + obj.name)
                weights.sort(reverse=True)
                vertex_bones.append(weights[0][1])
                rigid_weights["multi_influence_vertices"] += len(weights) > 1
                rigid_weights["retained_weight_sum"] += weights[0][0]/sum(w for w, _ in weights)
            uv_layer = mesh.uv_layers.active
            corners = mesh.corner_normals
            current, unique, parts = [], set(), []
            for triangle in mesh.loop_triangles:
                if triangle.area < .0000001:
                    continue
                vertices = {mesh.loops[li].vertex_index for li in triangle.loops}
                if current and (len(current) >= MAX_TRIANGLES_PER_SUBMODEL or
                                len(unique | vertices) > MAX_UNIQUE_VERTICES_PER_SUBMODEL):
                    parts.append((current, unique))
                    current, unique = [], set()
                current.append(triangle)
                unique.update(vertices)
            if current:
                parts.append((current, unique))
            for triangles, unique in parts:
                index = len(bodyparts)
                name = "horse_part_%02d" % index
                with (args.output / (name + ".smd")).open("w", newline="\n", encoding="ascii") as f:
                    write_nodes(f)
                    write_frame(f, 0, rest)
                    f.write("end\ntriangles\n")
                    for triangle in triangles:
                        material = mesh.materials[triangle.material_index] if mesh.materials else None
                        f.write(texture_for(material) + "\n")
                        for li in triangle.loops:
                            vi = mesh.loops[li].vertex_index
                            point = obj.matrix_world @ mesh.vertices[vi].co
                            normal = (normal_matrix @ corners[li].vector).normalized()
                            uv = uv_layer.data[li].uv if uv_layer else Vector((.5, .5))
                            bounds.append(tuple(point))
                            f.write("%d %.8f %.8f %.8f %.8f %.8f %.8f %.8f %.8f\n" %
                                    (vertex_bones[vi], *point, *normal, *uv))
                    f.write("end\n")
                bodyparts.append({"name": name, "source_mesh": obj.name, "triangles": len(triangles),
                                  "unique_source_vertices": len(unique),
                                  "worst_case_submitted_vertices": len(triangles)*3})
        finally:
            evaluated.to_mesh_clear()
    if len(bodyparts) > 32:
        raise ValueError("More than 32 native bodyparts")
    arm.data.pose_position = "POSE"
    if not arm.animation_data:
        raise ValueError("Export rig has no animations")
    previous_action = arm.animation_data.action
    for name, count, fps in SEQUENCES:
        action = bpy.data.actions.get(name)
        if not action:
            raise ValueError("Missing native action " + name)
        arm.animation_data.action = action
        with (args.output / ("horse_" + name + ".smd")).open("w", newline="\n", encoding="ascii") as f:
            write_nodes(f)
            for frame in range(count):
                bpy.context.scene.frame_set(frame + 1)
                bpy.context.view_layer.update()
                matrices = [arm.matrix_world @ arm.pose.bones[b.name].matrix for b in bones]
                write_frame(f, frame, matrices)
            f.write("end\n")
    arm.animation_data.action = previous_action
    arm.data.pose_position = previous_pose
    attachment = rest[ids[body_bone]].inverted() @ Vector(SADDLE_WORLD)
    lo = [min(p[i] for p in bounds) for i in range(3)]
    hi = [max(p[i] for p in bounds) for i in range(3)]
    qc = ['// CC0 horse conversion; +X forward, conservative native v10 format.',
          '$modelname "%s"' % args.model_name, '$cd "."', '$cdtexture "."',
          '$scale 1.0', '$gamma 1.8', '$origin 0 0 0 -90']
    qc += ['$body "%s" "%s"' % (p["name"], p["name"]) for p in bodyparts]
    qc.append('$attachment 0 "%s" %.8f %.8f %.8f' % (body_bone, *attachment))
    qc += ['$texrendermode "%s" masked' % Path(s["output"]).name for s in texture_specs if s["masked"]]
    qc += ['$sequence "%s" "horse_%s" fps %d loop' % (name, name, fps) for name, _, fps in SEQUENCES]
    qc += ['$bbox ' + ' '.join('%.4f' % v for v in lo+hi), '$cbox ' + ' '.join('%.4f' % v for v in lo+hi)]
    (args.output / "horse.qc").write_text("\n".join(qc) + "\n", encoding="ascii")
    spec_path = args.output / "texture-specs.json"
    spec_path.write_text(json.dumps(texture_specs, indent=2) + "\n", encoding="utf-8")
    if not args.texture_python:
        raise ValueError("Select --texture-python with Pillow installed")
    subprocess.run([args.texture_python, str(Path(__file__).resolve()), "--palette-worker", str(spec_path)], check=True)
    rigid_weights["mean_retained_weight"] = rigid_weights.pop("retained_weight_sum")/rigid_weights["vertices"]
    report = {"input_blend": args.input.name, "input_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
              "input_modified": False, "blender": bpy.app.version_string,
              "format": "GoldSrc v10, one bone influence, original diffuse indexed BMP",
              "bones": len(bones), "bodyparts": bodyparts,
              "triangles": sum(p["triangles"] for p in bodyparts), "bounds": {"min": lo, "max": hi},
              "saddle_attachment": {"index": 0, "bone": body_bone, "local": list(attachment), "world": SADDLE_WORLD},
              "sequences": [{"index": i, "name": name, "frames": count, "fps": fps, "loop": True}
                            for i, (name, count, fps) in enumerate(SEQUENCES)],
              "rigid_weight_conversion": rigid_weights,
              "textures": json.loads((args.output / "texture-report.json").read_text()),
              "limitations": ["Normal/AO source images are intentionally omitted by the legacy diffuse renderer.",
                              "Single-influence native deformation requires native movement review.",
                              "Animation and gameplay rider positioning require separate runtime verification."]}
    (args.output / "export-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("TEXTURED_HORSE_EXPORT_COMPLETE " + json.dumps({"triangles": report["triangles"], "bones": report["bones"],
                                                         "bodyparts": len(bodyparts), "textures": len(texture_specs)}))


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--palette-worker":
        palette_worker(sys.argv[2])
    else:
        export(arguments())
