"""Synthetic compiled-world surface regressions; no game or assets required."""
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Design-Source/Daragoth-Meadow'))
from meadow_surface import SurfaceIndex, coverage_survey


def fixture(polygons, *, world_faces=None):
    """polygons: (points, normal, plane distance, face side, texture)."""
    bsp = SimpleNamespace(models=[], faces=[], planes=[], vertexes=[], edges=[],
                          surfedges=[], texinfo=[], textures=[])
    for points, normal, distance, side, texture in polygons:
        firstvertex = len(bsp.vertexes)
        bsp.vertexes.extend(points)
        firstedge = len(bsp.surfedges)
        for i in range(len(points)):
            bsp.surfedges.append(len(bsp.edges))
            bsp.edges.append((firstvertex + i, firstvertex + (i + 1) % len(points)))
        bsp.planes.append(SimpleNamespace(normal=normal, dist=distance))
        bsp.texinfo.append(SimpleNamespace(miptex=len(bsp.textures)))
        bsp.textures.append(SimpleNamespace(name=texture))
        bsp.faces.append(SimpleNamespace(planenum=len(bsp.planes) - 1, side=side,
                                         firstedge=firstedge, numedges=len(points),
                                         texinfo=len(bsp.texinfo) - 1))
    bsp.models.append(SimpleNamespace(firstface=0, numfaces=len(polygons) if world_faces is None else world_faces))
    return bsp


def square(z, texture='DPGRASS', *, size=16, side=0):
    points=((0, 0, z), (size, 0, z), (size, size, z), (0, size, z))
    return points, (0, 0, -1 if side else 1), -z if side else z, side, texture


class MeadowSurfaceTests(unittest.TestCase):
    def test_stacked_planes_filters_and_inclusive_height_limits(self):
        index=SurfaceIndex(fixture([square(3), square(9, 'roof'), square(6, 'DPPATH')]), cell=4)
        self.assertEqual(index.at(8, 8)['z'], 9)
        self.assertEqual(index.at(8, 8, 'dpgrass')['z'], 3)
        self.assertEqual(index.at(8, 8, ['DPPATH', 'DPGRASS'])['z'], 6)
        self.assertEqual(index.ground(8, 8, max_z=6, min_z=6), 6)
        self.assertIsNone(index.at(8, 8, min_z=10))
        self.assertIsNone(index.at(8, 8, []))

    def test_sloped_plane_and_side_flipped_upward_normal(self):
        # z=10+x/2-y/4, stored as the opposite plane with face.side=1.
        normal=(.5, -.25, -1)
        points=((0, 0, 10), (16, 0, 18), (16, 16, 14), (0, 16, 6))
        index=SurfaceIndex(fixture([(points, normal, -10, 1, 'DPGRASS')]), cell=8)
        surface=index.at(8, 12)
        self.assertAlmostEqual(surface['z'], 11)
        length=math.sqrt(1.3125)
        for actual, expected in zip(surface['normal'], (-.5/length, .25/length, 1/length)):
            self.assertAlmostEqual(actual, expected)

    def test_triangle_uses_polygon_instead_of_bounding_box(self):
        triangle=(((0, 0, 4), (16, 0, 4), (0, 16, 4)), (0, 0, 1), 4, 0, 'DPGRASS')
        index=SurfaceIndex(fixture([triangle]), cell=8)
        self.assertIsNone(index.at(12, 12))
        self.assertEqual(index.ground(8, 8), 4)  # Shared/index boundary is inclusive.
        self.assertEqual(index.ground(0, 0), 4)
        self.assertIsNone(index.at(-.01, 1))

    def test_reversed_surfedges_and_negative_coordinate_cells(self):
        polygon=((((-16, -16, 2), (0, -16, 2), (0, 0, 2), (-16, 0, 2))), (0, 0, 1), 2, 0, 'grass')
        bsp=fixture([polygon])
        # Reverse the polygon winding through negative directed edge indexes.
        # Keep an unused edge zero so every reversed edge has a negative sign.
        bsp.edges.insert(0, (0, 0))
        bsp.surfedges=[-(e+1) for e in reversed(bsp.surfedges)]
        index=SurfaceIndex(bsp, cell=8)
        self.assertEqual(index.ground(-8, -8), 2)
        self.assertEqual(index.ground(0, 0), 2)
        self.assertIsNone(index.ground(1, -8))

    def test_downward_steep_and_submodel_faces_are_excluded(self):
        downward=(square(4)[0], (0, 0, 1), 4, 1, 'down')
        steep=(((0, 0, 0), (1, 0, 10), (1, 16, 10), (0, 16, 0)), (-10, 0, 1), 0, 0, 'steep')
        index=SurfaceIndex(fixture([square(1), downward, steep, square(100, 'submodel')], world_faces=3))
        self.assertEqual(index.at(.5, 8)['z'], 1)
        self.assertEqual(len(index.surfaces), 1)

    def test_coverage_counts_union_without_stacked_or_placement_double_count(self):
        index=SurfaceIndex(fixture([square(1), square(2), square(9, 'roof')]), cell=8)
        report=coverage_survey(index, [(8, 8), (8, 8)], spacing=8, radius=6)
        self.assertEqual(report['grid_samples'], 4)
        self.assertEqual(report['eligible_samples'], 4)
        self.assertEqual(report['covered_samples'], 4)
        self.assertEqual(report['estimated_eligible_xy_area'], 256)
        self.assertEqual(report['covered_fraction'], 1)
        empty=coverage_survey(index, spacing=8)
        self.assertEqual(empty['covered_fraction'], 0)
        clipped=coverage_survey(index, [{'origin': [4, 4, 1], 'radius': 1}], spacing=8, bounds=(0, 0, 8, 8))
        self.assertEqual(clipped['eligible_samples'], 1)
        self.assertEqual(clipped['covered_samples'], 1)

    def test_empty_index_and_invalid_grid_sizes(self):
        index=SurfaceIndex(fixture([]))
        self.assertIsNone(index.ground(0, 0))
        self.assertIsNone(coverage_survey(index)['covered_fraction'])
        for cell in (0, -1, float('nan')):
            with self.assertRaises(ValueError): SurfaceIndex(fixture([]), cell)
        with self.assertRaises(ValueError): coverage_survey(index, spacing=0)
        with self.assertRaises(ValueError): index.at(float('inf'), 0)


if __name__=='__main__':
    unittest.main()
