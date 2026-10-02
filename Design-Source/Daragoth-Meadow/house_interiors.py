"""Authored decorative Greenhollow interiors using existing private game models.

No models, map files, DLLs or runtime state are written here. The append builder
owns entity serialization and preservation proof. All props are env_model/dmg0:
they render fine detail but provide no furniture collision, inventory, flame,
merchant or loot behavior. The existing solid bench and house remain unchanged.

Bounds were replayed from the pinned studio v10 model's sequence0/frame0 and
selected body, including every bone parent and compressed channel, using only
vertices referenced by rendered mesh commands. They are mesh AABBs, not solid
hulls or promises of a continuous support surface. Orthogonal authored yaws make
the transformed bounds exact extrema. Native appearance/PVS/light sampling,
finite standing/world traces still need independent QA. Supported decorations
also replay the actual parent and child triangles: a mesh AABB maximum is never
accepted as tabletop contact. This checks vertical separation across their
overlapping XY footprints, including baked details and curved dish surfaces.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import math
from pathlib import Path
import struct

REGION = "daragoth_plains"
FLOOR_Z = 3128.0
BASIS = "production StudioSetUpTransform: entity origin + scale*Rz(yaw)*bone_pose; pitch=roll=0"
MODEL_POSE_POLICY = "sequence0/frame0/framerate0; CStaticModel has no animation Think; no controllers or EF_ROTATE"
SUPPORT_CONTACT_POLICY = ("Exact convex intersections of child/parent triangle XY projections; "
    "minimum vertical mesh separation across the footprint, not AABB top or equality of all foot vertices. "
    "A finite 0.02..0.08-unit minimum separation is authored contact; no collision is implied.")

# Derived from the pinned frame0 triangles, before six-decimal entity rounding.
# These are relative to each parent, so a plate's adjustment also moves its food.
# The long table includes baked dishes above its broad top. Mug3, cheese and
# knife already rest near those details and must not receive the broad-top drop.
_SUPPORT_DROPS = {
    ("inn", "plate_1"): 2.104962595553,
    ("inn", "plate_2"): 2.104962595553,
    ("inn", "plate_3"): 2.104962595553,
    ("inn", "mug_1"): 2.104962184011,
    ("inn", "mug_2"): 2.104962184012,
    ("inn", "wine_bottle"): 2.104962154461,
    ("inn", "bread_1"): .172428170029,
    ("inn", "bread_2"): .172428170029,
    ("inn", "bread_3"): .172428170029,
    ("cottage_south", "breakfast_bread"): .172428170029,
    ("bakery", "serving_cheese"): .120384271946,
}
ASSETS = {
    "models/props/bed_empty-wood.mdl": {"sha256":"b95f7e02b8e407cd5a6ed7020b21117279d0c071334fde5fbba6f0bc46c1caf0","sequence":0,"frame":0,"framerate":0,"bones":1,"controllers":0,"header_flags":0,"frames":1,"variants":{"0":{"name":"bed_empty-wood","bounds":[[-64.39,-34.800001,-0.42],[60.360002,33.340002,89.339996]],"drawn_vertices":176}}},
    "models/props/shelves1.mdl": {"sha256":"ab34c220ece899779ea3fde0f8e60cec13c29180a787d87999665c1955a18fd2","sequence":0,"frame":0,"framerate":0,"bones":1,"controllers":0,"header_flags":0,"frames":1,"variants":{"0":{"name":"shelves1_full_alch","bounds":[[-11.72034,-42.43,-31.810005],[9.049662,42.470001,33.259995]],"drawn_vertices":1201},"1":{"name":"shelves1_full","bounds":[[-11.72034,-42.43,-31.810005],[9.049662,42.470001,33.259995]],"drawn_vertices":230},"2":{"name":"shelves1_empty","bounds":[[-11.72034,-42.43,-31.810005],[9.049662,42.470001,33.259995]],"drawn_vertices":116}}},
    "models/props/books1.mdl": {"sha256":"412317405ca29ec07b46abe07bae6b7180cc376485ed3779f900909b2c029651","sequence":0,"frame":0,"framerate":0,"bones":1,"controllers":0,"header_flags":0,"frames":1,"variants":{"0":{"name":"books1","bounds":[[-4.77,-18.48,0.13],[4.77,16.850001,11.93]],"drawn_vertices":38}}},
    "models/props/Xen_furniture2.mdl": {"sha256":"57d5b73a495d7e6cba41f541a3105e45bb6f8f89899a7939a9c7665ea5044ac2","sequence":0,"frame":0,"framerate":0,"bones":1,"controllers":0,"header_flags":0,"frames":1,"variants":{"0":{"name":"./Schrank2","bounds":[[-19.248041,-27.026348,-0.173333],[9.451987,38.853654,90.086673]],"drawn_vertices":96}}},
    "models/props/foot_locker.mdl": {"sha256":"abfb216c56bd8b8a47f4a0017d17005bdb98d56989f8c3c60cd6237c286b905e","sequence":0,"frame":0,"framerate":0,"bones":1,"controllers":0,"header_flags":0,"frames":1,"variants":{"0":{"name":"foot_locker","bounds":[[-9.07,-17.34,-0.1],[9.07,17.34,14.63]],"drawn_vertices":8}}},
    "models/props/fireplace_logs1.mdl": {"sha256":"d0e05c960e06ba374b9568cc5496dd775cb282183fc3c176ef3db25e662dd08f","sequence":0,"frame":0,"framerate":0,"bones":27,"controllers":0,"header_flags":0,"frames":10,"variants":{"0":{"name":"fireplace_logs1","bounds":[[-21.7118,-19.509287,-0.228542],[24.274443,16.480728,26.232048]],"drawn_vertices":256}}},
    "models/props/wood_barrel1.mdl": {"sha256":"3266add2e42f86b09c2ffe1d549552a82235b7393ed4b0a362eea9bcec8e3b1e","sequence":0,"frame":0,"framerate":0,"bones":2,"controllers":0,"header_flags":0,"frames":10,"variants":{"0":{"name":"wood_barrel1","bounds":[[-24.434722,-22.931721,0],[23.585278,22.748294,50.779999]],"drawn_vertices":32}}},
    "models/props/pot1.mdl": {"sha256":"bb15042bd13825f7e95f17ce9e399f7725ec0068c73c3c414f383aa18a8053fe","sequence":0,"frame":0,"framerate":0,"bones":1,"controllers":0,"header_flags":0,"frames":1,"variants":{"0":{"name":"pot1","bounds":[[-16.649982,-10.007085,0.049426],[16.730017,19.302914,60.639431]],"drawn_vertices":153},"1":{"name":"pot1_full","bounds":[[-16.649982,-10.007085,0.049426],[16.730017,19.302914,60.639431]],"drawn_vertices":182}}},
    "models/props/pot2.mdl": {"sha256":"f1c3384f8d8586d3651e967d6257945851a0828715a97c0f9b67be496f1f17b5","sequence":0,"frame":0,"framerate":0,"bones":1,"controllers":0,"header_flags":0,"frames":1,"variants":{"0":{"name":"pot2","bounds":[[-18.023199,-18.290714,0.039993],[17.7968,17.519288,35.03]],"drawn_vertices":187}}},
    "models/props/shovel.mdl": {"sha256":"d798f92c2297d1039e2e46143ea308860b75e0f9654244ff7a60ba34e9091461","sequence":0,"frame":0,"framerate":0,"bones":1,"controllers":0,"header_flags":0,"frames":1,"variants":{"0":{"name":"shovel","bounds":[[-21.077858,-7.236276,0],[-11.813827,6.325251,46.720001]],"drawn_vertices":123}}},
    "models/props/repunzel_candle.mdl": {"sha256":"285d29b0c83bfd9f95f3efcd270613ae5bbada83257f68e49e98252e2893696a","sequence":0,"frame":0,"framerate":0,"bones":2,"controllers":0,"header_flags":0,"frames":1,"variants":{"0":{"name":"kerze","bounds":[[0.108872,-7.513107,0.592937],[11.518871,7.746893,25.266575]],"drawn_vertices":72}}},
    "models/misc/chair.mdl": {"sha256":"2cdcb1a4b0c6e92a003e5aadee502d3e7f015b1ab518be40f96df4ae0cd8f62e","sequence":0,"frame":0,"framerate":0,"bones":2,"controllers":0,"header_flags":0,"frames":7,"variants":{"0":{"name":"spork","bounds":[[-12.209466,-16.187193,0.384719],[15.010526,17.302806,54.064727]],"drawn_vertices":94},"1":{"name":"bord","bounds":[[-48.93,-25.78309,0.125471],[52.75,20.146911,36.505485]],"drawn_vertices":56}}},
    "models/misc/table1.mdl": {"sha256":"6ac43c24c8cd886a3653fccb76e607f2ff58feed8eebc9a80e779082eee2de51","sequence":0,"frame":0,"framerate":0,"bones":19,"controllers":0,"header_flags":0,"frames":10,"variants":{"0":{"name":"end_table1","bounds":[[-18.329376,-25.913859,-0.249617],[17.660624,26.076141,30.740384]],"drawn_vertices":144}}},
    "models/misc/table2.mdl": {"sha256":"040414f23ac2810f8b01b8ce6d61c6f2126d4668306d004f5906109e1554c46b","sequence":0,"frame":0,"framerate":0,"bones":1,"controllers":0,"header_flags":0,"frames":101,"variants":{"0":{"name":"bord","bounds":[[-20.147118,-48.930207,0.125471],[25.782885,52.749795,36.505485]],"drawn_vertices":56}}},
    "models/misc/dinner_table1.mdl": {"sha256":"d8faf9f3267b4a3a8dc446d6c5371f2ab15bf8f9c909e0534cbe1bca7c53d10d","sequence":0,"frame":0,"framerate":0,"bones":29,"controllers":0,"header_flags":0,"frames":10,"variants":{"0":{"name":"dinner_table1","bounds":[[-36.453197,-120.297378,0.321833],[35.586803,118.202622,38.203918]],"drawn_vertices":440}}},
    "models/misc/dinner_table2.mdl": {"sha256":"72740bd95a3375083012191ee4bffe88d72637cb1f5d5a2e143e464bf57a0c98","sequence":0,"frame":0,"framerate":0,"bones":15,"controllers":0,"header_flags":0,"frames":10,"variants":{"0":{"name":"dinner_table2","bounds":[[-40.461169,-55.723188,0.154339],[39.538843,56.266815,30.147696]],"drawn_vertices":204}}},
    "models/turbosquid/bread.mdl": {"sha256":"2c3d76bb3e568024e2ae7d79261321453a3f40e8478a334ed691e3f85ba93bbd","sequence":0,"frame":0,"framerate":0,"bones":1,"controllers":0,"header_flags":0,"frames":30,"variants":{"0":{"name":"./ref","bounds":[[-9.353754,-6.078449,0.195143],[12.326246,6.081551,8.295142]],"drawn_vertices":38}}},
    "models/turbosquid/mug.mdl": {"sha256":"6c8bfa65f99ac7b16df3015501d5d73e3d7a872bfdb437689fba1813256ed98b","sequence":0,"frame":0,"framerate":0,"bones":1,"controllers":0,"header_flags":0,"frames":1,"variants":{"0":{"name":"./ref","bounds":[[-4.563012,-5.053907,0.090437],[4.556988,6.636094,9.870439]],"drawn_vertices":42}}},
    "models/turbosquid/bowl.mdl": {"sha256":"a6a4c001876b512bb29e019b69987ca70c4bb929fef217ca2fd520061e0bd5aa","sequence":0,"frame":0,"framerate":0,"bones":1,"controllers":0,"header_flags":0,"frames":1,"variants":{"0":{"name":"./ref","bounds":[[-7.569686,-7.571116,0.104141],[7.560313,7.568885,3.514143]],"drawn_vertices":26}}},
    "models/turbosquid/bottle.mdl": {"sha256":"34e5ab0188ff25337e8565fa703815eec01dcfd165da2e20394b9f2c899ec0bd","sequence":0,"frame":0,"framerate":0,"bones":1,"controllers":0,"header_flags":0,"frames":50,"variants":{"0":{"name":"tall_green","bounds":[[-1.489064,-1.497397,0.00534],[1.500936,1.502603,17.755341]],"drawn_vertices":24},"5":{"name":"med_red","bounds":[[-1.489064,-1.497397,0.00534],[1.500936,1.502603,14.75534]],"drawn_vertices":24},"10":{"name":"sml_blue","bounds":[[-1.489064,-1.497397,0.00534],[1.500936,1.502603,11.75534]],"drawn_vertices":24},"15":{"name":"tny_yelo","bounds":[[-1.489064,-1.497397,0.00534],[1.500936,1.502603,8.75534]],"drawn_vertices":24}}},
    "models/turbosquid/plate.mdl": {"sha256":"a943e9c1d6105a3ab997482dd5ed6a1b86577babe521433e1026d6b32ab7f860","sequence":0,"frame":0,"framerate":0,"bones":1,"controllers":0,"header_flags":0,"frames":1,"variants":{"0":{"name":"./ref","bounds":[[-8.54,-7.73,0.224411],[8.54,8.92,1.174414]],"drawn_vertices":16}}},
    "models/turbosquid/cheese.mdl": {"sha256":"35c01608cfbb4f81671400084342b7cbf9b86e4c42565bc1cb4957f87c12783e","sequence":0,"frame":0,"framerate":0,"bones":1,"controllers":0,"header_flags":0,"frames":1,"variants":{"0":{"name":"./ref","bounds":[[-3.645627,-6.318484,0.005438],[3.654373,5.701516,5.27544]],"drawn_vertices":6}}},
    "models/turbosquid/knife.mdl": {"sha256":"99075ea9df0b5dc2d7820767b94f442587cd8ff92bfce066670a0847eb44cab1","sequence":0,"frame":0,"framerate":0,"bones":1,"controllers":0,"header_flags":0,"frames":1,"variants":{"0":{"name":"./ref","bounds":[[-5.184374,-2.321159,-0.388277],[16.595625,2.82884,0.391723]],"drawn_vertices":21}}},
}

# Source footprint sizes after village.py's human-scale rounding. Centers are
# house centers, not the door hinges (hingeY=centerY-36).
HOUSE_LAYOUTS = [
    {"house_id": "inn", "center": [-3169.9527, 5316.0], "half_size": [288, 200],
     "facing": "east", "description": "Inn dining room with stocked storage and a tea corner"},
    {"house_id": "workshop", "center": [-3169.9527, 6396.0], "half_size": [232, 192],
     "facing": "east", "description": "Workshop workbench, books, tool storage and oil pots"},
    {"house_id": "cottage_south", "center": [-1399.9527, 4956.0], "half_size": [176, 160],
     "facing": "west", "description": "Cottage sleeping corner and breakfast sitting area"},
    {"house_id": "cottage_north", "center": [-1399.9527, 6856.0], "half_size": [176, 160],
     "facing": "west", "description": "Cottage study with an alchemical shelf and potted greenery"},
    {"house_id": "bakery", "center": [-3169.9527, 7196.0], "half_size": [176, 152],
     "facing": "east", "description": "Bakery preparation table, bread, cheese, dishes and storage"},
    {"house_id": "farmhouse", "center": [-3299.9527, 4476.0], "half_size": [152, 152],
     "facing": "east", "description": "Farmhouse bedroom, small dining table, locker and shovel"},
]

for _house in HOUSE_LAYOUTS:
    _hx, _hy = _house["half_size"]
    _sign = 1 if _house["facing"] == "east" else -1
    _hinge_x = _sign * (_hx - 12)
    _house.update({
        "floor_z": FLOOR_Z, "wall_top_z": FLOOR_Z + 112,
        "interior_local_bounds": [[-_hx + 24, -_hy + 24, 0], [_hx - 24, _hy - 24, 112]],
        "existing_bench_local_bounds": [[-88, _hy - 64, 0], [88, _hy - 40, 24]],
        "door_hinge": [_house["center"][0] + _hinge_x, _house["center"][1] - 36, FLOOR_Z + 46],
        "door_reserve_local_bounds": [[_hinge_x - 100, -136, 0], [_hinge_x + 100, 64, 112]],
        "central_corridor_local_bounds": [[-_hx + 24, -32, 0], [_hx - 24, 32, 72]],
        "route_points": [[_house["center"][0] + _sign*x, _house["center"][1], FLOOR_Z + 36]
                         for x in (_hx + 64, _hx - 12, _hx - 70, 0, -_hx + 70)],
        "route_clear_width": 64, "route_standing_height": 72,
        "route_status": "authored visual clearance; actual world standing traces are not claimed",
        "diagnostic_views": [
            {"label": "entry", "body_origin": [_house["center"][0] + _sign*(_hx-80), _house["center"][1], FLOOR_Z+36],
             "yaw": 180 if _sign == 1 else 0, "pitch": 15},
            {"label": "back", "body_origin": [_house["center"][0] - _sign*(_hx-80), _house["center"][1], FLOOR_Z+36],
             "yaw": 0 if _sign == 1 else 180, "pitch": 15}],
        "collision_policy": "All new model props are decorative SOLID_NOT; old world and solid bench untouched",
        "lighting_policy": "Reuse existing scene lighting; no emissive lights, fire or new lightmaps",
    })

_SHORT = {
    "bed": "models/props/bed_empty-wood.mdl",
    "shelf": "models/props/shelves1.mdl",
    "books": "models/props/books1.mdl",
    "cabinet": "models/props/Xen_furniture2.mdl",
    "locker": "models/props/foot_locker.mdl",
    "logs": "models/props/fireplace_logs1.mdl",
    "barrel": "models/props/wood_barrel1.mdl",
    "plant_pot": "models/props/pot1.mdl",
    "pot": "models/props/pot2.mdl",
    "shovel": "models/props/shovel.mdl",
    "candle": "models/props/repunzel_candle.mdl",
    "chair": "models/misc/chair.mdl",
    "end_table": "models/misc/table1.mdl",
    "work_table": "models/misc/table2.mdl",
    "long_table": "models/misc/dinner_table1.mdl",
    "small_table": "models/misc/dinner_table2.mdl",
    "bread": "models/turbosquid/bread.mdl",
    "mug": "models/turbosquid/mug.mdl",
    "bowl": "models/turbosquid/bowl.mdl",
    "bottle": "models/turbosquid/bottle.mdl",
    "plate": "models/turbosquid/plate.mdl",
    "cheese": "models/turbosquid/cheese.mdl",
    "knife": "models/turbosquid/knife.mdl",
}


def _rotated_bounds(bounds, yaw, scale):
    # Authored yaws are orthogonal: extrema need no sampled rotation estimate.
    if yaw % 90:
        raise ValueError("Only orthogonal authored furniture rotations are supported")
    cs, sn = round(math.cos(math.radians(yaw))), round(math.sin(math.radians(yaw)))
    points = [(scale*(cs*x-sn*y), scale*(sn*x+cs*y), scale*z)
              for x in (bounds[0][0], bounds[1][0])
              for y in (bounds[0][1], bounds[1][1])
              for z in (bounds[0][2], bounds[1][2])]
    return [[min(p[k] for p in points) for k in range(3)],
            [max(p[k] for p in points) for k in range(3)]]


def _overlap(a, b):
    return all(min(a[1][k], b[1][k]) - max(a[0][k], b[0][k]) > .01 for k in range(3))


def placements():
    """Return fresh authored records; use build_layout(model_root) to verify assets."""
    records = []

    def add(house_id, identifier, kind, x, y, bottom=0, yaw=0, body=0, scale=1, support="floor"):
        house = next(h for h in HOUSE_LAYOUTS if h["house_id"] == house_id)
        model = _SHORT[kind]
        asset = ASSETS[model]
        selected = asset["variants"][str(body)]
        bounds = deepcopy(selected["bounds"])
        rotated = _rotated_bounds(bounds, yaw, scale)
        z = bottom - rotated[0][2]
        origin = [house["center"][0]+x, house["center"][1]+y, FLOOR_Z+z]
        local = [[rotated[j][k] + (x,y,z)[k] for k in range(3)] for j in range(2)]
        world = [[rotated[j][k] + origin[k] for k in range(3)] for j in range(2)]
        target = f"greenhollow_interior_{house_id}_{identifier}"
        number = lambda v: format(v, ".6f").rstrip("0").rstrip(".") or "0"
        entity = {
            "classname": "env_model", "targetname": target, "model": model,
            "origin": " ".join(number(v) for v in origin), "angles": f"0 {yaw} 0",
            "sequence": "0", "frame": "0", "framerate": "0", "body": str(body), "skin": "0",
            "scale": number(scale), "dmg": "0", "rendermode": "0", "renderamt": "255",
            "msr_region": REGION,
        }
        clear = house["interior_local_bounds"]
        if any(local[0][k] < clear[0][k]-.001 or local[1][k] > clear[1][k]+.001 for k in range(3)):
            raise ValueError(f"{target} exceeds the existing room")
        if _overlap(local, house["door_reserve_local_bounds"]):
            raise ValueError(f"{target} enters the conservative hinge reserve")
        if _overlap(local, house["central_corridor_local_bounds"]):
            raise ValueError(f"{target} enters the central standing corridor")
        if _overlap(local, house["existing_bench_local_bounds"]):
            raise ValueError(f"{target} intersects the old solid bench")
        record = {
            "house_id": house_id, "identifier": identifier, "description": kind.replace("_", " "),
            "entity": entity, "model_sha256": asset["sha256"], "posed_local_bounds": bounds,
            "house_local_bounds": local, "world_bounds": world, "support": support,
            "support_bottom_above_floor": bottom, "decoration_only": True,
            "model_pose": {"sequence": 0, "frame": 0, "framerate": 0, "body": body, "skin": 0,
                "scale": scale, "angles": [0,yaw,0], "selected_submodel": selected["name"],
                "drawn_vertices": selected["drawn_vertices"], "bones": asset["bones"],
                "controllers": 0, "model_header_flags": 0, "sequence_frames": asset["frames"],
                "motiontype": 0, "blends": 1,
                "basis": BASIS, "policy": MODEL_POSE_POLICY},
            "bounds_caveat": "Rendered frame0 AABB; no collision proxy or native visibility/lighting claim",
        }
        records.append(record)
        return local[1][2]

    # Inn: a real modeled dining set and individual tabletop objects.
    h="inn"
    table=add(h,"dining_table","long_table",-100,-95,yaw=90)
    for i,x in enumerate((-175,-105,-35)):
        add(h,f"dining_chair_{i+1}","chair",x,-149,yaw=180)
    for i,x in enumerate((-170,-105,-40)):
        plate=add(h,f"plate_{i+1}","plate",x,-96,table+.04,support="dining_table")
        add(h,f"mug_{i+1}","mug",x+17,-82,table+.04,support="dining_table")
        add(h,f"bread_{i+1}","bread",x,-96,plate+.04,scale=.68,support=f"plate_{i+1}")
    add(h,"cheese","cheese",-134,-112,table+.04,support="dining_table")
    add(h,"wine_bottle","bottle",-66,-111,table+.04,body=5,support="dining_table")
    add(h,"knife","knife",-121,-77,table+.04,yaw=180,support="dining_table")
    add(h,"book_shelf","shelf",-244,-85,body=1)
    add(h,"cabinet","cabinet",-220,81)
    tea=add(h,"tea_table","end_table",145,103)
    add(h,"tea_candle","candle",138,95,tea+.04,support="tea_table")
    add(h,"tea_bowl","bowl",150,115,tea+.04,support="tea_table")
    add(h,"barrel","barrel",219,147)

    # Workshop: workbench, tools, storage and a separate oil/pot table.
    h="workshop"
    table=add(h,"workbench","work_table",-85,-103,yaw=90)
    add(h,"work_chair","chair",-85,-149,yaw=180)
    add(h,"manuals","books",-87,-103,table+.04,yaw=90,support="workbench")
    add(h,"work_knife","knife",-126,-103,table+.04,support="workbench")
    add(h,"oil_bottle","bottle",-49,-103,table+.04,body=10,support="workbench")
    add(h,"storage_shelf","shelf",-190,-82,body=2)
    add(h,"shovel","shovel",-170,71)
    add(h,"tool_locker","locker",-129,104,yaw=90)
    add(h,"supply_barrel","barrel",166,128)
    table=add(h,"pot_table","end_table",116,99)
    add(h,"clay_pot","pot",116,99,table+.04,scale=.65,support="pot_table")
    add(h,"table_candle","candle",105,80,table+.04,scale=.75,support="pot_table")
    add(h,"small_oil","bottle",127,118,table+.04,body=15,support="pot_table")

    # South cottage: sleeping area and a separate breakfast seat/table.
    h="cottage_south"
    add(h,"bed","bed",65,-85)
    add(h,"wardrobe","cabinet",125,78)
    table=add(h,"bedside_table","end_table",-40,-82)
    add(h,"bedside_candle","candle",-47,-89,table+.04,support="bedside_table")
    add(h,"bedside_book","books",-29,-82,table+.04,support="bedside_table")
    add(h,"book_shelf","shelf",-100,78,yaw=90,body=1)
    table=add(h,"breakfast_table","end_table",0,61)
    add(h,"breakfast_chair","chair",65,61,yaw=90)
    plate=add(h,"breakfast_plate","plate",-3,61,table+.04,support="breakfast_table")
    add(h,"breakfast_bread","bread",-3,61,plate+.04,scale=.68,support="breakfast_plate")
    add(h,"breakfast_mug","mug",9,76,table+.04,support="breakfast_table")

    # North cottage: contrasting study/alchemy detail; no functional potions.
    h="cottage_north"
    add(h,"bed","bed",60,-85)
    add(h,"wardrobe","cabinet",125,78)
    add(h,"alchemical_shelf","shelf",-100,78,yaw=90,body=0)
    add(h,"storage_barrel","barrel",-113,113)
    table=add(h,"plant_table","end_table",-40,-82)
    add(h,"potted_greenery","plant_pot",-40,-82,table+.04,body=1,support="plant_table")
    table=add(h,"study_table","end_table",0,61)
    add(h,"study_chair","chair",65,61,yaw=90)
    add(h,"study_books","books",-8,61,table+.04,support="study_table")
    add(h,"study_candle","candle",4,77,table+.04,scale=.8,support="study_table")
    add(h,"study_bottle","bottle",9,47,table+.04,body=10,support="study_table")

    # Bakery: individual loaves/utensils on modeled furniture.
    h="bakery"
    table=add(h,"prep_table","work_table",-60,-80,yaw=90)
    for i,x in enumerate((-94,-66,-36)):
        add(h,f"loaf_{i+1}","bread",x,-79,table+.04,support="prep_table")
    add(h,"prep_knife","knife",-65,-96,table+.04,support="prep_table")
    add(h,"prep_bowl","bowl",-100,-65,table+.04,support="prep_table")
    add(h,"storage_shelf","shelf",-134,-78,body=2)
    add(h,"flour_pot","plant_pot",-108,65,body=0,scale=.8)
    add(h,"supply_barrel","barrel",115,102)
    add(h,"hearth_logs","logs",-120,105,scale=.7)
    table=add(h,"serving_table","end_table",-35,60)
    add(h,"serving_chair","chair",24,58,yaw=90)
    plate=add(h,"serving_plate","plate",-37,60,table+.04,support="serving_table")
    add(h,"serving_cheese","cheese",-37,60,plate+.04,support="serving_plate")
    add(h,"serving_mug","mug",-23,76,table+.04,support="serving_table")
    add(h,"bottle","bottle",-45,78,table+.04,body=0,support="serving_table")

    # Farmhouse: smaller objects keep this compact room navigable.
    h="farmhouse"
    add(h,"bed","bed",-40,-86)
    add(h,"foot_locker","locker",-115,-63)
    add(h,"wardrobe","cabinet",116,91,scale=.9)
    add(h,"shovel","shovel",-95,110)
    table=add(h,"meal_table","end_table",-103,60)
    add(h,"meal_chair","chair",-54,56,yaw=90)
    add(h,"meal_pot","pot",-107,58,table+.04,scale=.55,support="meal_table")
    add(h,"meal_mug","mug",-92,76,table+.04,support="meal_table")
    add(h,"meal_bread","bread",-102,41,table+.04,scale=.8,support="meal_table")
    add(h,"small_bottle","bottle",-115,77,table+.04,body=15,support="meal_table")
    add(h,"candle_on_bench","candle",20,100,24.04,scale=.75,support="existing_solid_bench")
    add(h,"books_on_bench","books",-31,100,24.04,yaw=90,support="existing_solid_bench")
    if len({r["entity"]["targetname"] for r in records}) != len(records):
        raise ValueError("Duplicate authored interior targetname")
    # Keep the authored XY layout and apply the independently diagnosed support
    # heights. build_layout verifies these against complete projected meshes.
    drops = {}
    for record in records:
        key = (record["house_id"], record["identifier"])
        parent = (record["house_id"], record["support"])
        drop = drops.get(parent, 0) + _SUPPORT_DROPS.get(key, 0)
        drops[key] = drop
        if drop:
            origin = [float(v) for v in record["entity"]["origin"].split()]
            origin[2] -= drop
            record["entity"]["origin"] = " ".join(format(v, ".6f").rstrip("0").rstrip(".") or "0" for v in origin)
            for field in ("house_local_bounds", "world_bounds"):
                for bound in record[field]:
                    bound[2] -= drop
            record["support_bottom_above_floor"] -= drop
        record["support_vertical_adjustment"] = -drop
        record["support_contact_policy"] = SUPPORT_CONTACT_POLICY
    return records


def _matrix_product(a, b):
    return [[sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _matrix_vector(a, v):
    return [sum(a[i][j]*v[j] for j in range(3)) for i in range(3)]


def _posed_geometry(data, body):
    """Read-only sequence0/frame0 replay, restricted to the pinned asset format."""
    if data[:4] != b"IDST" or struct.unpack_from("<i",data,4)[0] != 10:
        raise ValueError("Expected studio v10")
    bones, bone_at = struct.unpack_from("<2i",data,140)
    if not 0 < bones <= 128 or struct.unpack_from("<i",data,148)[0]:
        raise ValueError("Unsupported bone/controller layout")
    sequences, seq_at = struct.unpack_from("<2i",data,164)
    parts, part_at = struct.unpack_from("<2i",data,204)
    if sequences < 1 or parts != 1 or struct.unpack_from("<i",data,seq_at+156)[0]:
        raise ValueError("Unsupported sequence/bodypart layout")
    if struct.unpack_from("<i",data,seq_at+68)[0] or struct.unpack_from("<i",data,seq_at+120)[0] != 1:
        raise ValueError("Unsupported root motion or blended sequence")
    anim = struct.unpack_from("<i",data,seq_at+124)[0]
    transforms = []
    for b in range(bones):
        at=bone_at+112*b
        parent=struct.unpack_from("<i",data,at+32)[0]
        if parent >= b or parent < -1:
            raise ValueError("Invalid bone hierarchy")
        pose=list(struct.unpack_from("<6f",data,at+64))
        scales=struct.unpack_from("<6f",data,at+88)
        for k, offset in enumerate(struct.unpack_from("<6H",data,anim+12*b)):
            if offset:
                valid,total=struct.unpack_from("<2B",data,anim+12*b+offset)
                if not 0 < valid <= total:
                    raise ValueError("Invalid frame0 compressed channel")
                pose[k]+=struct.unpack_from("<h",data,anim+12*b+offset+2)[0]*scales[k]
        rx,ry,rz=pose[3:]
        cx,sx,cy,sy,cz,sz=math.cos(rx),math.sin(rx),math.cos(ry),math.sin(ry),math.cos(rz),math.sin(rz)
        r=_matrix_product(_matrix_product([[cz,-sz,0],[sz,cz,0],[0,0,1]],[[cy,0,sy],[0,1,0],[-sy,0,cy]]),
                          [[1,0,0],[0,cx,-sx],[0,sx,cx]])
        p=pose[:3]
        if parent >= 0:
            pr,pp=transforms[parent]
            p=[v+pp[k] for k,v in enumerate(_matrix_vector(pr,p))]
            r=_matrix_product(pr,r)
        transforms.append((r,p))
    count,base,model_at=struct.unpack_from("<3i",data,part_at+64)
    selected=(body//base)%count
    at=model_at+112*selected
    record=struct.unpack_from("<64sif10i",data,at)
    meshes,mesh_at,vertices,bone_indices,vertex_at=record[3:8]
    used=set()
    triangle_indices=[]
    for i in range(meshes):
        cursor=struct.unpack_from("<i",data,mesh_at+20*i+4)[0]
        while True:
            number=struct.unpack_from("<h",data,cursor)[0];cursor+=2
            if number == 0:
                break
            strip = [struct.unpack_from("<h",data,cursor+8*j)[0] for j in range(abs(number))]
            used.update(strip)
            for j in range(len(strip)-2):
                indices = ((strip[j],strip[j+1],strip[j+2]) if j%2 == 0 else
                           (strip[j+1],strip[j],strip[j+2])) if number > 0 else (strip[0],strip[j+1],strip[j+2])
                triangle_indices.append(indices)
            cursor+=abs(number)*8
    posed={}
    for index in sorted(used):
        if not 0 <= index < vertices or data[bone_indices+index] >= bones:
            raise ValueError("Invalid referenced studio vertex")
        r,p=transforms[data[bone_indices+index]]
        point=_matrix_vector(r,struct.unpack_from("<3f",data,vertex_at+12*index))
        posed[index]=[point[k]+p[k] for k in range(3)]
    points=list(posed.values())
    if not points or not triangle_indices:
        raise ValueError("Empty selected model")
    return {"bounds": [[min(p[k] for p in points) for k in range(3)],
                       [max(p[k] for p in points) for k in range(3)]],
            "drawn_vertices": len(used), "points": points,
            "triangles": [[posed[i] for i in indices] for indices in triangle_indices]}


def _posed_bounds(data, body):
    geometry = _posed_geometry(data, body)
    return geometry["bounds"], geometry["drawn_vertices"]


def _world_geometry(record, geometry):
    origin = [float(v) for v in record["entity"]["origin"].split()]
    yaw = float(record["entity"]["angles"].split()[1])
    scale = float(record["entity"]["scale"])
    cs, sn = round(math.cos(math.radians(yaw))), round(math.sin(math.radians(yaw)))
    def transform(p):
        return [origin[0]+scale*(cs*p[0]-sn*p[1]),
                origin[1]+scale*(sn*p[0]+cs*p[1]), origin[2]+scale*p[2]]
    return {"points": [transform(p) for p in geometry["points"]],
            "triangles": [[transform(p) for p in tri] for tri in geometry["triangles"]]}


def _projected_plane(triangle):
    a,b,c = triangle
    ux,uy,uz = [b[k]-a[k] for k in range(3)]
    vx,vy,vz = [c[k]-a[k] for k in range(3)]
    nx,ny,nz = uy*vz-uz*vy, uz*vx-ux*vz, ux*vy-uy*vx
    if abs(nz) < 1e-9:
        return None  # Vertical/zero-area XY triangles cannot support a footprint.
    # Keep the reference point instead of a large world-coordinate intercept;
    # very narrow projected triangles otherwise lose precision near their edge.
    return (-nx/nz, -ny/nz, *a)


def _plane_height(plane, xy):
    sx,sy,x,y,z = plane
    return z+sx*(xy[0]-x)+sy*(xy[1]-y)


def _xy_intersection(child, parent):
    """Convex triangle intersection, independent of source winding."""
    polygon = [p[:2] for p in child]
    signed = sum(parent[i][0]*parent[(i+1)%3][1]-parent[(i+1)%3][0]*parent[i][1] for i in range(3))
    sign = 1 if signed > 0 else -1
    for i in range(3):
        a,b = parent[i],parent[(i+1)%3]
        def distance(p):
            return sign*((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]))
        clipped=[]
        for j,p in enumerate(polygon):
            q=polygon[(j+1)%len(polygon)]
            dp,dq=distance(p),distance(q)
            if dp >= -1e-8:
                clipped.append(p)
            if (dp >= 0) != (dq >= 0):
                t=dp/(dp-dq)
                clipped.append([p[k]+t*(q[k]-p[k]) for k in range(2)])
        polygon=clipped
        if not polygon:
            break
    return polygon


def _mesh_separation(child, parent):
    """Minimum child-minus-parent height over all projected triangle overlaps."""
    best=None
    for ci,ct in enumerate(child["triangles"]):
        cp=_projected_plane(ct)
        if cp is None:
            continue
        cbox=[min(p[k] for p in ct) for k in range(2)]+[max(p[k] for p in ct) for k in range(2)]
        for pi,pt in enumerate(parent["triangles"]):
            pp=_projected_plane(pt)
            if pp is None:
                continue
            if any(cbox[k+2] < min(p[k] for p in pt)-1e-8 or cbox[k] > max(p[k] for p in pt)+1e-8 for k in range(2)):
                continue
            for xy in _xy_intersection(ct,pt):
                cz=_plane_height(cp,xy)
                pz=_plane_height(pp,xy)
                gap=cz-pz
                if best is None or gap < best["minimum_separation"]:
                    best={"minimum_separation":gap, "child_triangle":ci,
                          "parent_triangle":pi,"xy":xy,"child_z":cz,"parent_z":pz,
                          "parent_plane_z_from_xy":{"slope_xy":list(pp[:2]),"reference_xyz":list(pp[2:])}}
    if best is None:
        raise ValueError("Decoration has no rendered parent footprint")
    return best


def build_layout(model_root):
    """Verify only referenced frozen model files; return records without writing."""
    model_root=Path(model_root).resolve()
    records=placements()
    selected={(r["entity"]["model"],int(r["entity"]["body"])) for r in records}
    geometries={}
    for model in sorted({model for model,body in selected}):
        path=model_root/model
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest() != ASSETS[model]["sha256"]:
            raise ValueError(f"Changed original furnishing asset: {model}")
        for _,body in sorted(pair for pair in selected if pair[0] == model):
            geometry=_posed_geometry(data,body)
            actual,count=geometry["bounds"],geometry["drawn_vertices"]
            expected=ASSETS[model]["variants"][str(body)]
            if count != expected["drawn_vertices"] or max(abs(actual[j][k]-expected["bounds"][j][k])
                    for j in range(2) for k in range(3)) > .000002:
                raise ValueError(f"Selected frame0/body bounds changed: {model}/{body}")
            geometries[(model,body)]=geometry
    world={}
    for record in records:
        key=(record["house_id"],record["identifier"])
        geometry=_world_geometry(record,geometries[(record["entity"]["model"],int(record["entity"]["body"]))])
        parent=(record["house_id"],record["support"])
        if record["support"] in ("floor","existing_solid_bench"):
            height=FLOOR_Z+(24 if record["support"] == "existing_solid_bench" else 0)
            gap=min(p[2] for p in geometry["points"])-height
            contact={"minimum_separation":gap,"support_plane_z":height,
                     "method":"Pinned flat house floor/old solid bench and actual rendered minimum vertex"}
            if not -.00001 <= gap <= .08001:
                raise ValueError(f"Flat support mismatch: {key}/{gap}")
        else:
            if parent not in world:
                raise ValueError(f"Parent must precede its decoration: {key}")
            contact=_mesh_separation(geometry,world[parent])
            contact["method"]="All nondegenerate child/parent triangle XY intersections, exact affine height separation"
            if not .01999 <= contact["minimum_separation"] <= .08001:
                raise ValueError(f"Actual mesh support mismatch: {key}/{contact['minimum_separation']}")
        record["support_contact"]=contact
        world[key]=geometry
    return records
