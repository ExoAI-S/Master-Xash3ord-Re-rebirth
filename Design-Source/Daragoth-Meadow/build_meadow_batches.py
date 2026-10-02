"""Bake frozen meadow grass placements into private, spatial studio batches.

Only the BSP entity lump is replaced. Terrain, collision, lighting, visibility,
textures, and ordered nongrass records remain untouched. No installed game is
written; the resulting assets and BSP still require independent and native QA.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import struct
import subprocess

from build_meadow_polish import BSP, Entity, format_entities, lump_hashes, transform_root

BASE_SHA = "e14b54e89f7a5870944c3759a3e8eda4e5e4b4ef962856b5ffbe52fe06da7b06"
PATCH_COUNT = 920
CELL_SIZE = 2560
PATCHES_PER_BODY = 11
TEXTURE = "meadow_grass_blades.bmp"
LIGHTING_ANCHOR_POLICY = "nearest_patch_to_grid_center_xy_then_index_ground_plus_64_z_rounded_4"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def smd_triangles(path):
    lines = path.read_text().splitlines()
    start = lines.index("triangles") + 1
    body = lines[start:lines.index("end", start)]
    header = lines[:start]
    if header != ["version 1", "nodes", '0 "root" -1', "end", "skeleton",
                  "time 0", "0 0 0 0 0 0 0", "end", "triangles"]:
        raise ValueError("Grass reference must have one neutral root bone")
    if len(body) % 4:
        raise ValueError("Incomplete source SMD triangles")
    triangles = []
    for i in range(0, len(body), 4):
        if body[i] != TEXTURE:
            raise ValueError("Unexpected grass material")
        vertices = []
        for line in body[i + 1:i + 4]:
            values = line.split()
            if len(values) != 9 or values[0] != "0":
                raise ValueError("Grass requires one bone influence and eight vertex values")
            vertex = tuple(map(float, values[1:]))
            if not all(math.isfinite(v) for v in vertex):
                raise ValueError("Nonfinite grass vertex")
            vertices.append(vertex)
        triangles.append(vertices)
    if len(triangles) != 336 or len({v[:3] for t in triangles for v in t}) != 336:
        raise ValueError("Expected frozen 336-triangle, 336-source-vertex grass patch")
    return header, triangles


def bake_vertex(vertex, placement, origin):
    pitch, roll = math.radians(placement["pitch"]), math.radians(placement["roll"])
    rotated = transform_root(vertex[:3], pitch, roll)
    position = tuple(placement["origin"][a] + rotated[a] - origin[a] for a in range(3))
    # A rigid rotation acts on normals without translation. Entity scale is one.
    normal = transform_root(vertex[3:6], pitch, roll)
    return (*position, *normal, *vertex[6:8])


def replay_error(compiled, expected):
    # Float32 can collapse distinct x coordinates without changing the vertices.
    # Match spatially rather than sorting floats lexicographically across ties.
    buckets = collections.defaultdict(list)
    for point in expected:
        buckets[tuple(math.floor(v / 0.004) for v in point)].append(point)
    error = 0.0
    for point in compiled:
        cell = tuple(math.floor(v / 0.004) for v in point)
        candidates = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    key = (cell[0]+dx, cell[1]+dy, cell[2]+dz)
                    for i, wanted in enumerate(buckets.get(key, ())):
                        distance = max(abs(a-b) for a,b in zip(point,wanted))
                        if distance <= 0.002:
                            candidates.append((distance, key, i))
        if not candidates:
            raise ValueError(f"Compiled vertex does not replay baked source: {point}")
        distance, key, i = min(candidates)
        buckets[key].pop(i)
        error = max(error, distance)
    if any(buckets.values()):
        raise ValueError("Baked source vertices missing from compiled model")
    return error


def model_check(path, expected_parts, expected_bounds, patch_flags=True):
    data = bytearray(path.read_bytes())
    if data[:4] != b"IDST" or struct.unpack_from("<i", data, 4)[0] != 10:
        raise ValueError("Expected GoldSrc studio version 10")
    if struct.unpack_from("<i", data, 72)[0] != len(data):
        raise ValueError("Compiled model length mismatch")
    bones, bone_at = struct.unpack_from("<2i", data, 140)
    if bones != 1 or struct.unpack_from("<6f", data, bone_at + 64) != (0, 0, 0, 0, 0, 0):
        raise ValueError("Compiled grass bone is not neutral")
    count, texture_at, _ = struct.unpack_from("<3i", data, 180)
    if count != 1:
        raise ValueError("Batch must retain one texture")
    flags, width, height, pixels_at = struct.unpack_from("<4i", data, texture_at + 64)
    if (width, height) != (512, 512) or not flags & 64 or flags & 4:
        raise ValueError("Grass texture dimensions, alpha, or lighting changed")
    if 255 not in data[pixels_at:pixels_at + width * height]:
        raise ValueError("Masked grass pixels missing")
    if patch_flags:
        flags |= 1
        struct.pack_into("<i", data, texture_at + 64, flags)
        path.write_bytes(data)
    elif not flags & 1:
        raise ValueError("Frozen source grass must retain scene-lit flatshade")
    texture_hash = hashlib.sha256(data[pixels_at:pixels_at + width * height + 768]).hexdigest()
    body_count, body_at = struct.unpack_from("<2i", data, 204)
    if body_count != len(expected_parts):
        raise ValueError("Permanent bodypart count changed")
    parts = []; compiled_points = []
    max_error = 0.0
    for i, expected in enumerate(expected_parts):
        _, models, _, model_at = struct.unpack_from("<64s3i", data, body_at + i * 76)
        if models != 1:
            raise ValueError("Every grass bodypart must remain permanently present")
        model = struct.unpack_from("<64sif10i", data, model_at)
        meshes, mesh_at, verts, vertex_bones, vertex_at = model[3:8]
        if not 0 < verts <= 4000 or any(data[vertex_bones + j] for j in range(verts)):
            raise ValueError("Compiled vertex or bone budget exceeded")
        compiled = [struct.unpack_from("<3f", data, vertex_at + j * 12) for j in range(verts)]
        compiled_points.extend(compiled)
        wanted = sorted(set(v[:3] for t in expected for v in t))
        if len(compiled) != len(wanted):
            raise ValueError("Compiled vertex count does not replay baked source")
        error = replay_error(compiled, wanted)
        max_error = max(max_error, error)
        if error > 0.002:
            raise ValueError(f"Compiled transform replay error: {error}")
        triangles = submitted = 0
        for j in range(meshes):
            ntri, commands, _, _, _ = struct.unpack_from("<5i", data, mesh_at + j * 20)
            triangles += ntri
            while True:
                n = struct.unpack_from("<h", data, commands)[0]
                commands += 2
                if not n:
                    break
                if abs(n) < 3:
                    raise ValueError("Invalid triangle command")
                submitted += abs(n)
                for k in range(abs(n)):
                    vertex, normal, _, _ = struct.unpack_from("<4h", data, commands + k * 8)
                    if not 0 <= vertex < verts or not 0 <= normal < model[8]:
                        raise ValueError("Invalid triangle command index")
                commands += abs(n) * 8
        if triangles != len(expected) or triangles > 4096 or submitted > 16384:
            raise ValueError("Compiled triangle or submitted-vertex budget exceeded")
        parts.append({"bodypart": i, "triangles": triangles, "vertices": verts,
                      "submitted_vertices": submitted, "compiled_position_error": error})
    seq_count, sequence_at = struct.unpack_from("<2i", data, 164)
    if seq_count != 1 or data[sequence_at:sequence_at + 32].split(b"\0", 1)[0] != b"idle":
        raise ValueError("Batch must retain one idle sequence")
    sequence_bounds = [list(struct.unpack_from("<3f", data, sequence_at + p)) for p in (96, 108)]
    if any(sequence_bounds[0][a] > expected_bounds[0][a] + 0.002 or
           sequence_bounds[1][a] < expected_bounds[1][a] - 0.002 for a in range(3)):
        raise ValueError("Compiled sequence bounds exclude grass")
    compiled_bounds = [[min(p[a] for p in compiled_points) for a in range(3)],
                       [max(p[a] for p in compiled_points) for a in range(3)]]
    if any(sequence_bounds[0][a] > compiled_bounds[0][a] + 0.0001 or
           sequence_bounds[1][a] < compiled_bounds[1][a] - 0.0001 for a in range(3)):
        raise ValueError("Compiled sequence bounds exclude actual compiled geometry")
    return {"bounds": expected_bounds, "compiled_sequence_bounds": sequence_bounds,
            "compiled_geometry_bounds": compiled_bounds,
            "bodyparts": parts, "texture_dimensions": [width, height], "texture_flags": flags,
            "texture_pixels_palette_sha256": texture_hash, "compiled_position_error": max_error,
            "bytes": len(data), "sha256": sha(path)}


def build(bsp_path, patch_report_path, grass_source, compiler, out):
    bsp_path, patch_report_path, grass_source, compiler, out = (
        p.resolve() for p in (bsp_path, patch_report_path, grass_source, compiler, out))
    target = out / "daragoth_meadow_batched.bsp"
    if target == bsp_path or out.is_relative_to(Path("C:/MSR").resolve()):
        raise ValueError("Use a private output distinct from the source and installed game")
    if any(part.lower() in ("runtime", "runtime-peer", "runtime-fresh", "game") for part in out.parts):
        raise ValueError("Batch outputs must not target a game runtime")
    paths = [bsp_path, patch_report_path, grass_source / "meadow_grass_patch_reference.smd",
             grass_source / "meadow_grass_patch_idle.smd", grass_source / TEXTURE,
             grass_source / "meadow_grass_patch.mdl", compiler,
             Path(__file__).with_name("build_meadow_polish.py"), Path(__file__).resolve()]
    hashes = {str(p): sha(p) for p in paths}
    report = json.loads(patch_report_path.read_text())
    if report["base_sha256"] != BASE_SHA or report["sha256"] != hashes[str(bsp_path)]:
        raise ValueError("Patch BSP/report do not match the approved frozen base")
    if report["grass_model_sha256"] != hashes[str(grass_source / "meadow_grass_patch.mdl")]:
        raise ValueError("Compiled source grass does not match patch report")
    base = Path(report["base_path"]).resolve()
    if sha(base) != BASE_SHA:
        raise ValueError("Approved base changed")
    paths.append(base); hashes[str(base)] = BASE_SHA
    placements = report["placements"]
    if len(placements) != PATCH_COUNT or collections.Counter(p["region"] for p in placements) != {"fields": 840, "valley": 80}:
        raise ValueError("Expected all 840 field and 80 valley placements")
    for p in placements:
        if p["kind"] != "grass" or p["yaw"] != 0 or not all(math.isfinite(v) for v in (*p["origin"], p["pitch"], p["roll"])):
            raise ValueError("Unexpected grass transform")
    header, triangles = smd_triangles(grass_source / "meadow_grass_patch_reference.smd")
    source_points = [v[:3] for t in triangles for v in t]
    source_bounds = [[min(p[a] for p in source_points) for a in range(3)],
                     [max(p[a] for p in source_points) for a in range(3)]]
    source_check = model_check(grass_source / "meadow_grass_patch.mdl", [triangles], source_bounds, False)
    idle = (grass_source / "meadow_grass_patch_idle.smd").read_text()
    if idle.splitlines() != ["version 1", "nodes", '0 "root" -1', "end", "skeleton", "time 0",
                            "0 0 0 0 0 0 0", "time 1", "0 0 0 0 0 0 0", "end"]:
        raise ValueError("Idle must retain two identical neutral frames")
    bsp = BSP.load(bsp_path); data = bsp_path.read_bytes()
    removed = {}
    kept = []
    pattern = re.compile(r"meadow_polish_grass_(\d{4})\Z")
    for entity in bsp.entities:
        match = pattern.fullmatch(entity.get("targetname", ""))
        if not match:
            kept.append(entity)
            continue
        index = int(match[1])
        if index in removed or index >= PATCH_COUNT or entity.classname != "env_model":
            raise ValueError("Unexpected or duplicate grass record")
        p = placements[index]
        expected_region = "daragoth" if p["region"] == "valley" else "daragoth_plains"
        if entity.get("model") != report["model_runtime_path"] or entity.get("msr_region") != expected_region:
            raise ValueError("Grass entity material/region does not match report")
        expected_angles = [p["pitch"], 0, p["roll"]]
        if any(abs(a-b) > 0.000001 for a,b in zip(map(float, entity.get("origin").split()),p["origin"])) or \
           any(abs(a-b) > 0.000001 for a,b in zip(map(float, entity.get("angles").split()),expected_angles)) or entity.get("scale") != "1":
            raise ValueError("Grass entity transform does not match report")
        removed[index] = entity
    if set(removed) != set(range(PATCH_COUNT)) or len(kept) != 960:
        raise ValueError("Expected exactly 920 grass and 960 ordered nongrass records")
    grouped = collections.defaultdict(list)
    for i, p in enumerate(placements):
        grouped[(p["region"], math.floor(p["origin"][0]/CELL_SIZE), math.floor(p["origin"][1]/CELL_SIZE))].append(i)
    batches = []
    for number, ((region, gx, gy), indices) in enumerate(sorted(grouped.items())):
        name = f"meadow_sector_{number:03d}"
        folder = out / "batches" / name; folder.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(grass_source / TEXTURE, folder / TEXTURE)
        (folder / "idle.smd").write_text(idle)
        grid_center = [(gx + 0.5)*CELL_SIZE, (gy + 0.5)*CELL_SIZE]
        anchor_index = min(indices, key=lambda i: (
            sum((placements[i]["origin"][a] - grid_center[a])**2 for a in range(2)), i))
        # Scene lighting is sampled at the entity origin. An empty point above
        # a grass patch avoids sampling inside nearby hills at the grid center.
        # bake_vertex subtracts this origin, preserving every world position.
        origin = [*placements[anchor_index]["origin"][:2],
                  round(placements[anchor_index]["terrain_ground_z"] + 64, 4)]
        parts = []; all_points = []
        for at in range(0, len(indices), PATCHES_PER_BODY):
            indices_part = indices[at:at + PATCHES_PER_BODY]
            baked = [[bake_vertex(v, placements[i], origin) for v in t] for i in indices_part for t in triangles]
            lines = list(header)
            for triangle in baked:
                lines.append(TEXTURE)
                lines.extend("0 " + " ".join(f"{v:.8f}" for v in vertex) for vertex in triangle)
                all_points.extend(v[:3] for v in triangle)
            lines.append("end")
            (folder / f"body_{len(parts):02d}.smd").write_text("\n".join(lines) + "\n")
            parts.append(baked)
        bounds = [[min(p[a] for p in all_points) for a in range(3)],
                  [max(p[a] for p in all_points) for a in range(3)]]
        bound_text = " ".join(f"{v:.8f}" for p in bounds for v in p)
        bodies = "\n".join(f'$body "grass_{i:02d}" "body_{i:02d}"' for i in range(len(parts)))
        qc = f'''// Frozen meadow patches baked with production stock renderer transforms.
$modelname "{name}.mdl"
$cd "."
$cdtexture "."
$scale 1
$gamma 1.8
$origin 0 0 0 -90
{bodies}
$sequence "idle" "idle" fps 12 loop
$bbox {bound_text}
$cbox {bound_text}
$texrendermode "{TEXTURE}" masked
'''
        (folder / f"{name}.qc").write_text(qc)
        result = subprocess.run([str(compiler), f"{name}.qc"], cwd=folder, capture_output=True, text=True)
        (folder / "compile.log").write_text(result.stdout + result.stderr)
        model_path = folder / f"{name}.mdl"
        if result.returncode or not model_path.is_file():
            raise RuntimeError(f"Batch {name} compilation failed; see {folder/'compile.log'}")
        checked = model_check(model_path, parts, bounds)
        if checked["texture_pixels_palette_sha256"] != source_check["texture_pixels_palette_sha256"]:
            raise ValueError("Compiled grass indexed pixels or full palette changed")
        runtime = f"models/plains/{name}.mdl"
        batches.append({"model_path": str(model_path), "model_runtime_path": runtime,
                        "origin": origin, "patch_indices": indices, "region": region,
                        "grid": [gx, gy], "patches": len(indices),
                        "lighting_anchor_patch_id": anchor_index,
                        "lighting_anchor_policy": LIGHTING_ANCHOR_POLICY, **checked})
        kept.append(Entity([["classname", "env_model"], ["model", runtime],
                            ["origin", " ".join(f"{v:.4f}" for v in origin)], ["angles", "0 0 0"],
                            ["sequence", "0"], ["framerate", "0"], ["dmg", "0"],
                            ["rendermode", "0"], ["renderamt", "255"], ["scale", "1"],
                            ["skin", "0"], ["body", "0"], ["targetname", name],
                            ["msr_region", "daragoth" if region == "valley" else "daragoth_plains"]]))
        print(f"Compiled {number+1}/{len(grouped)}: {name}, {len(indices)} patches, {len(parts)} bodyparts", flush=True)
    output = bytearray(data); output.extend(b"\0" * (-len(output) % 4))
    entity_at = len(output); entities = format_entities(kept); output.extend(entities)
    struct.pack_into("<2i", output, 4, entity_at, len(entities))
    before, after = lump_hashes(data), lump_hashes(output)
    if any(before[str(i)] != after[str(i)] for i in range(1,15)):
        raise ValueError("Non-entity BSP lump changed")
    if any(sha(p) != hashes[str(p)] for p in paths):
        raise ValueError("A frozen input changed during batch build")
    target.write_bytes(output)
    result = {"source_map_sha256": hashes[str(bsp_path)], "base_map_sha256": BASE_SHA,
              "output_sha256": sha(target), "source_report_sha256": hashes[str(patch_report_path)],
              "output_path": str(target), "source_path": str(bsp_path), "source_report_path": str(patch_report_path),
              "input_hashes": hashes, "batches": batches, "total_entities": len(kept), "patches": PATCH_COUNT,
              "batch_count": len(batches), "nongrass_entities": 960, "grid_size": CELL_SIZE,
              "lighting_anchor_policy": LIGHTING_ANCHOR_POLICY,
              "patches_per_bodypart": PATCHES_PER_BODY, "all_non_entity_lumps_identical": True,
              "non_entity_lump_hashes": {k:v for k,v in before.items() if k != "0"},
              "max_triangles_per_submodel": max(p["triangles"] for b in batches for p in b["bodyparts"]),
              "max_vertices_per_submodel": max(p["vertices"] for b in batches for p in b["bodyparts"]),
              "max_submitted_vertices_per_submodel": max(p["submitted_vertices"] for b in batches for p in b["bodyparts"]),
              "max_compiled_position_error": max(b["compiled_position_error"] for b in batches),
              "scope": "Private static grass batches; native network/render QA required before staging."}
    (out / "whole-map-batch-report.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k:result[k] for k in ("output_sha256", "patches", "batch_count", "total_entities",
        "max_triangles_per_submodel", "max_vertices_per_submodel", "max_submitted_vertices_per_submodel",
        "max_compiled_position_error")}, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bsp", type=Path, required=True)
    parser.add_argument("--patch-report", type=Path, required=True)
    parser.add_argument("--grass-source", type=Path, required=True)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    build(args.bsp, args.patch_report, args.grass_source, args.compiler, args.out)
