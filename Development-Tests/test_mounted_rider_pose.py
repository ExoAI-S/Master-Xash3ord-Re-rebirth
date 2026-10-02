"""Validate saddle pose joint geometry against a supplied MSR human MDL.

Usage: python Development-Tests/test_mounted_rider_pose.py path/to/reference.mdl
No game assets are embedded in this test. It reads the actual human skeleton and
the production pose table, then checks straddling, knee bend and boot direction.
"""
import math
from pathlib import Path
import re
import struct
import sys

repo = Path(__file__).resolve().parents[1]
source = repo / "Full-Source/msr_source/src/game/client/render/mounted_rider_pose.h"
rows = re.findall(r'\{"([^"]+)", \{([^}]+)\}\}', source.read_text())
angles = {name: [float(v.strip().removesuffix("f")) for v in values.split(",")] for name, values in rows}
policy = (repo / "Full-Source/msr_source/src/game/shared/ms/mount_policy.h").read_text()
lift = float(re.search(r'RiderLift = ([\d.]+)f;', policy).group(1))
renderer = source.with_name('studiomodelrenderer.cpp').read_text()
root_z = float(re.search(r'pos\[indices\[0\]\]\[2\] = (-?[\d.]+)f;', renderer).group(1))
saddle_pelvis = 36 + lift + root_z
assert 66.5 <= saddle_pelvis <= 68, 'hips must clear the padded seat without floating'
data = Path(sys.argv[1]).read_bytes()
assert data[:4] == b"IDST", "not a GoldSrc studio model"
count, index = struct.unpack_from("<2i", data, 140)
assert 1 <= count <= 128 and index + count * 112 <= len(data)

def rotation(a):
    x, y, z = a
    cx, sx, cy, sy, cz, sz = math.cos(x), math.sin(x), math.cos(y), math.sin(y), math.cos(z), math.sin(z)
    return [[cz*cy, cz*sy*sx-sz*cx, cz*sy*cx+sz*sx],
            [sz*cy, sz*sy*sx+cz*cx, sz*sy*cx-cz*sx], [-sy, cy*sx, cy*cx]]

def multiply(a, b):
    return [[sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

def vector(a, b):
    return [sum(a[i][k]*b[k] for k in range(3)) for i in range(3)]

world, names = [], {}
for i in range(count):
    offset = index + i * 112
    name = data[offset:offset+32].split(b"\0")[0].decode()
    parent = struct.unpack_from("<i", data, offset+32)[0]
    values = list(struct.unpack_from("<6f", data, offset+64))
    position, local_angles = values[:3], angles.get(name, values[3:])
    if name == "Bip01":
        # Renderer draw offset and standing origin place the root at saddle 64.
        position = [0.0, 0.0, saddle_pelvis]
    matrix = rotation(local_angles)
    if parent >= 0:
        assert parent < i
        prior, origin = world[parent]
        matrix = multiply(prior, matrix)
        position = [a+b for a, b in zip(vector(prior, position), origin)]
    world.append((matrix, position))
    names[name] = i

assert all(name in names for name in angles), "incompatible skeleton: pose must remain disabled"
point = lambda name: world[names[name]][1]
pelvis = point("Bip01 Pelvis")
assert abs(pelvis[2] - saddle_pelvis) < 0.1
for side, sign in [("L", 1), ("R", -1)]:
    hip, knee, ankle, toe = [point(f"Bip01 {side} {bone}") for bone in ["Leg", "Leg1", "Foot", "Toe0"]]
    assert 3 < hip[1] * sign < 5, (side, "hip width", hip)
    assert 12 < knee[1] * sign < 18, (side, "knee must straddle the saddle", knee)
    assert 17 < ankle[1] * sign < 24, (side, "ankle must stay outside horse", ankle)
    assert hip[2] > knee[2] > ankle[2] > toe[2], (side, "legs must hang down")
    assert knee[0] > hip[0] + 8 and ankle[0] < knee[0] - 1, (side, "forward knee and bent shin")
    foot = world[names[f"Bip01 {side} Foot"]][0]
    toe_direction = world[names[f"Bip01 {side} Toe0"]][0]
    assert vector(foot, [1, 0, 0])[2] < -0.99, (side, "boot must be upright")
    assert vector(toe_direction, [1, 0, 0])[0] > 0.99, (side, "toes must point forward")

for bone in ["Leg", "Leg1", "Foot", "Toe0"]:
    left, right = point(f"Bip01 L {bone}"), point(f"Bip01 R {bone}")
    assert abs(left[0]-right[0]) < 0.02 and abs(left[1]+right[1]) < 0.02 and abs(left[2]-right[2]) < 0.02
print("Mounted rider pose PASS: symmetric straddling, bent knees, upright forward boots; collider unchanged.")
print("Pelvis", [round(v, 2) for v in pelvis], "left knee", [round(v, 2) for v in point("Bip01 L Leg1")],
      "left ankle", [round(v, 2) for v in point("Bip01 L Foot")])
