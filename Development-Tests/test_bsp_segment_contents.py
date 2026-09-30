"""Independent continuous-segment oracle regressions; no engine or assets needed."""
from types import SimpleNamespace
import struct
import unittest

from test_daragoth_expanded_collision import point_clear_segment,segment_content_intervals


class SegmentContentsTests(unittest.TestCase):
    def setUp(self):
        # A real positive-width solid leaf between adjacent y planes. Its width
        # is below the former 33-point oracle's spacing on this five-unit sweep.
        self.minimum,self.maximum=struct.unpack('<2f',struct.pack('<2f',11160.071,11160.077))
        self.map=SimpleNamespace(
            planes=[(0.,1.,0.,self.minimum,1),(0.,1.,0.,self.maximum,1)],
            hulls=[(0,[(0,1,-1),(1,-1,-2)])])
        self.start=(0.,11160.,0.)
        self.end=(0.,11165.333,0.)

    def test_thin_solid_between_all_former_samples(self):
        for k in range(33):
            y=self.start[1]+(self.end[1]-self.start[1])*k/32
            self.assertFalse(self.minimum<=y<self.maximum)
        self.assertFalse(point_clear_segment(self.map,0,self.start,self.end))
        solid=[(a,b)for a,b,c in segment_content_intervals(self.map,0,self.start,self.end)if c==-2]
        self.assertEqual(len(solid),1)
        self.assertGreater(solid[0][1],solid[0][0])

    def test_thin_solid_reverse_sweep(self):
        self.assertFalse(point_clear_segment(self.map,0,self.end,self.start))

    def test_known_empty_before_and_after_solid(self):
        self.assertTrue(point_clear_segment(self.map,0,self.start,(0.,11160.070,0.)))
        self.assertTrue(point_clear_segment(self.map,0,(0.,11160.078,0.),self.end))

    def test_stationary_inside_and_outside(self):
        inside=(0.,11160.074,0.)
        self.assertFalse(point_clear_segment(self.map,0,inside,inside))
        self.assertTrue(point_clear_segment(self.map,0,self.start,self.start))

    def test_exact_plane_endpoint_ownership(self):
        minimum=(0.,self.minimum,0.)
        maximum=(0.,self.maximum,0.)
        self.assertFalse(point_clear_segment(self.map,0,self.start,minimum))
        self.assertTrue(point_clear_segment(self.map,0,maximum,self.end))
        self.assertFalse(point_clear_segment(self.map,0,minimum,minimum))
        self.assertTrue(point_clear_segment(self.map,0,maximum,maximum))

    def test_empty_and_water_terminal_roots(self):
        self.map.hulls=[(-1,[])]
        self.assertTrue(point_clear_segment(self.map,0,self.start,self.end))
        self.map.hulls=[(-3,[])]
        self.assertFalse(point_clear_segment(self.map,0,self.start,self.end))


if __name__=='__main__':unittest.main()
