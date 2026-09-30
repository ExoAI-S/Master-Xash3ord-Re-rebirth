"""Original ridge profiles for the private continuous Daragoth meadow.

The original Daragoth half of the join is never passed through this function.
Inputs are local plains coordinates. This module imports no map builders and
performs no file or runtime operations. Its height field only raises terrain.

Integration: apply boundary_height AFTER the existing meadow height function.
Wrap row_x with boundary_row_x so the two entry road-edge grid columns exactly
follow the protected legacy aperture; this avoids interpolating an adjacent
raised bank across that aperture on the existing 600-unit grid.
"""
from __future__ import annotations
import math

HALF_WIDTH = 12000.0
HALF_LENGTH = 10640.0
SKY_TOP = 4096.0
MAX_HEIGHT = 3320.0
SEAM_Y = -10000.0
PLAINS_OFFSET_X = 1650.0473022166188
ENTRY_ROAD_X = 1528.0 - PLAINS_OFFSET_X
ENTRY_PORTAL_MIN_X = 1104.0 - PLAINS_OFFSET_X
ENTRY_PORTAL_MAX_X = 2432.0 - PLAINS_OFFSET_X
OUTER_X_START = 8400.0
OUTER_NORTH_START = 7040.0
ENTRY_BANK_START_Y = -8200.0
ENTRY_GRID_FIXED_Y = -9000.0
WALKABLE_NORMAL_Z = 0.7


def _smooth(value):
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def _ridge_profile(value):
    """Gentle lower foothill, followed by the deliberately steep upper face."""
    value = min(1.0, max(0.0, value))
    if value <= 0.7:
        return 0.14 * _smooth(value / 0.7)
    return 0.14 + 0.86 * _smooth((value - 0.7) / 0.3)


def _road_x(y):
    return 250.0 * math.sin(y / 3800.0)


def _rectangle_release(x, y, xmin, xmax, ymin, ymax, feather=600.0):
    """Zero on a retained gameplay pad; smoothly releases outside it."""
    distance = max(xmin - x, x - xmax, ymin - y, y - ymax, 0.0)
    return _smooth(distance / feather)


def boundary_row_x(x, y, base_x, inner=600.0):
    """Wrap the builder's existing row_x without adding terrain columns.

    Only the existing -inner, 0, +inner columns change near the south entry.
    Their order is preserved between the neighboring +/-1200 columns. North
    of the bank and throughout the rest of the map, base_x is returned exactly.
    """
    if y >= ENTRY_BANK_START_Y:
        return base_x
    if x == -round(inner):
        fixed = ENTRY_PORTAL_MIN_X
    elif x == 0:
        fixed = ENTRY_ROAD_X
    elif x == round(inner):
        fixed = ENTRY_PORTAL_MAX_X
    else:
        return base_x
    weight = _smooth((ENTRY_BANK_START_Y - y) /
                     (ENTRY_BANK_START_Y - ENTRY_GRID_FIXED_Y))
    return base_x + (fixed - base_x) * weight


def boundary_height(x, y, base_height):
    """Return a bounded raised ridge height, preserving gameplay pads.

    West/east foothills begin at |x|=8400, with steep upper faces beyond
    |x|=10920. The northern ridge starts at y=7040 and steepens beyond y=9560.
    Its road channel stays unchanged within 800 units of road_x(y), feathering
    out to 1800. The far Deralia exit therefore remains traversable.

    The south entry bank starts at y=-8200 and steepens toward y=-10000,
    outside the exact x=1104..2432 legacy world-space aperture. The bank crest
    is 1470..2530 local units, safely above the old ~824-unit rock cap. The
    stable, village and ruins pads retain their original base heights.
    """
    if not all(math.isfinite(v) for v in (x, y, base_height)):
        raise ValueError('Boundary inputs must be finite')
    if base_height > MAX_HEIGHT:
        raise ValueError('Base terrain exceeds the boundary sky-headroom limit')

    # Two oblique waves give visibly unequal summits and saddles on the existing
    # grid. Their 2250..3250 bound retains sky headroom and the upper steep belt.
    # The lower bound also keeps the east/south corner steep where the bank
    # and outer ridge overlap on the existing coarse terrain triangles.
    crest = (2750.0 + 325.0 * math.sin(y / 1400.0 + x / 3300.0)
             + 175.0 * math.sin(y / 750.0 - x / 2200.0))
    west_east = _ridge_profile((abs(x) - OUTER_X_START) /
                              (HALF_WIDTH - OUTER_X_START))
    north = _ridge_profile((y - OUTER_NORTH_START) /
                          (HALF_LENGTH - OUTER_NORTH_START))
    north *= _smooth((abs(x - _road_x(y)) - 800.0) / 1000.0)
    outer_weight = max(west_east, north)

    # Shorter, unequal waves break up the long south crest into rolling hills.
    # Even the deepest saddle remains well above the retained original cap.
    bank_crest = (2000.0 + 270.0 * math.sin(x / 600.0)
                  + 180.0 * math.sin(x / 1500.0) + 80.0 * math.cos(x / 350.0))
    bank = _ridge_profile((ENTRY_BANK_START_Y - y) /
                         (ENTRY_BANK_START_Y - SEAM_Y))
    outside_portal = max(ENTRY_PORTAL_MIN_X - x, x - ENTRY_PORTAL_MAX_X, 0.0)
    bank *= _smooth(outside_portal / 720.0)

    # Retain authored floors, threshold steps, horse access and walking routes.
    release = min(
        _rectangle_release(x, y, -2600.0, -800.0, -8640.0, -7160.0),
        _rectangle_release(x, y, -5678.0, -2472.0, -9198.0, -5502.0),
        _rectangle_release(x, y, 5480.0, 7520.0, 5180.0, 7220.0))
    raised = max(base_height + max(0.0, crest - base_height) * outer_weight,
                 base_height + max(0.0, bank_crest - base_height) * bank)
    return min(MAX_HEIGHT, base_height + (raised - base_height) * release)


def integration_notes():
    """Machine-readable recommendations; no source text patching is done here."""
    return {
        'coordinate_space': 'local plains, original Daragoth remains unmodified',
        'height_after_base': True,
        'row_x_wrapper_required': True,
        'additional_x_columns_required': [],
        'recommended_y_rows': [-10000, -9600, -9400, -9000, -8200, 7040, 9560, 10000, 10640],
        'grid_rule': 'Retain existing bridge and village rows. Add only necessary bank/north rows; avoid near-duplicate rows under 160 units.',
        'expected_height_limit': MAX_HEIGHT,
        'ridge_crest_height_bounds': {'outer': [2250.0, 3250.0], 'entrance_bank': [1470.0, 2530.0]},
        'minimum_sky_headroom': SKY_TOP - MAX_HEIGHT,
        'outer_steep_zones': {'west': 'x<-10920', 'east': 'x>10920', 'north': 'y>9560 outside far road channel'},
        'entry_bank_zone': {'y': [SEAM_Y, ENTRY_BANK_START_Y], 'protected_x': [ENTRY_PORTAL_MIN_X, ENTRY_PORTAL_MAX_X]},
        'slope_validation': 'Keep playable interior ground under its existing limit. Allow intended boundary triangles to exceed acos(0.7)=45.573 degrees. Require an actual compiled hull barrier around the upper ridges; do not infer impassability only from this analytic field.',
        'material_recommendation': 'Use grass on lower foothills and original rock on steep upper terrain; cover the old seam cap from the north with solid terrain, never remove cap/PVS/sky coverage without replacement.',
        'scope': 'Analytic heights are a proposal. Compiled seam, source pads, native collision and render closure must be re-audited after integration.'}
