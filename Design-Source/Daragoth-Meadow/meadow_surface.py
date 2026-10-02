"""Read-only height and coverage queries against compiled BSP world polygons.

Accepts the existing ``bsp30.BSP`` records. These are rendered surfaces, not a
collision trace, PVS test, or proof that a floor is reachable. A texture filter
selects the highest *matching* surface, even beneath a nonmatching roof; query
without a filter when testing whether another world surface is above a patch.
"""
from __future__ import annotations

import math
from typing import NamedTuple


_EPSILON = 1e-5  # World units, including at polygon and index-cell boundaries.


class _Surface(NamedTuple):
    face: int
    texture: str
    normal: tuple
    dist: float
    points: tuple
    bounds: tuple  # xmin, ymin, xmax, ymax
    edges: tuple  # ax, ay, unit edge dx, unit edge dy


def _texture_set(names):
    if names is None:
        return None
    if isinstance(names, str):
        names = (names,)
    return frozenset(name.casefold() for name in names)


def _contains(surface, x, y):
    xmin, ymin, xmax, ymax = surface.bounds
    if not (xmin - _EPSILON <= x <= xmax + _EPSILON and
            ymin - _EPSILON <= y <= ymax + _EPSILON):
        return False
    # Compiled brush faces are convex; either winding is valid. Normalize each
    # edge so tolerance is a distance, independent of the polygon's dimensions.
    positive = negative = False
    for ax, ay, dx, dy in surface.edges:
        cross = dx * (y - ay) - dy * (x - ax)
        positive |= cross > _EPSILON
        negative |= cross < -_EPSILON
        if positive and negative:
            return False
    return True


class SurfaceIndex:
    """Spatial index of world faces with effective upward normal z > 0.2.

    ``at`` returns ``{z, normal, texture, face}`` or None. Normals are unit
    vectors after applying ``face.side``; z is solved from the compiled plane.
    Height limits are inclusive and expressed in the BSP's world coordinates.
    ``surfaces`` exposes immutable records, and ``bounds`` is their XY union.
    Build a new index after modifying world geometry.
    """

    def __init__(self, bsp, cell=512):
        self.cell = float(cell)
        if not math.isfinite(self.cell) or self.cell <= 0:
            raise ValueError('Surface index cell must be finite and positive')
        self._cells = {}
        surfaces = []
        if bsp.models:
            world = bsp.models[0]
            for face_id in range(world.firstface, world.firstface + world.numfaces):
                face = bsp.faces[face_id]
                plane = bsp.planes[face.planenum]
                length = math.sqrt(sum(n * n for n in plane.normal))
                if not math.isfinite(length) or length == 0:
                    continue
                factor = (-1 if face.side else 1) / length
                normal = tuple(n * factor for n in plane.normal)
                if normal[2] <= .2:
                    continue
                points = tuple(tuple(bsp.vertexes[bsp.edges[abs(edge)][0 if edge >= 0 else 1]])
                               for edge in bsp.surfedges[face.firstedge:face.firstedge + face.numedges])
                if len(points) < 3:
                    continue
                area2 = sum(a[0] * b[1] - b[0] * a[1]
                            for a, b in zip(points, points[1:] + points[:1]))
                if abs(area2) <= _EPSILON * _EPSILON:
                    continue
                edges = []
                for a, b in zip(points, points[1:] + points[:1]):
                    dx, dy = b[0] - a[0], b[1] - a[1]
                    size = math.hypot(dx, dy)
                    if size > _EPSILON:
                        edges.append((a[0], a[1], dx / size, dy / size))
                if len(edges) < 3:
                    continue
                bounds = (min(p[0] for p in points), min(p[1] for p in points),
                          max(p[0] for p in points), max(p[1] for p in points))
                texture = bsp.textures[bsp.texinfo[face.texinfo].miptex].name
                surface = _Surface(face_id, texture, normal, plane.dist * factor,
                                   points, bounds, tuple(edges))
                surfaces.append(surface)
                xmin, ymin, xmax, ymax = bounds
                for ix in range(math.floor((xmin - _EPSILON) / self.cell),
                                math.floor((xmax + _EPSILON) / self.cell) + 1):
                    for iy in range(math.floor((ymin - _EPSILON) / self.cell),
                                    math.floor((ymax + _EPSILON) / self.cell) + 1):
                        self._cells.setdefault((ix, iy), []).append(surface)
        self.surfaces = tuple(surfaces)
        self.bounds = ((min(s.bounds[0] for s in surfaces), min(s.bounds[1] for s in surfaces),
                        max(s.bounds[2] for s in surfaces), max(s.bounds[3] for s in surfaces))
                       if surfaces else None)

    def at(self, x, y, texture_names=None, max_z=None, min_z=None):
        """Highest matching surface at XY, or None; texture names ignore case."""
        x, y = float(x), float(y)
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError('Surface query coordinates must be finite')
        names = _texture_set(texture_names)
        selected = None
        key = (math.floor(x / self.cell), math.floor(y / self.cell))
        for surface in self._cells.get(key, ()):
            if names is not None and surface.texture.casefold() not in names:
                continue
            if not _contains(surface, x, y):
                continue
            nx, ny, nz = surface.normal
            z = (surface.dist - nx * x - ny * y) / nz
            if max_z is not None and z > max_z or min_z is not None and z < min_z:
                continue
            if selected is None or z > selected['z']:
                selected = {'z': z, 'normal': surface.normal,
                            'texture': surface.texture, 'face': surface.face}
        return selected

    def ground(self, x, y, texture_names=None, max_z=None, min_z=None):
        """Height-only equivalent of at(), returning None for no surface."""
        surface = self.at(x, y, texture_names, max_z, min_z)
        return None if surface is None else surface['z']


def coverage_survey(index, placements=(), *, spacing=16,
                    texture_names=('medgrass2_ewoks', 'DPGRASS'), bounds=None,
                    radius=140, min_normal_z=.7, max_z=None, min_z=None):
    """Estimate XY meadow coverage on a global, cell-centered sampling grid.

    Dict placements use their ``origin`` and optional ``radius``; XY/XYZ tuples
    use the supplied default radius. Coverage is a circular footprint estimate,
    not opaque blade coverage. Spacing controls cost and accuracy; use 128/256
    for an initial survey and 16 for a finer statistical pass. World surface
    selection follows at(): nonmatching roofs, hulls, and dynamic models are
    not considered. The result does not claim full movement or render QA.
    """
    spacing, radius = float(spacing), float(radius)
    if not math.isfinite(spacing) or spacing <= 0:
        raise ValueError('Survey spacing must be finite and positive')
    if not math.isfinite(radius) or radius < 0:
        raise ValueError('Coverage radius must be finite and nonnegative')
    names = _texture_set(texture_names)
    matching = [s for s in index.surfaces
                if names is None or s.texture.casefold() in names]
    if bounds is None and matching:
        bounds = (min(s.bounds[0] for s in matching), min(s.bounds[1] for s in matching),
                  max(s.bounds[2] for s in matching), max(s.bounds[3] for s in matching))
    centers = []
    for placement in placements:
        point = placement['origin'] if isinstance(placement, dict) else placement
        r = float(placement.get('radius', radius)) if isinstance(placement, dict) else radius
        center = (float(point[0]), float(point[1]), r)
        if not all(math.isfinite(v) for v in center) or r < 0:
            raise ValueError('Coverage placement must have finite XY and nonnegative radius')
        centers.append(center)
    # A second spatial grid keeps coverage checks local even in a fine survey.
    cover_cells = {}
    for x, y, r in centers:
        for ix in range(math.floor((x - r) / index.cell), math.floor((x + r) / index.cell) + 1):
            for iy in range(math.floor((y - r) / index.cell), math.floor((y + r) / index.cell) + 1):
                cover_cells.setdefault((ix, iy), []).append((x, y, r * r))
    sampled = eligible = covered = 0
    textures = {}
    if bounds is not None:
        xmin, ymin, xmax, ymax = map(float, bounds)
        if not all(math.isfinite(v) for v in (xmin, ymin, xmax, ymax)) or xmax < xmin or ymax < ymin:
            raise ValueError('Survey bounds must be finite ordered xmin,ymin,xmax,ymax')
        for ix in range(math.ceil(xmin / spacing - .5), math.ceil(xmax / spacing - .5)):
            x = (ix + .5) * spacing
            for iy in range(math.ceil(ymin / spacing - .5), math.ceil(ymax / spacing - .5)):
                y = (iy + .5) * spacing
                sampled += 1
                surface = index.at(x, y, names, max_z, min_z)
                if surface is None or surface['normal'][2] < min_normal_z:
                    continue
                eligible += 1
                counts = textures.setdefault(surface['texture'], {'eligible': 0, 'covered': 0})
                counts['eligible'] += 1
                candidates = cover_cells.get((math.floor(x / index.cell), math.floor(y / index.cell)), ())
                if any((x - px) ** 2 + (y - py) ** 2 <= r2 for px, py, r2 in candidates):
                    covered += 1
                    counts['covered'] += 1
    return {'spacing': spacing, 'bounds': bounds, 'grid_samples': sampled,
            'eligible_samples': eligible, 'covered_samples': covered,
            'estimated_eligible_xy_area': eligible * spacing * spacing,
            'estimated_covered_xy_area': covered * spacing * spacing,
            'covered_fraction': covered / eligible if eligible else None,
            'placements': len(centers), 'textures': textures,
            'scope': 'Cell-centered world render-surface sampling; circular XY prop footprints. '
                     'Texture-filtered surfaces may be beneath roofs. No collision, PVS, '
                     'dynamic-entity, blade-opacity, or traversal guarantee.'}
