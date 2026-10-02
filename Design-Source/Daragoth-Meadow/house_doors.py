"""Shared authored geometry/settings for Greenhollow's usable wooden doors."""

DOOR_IDS = ('inn', 'workshop', 'cottage_south', 'cottage_north', 'bakery', 'farmhouse')
LEAF_MINS = (-3, 0, -45)
LEAF_MAXS = (3, 72, 45)
DOOR_SETTINGS = {'classname': 'func_door_rotating', 'angles': '0 0 0',
                 'spawnflags': '288', 'speed': '90', 'distance': '90',
                 'wait': '3', 'dmg': '0', 'movesnd': '9', 'stopsnd': '0',
                 'msr_region': 'daragoth_plains'}


def door_values(identifier, hinge, origin, model=None):
    values = dict(DOOR_SETTINGS)
    values.update({'targetname': 'greenhollow_door_' + identifier,
                   'origin': origin(*hinge)})
    if model is not None:
        values['model'] = model
    return values


def door_brushes(box, hinge):
    """An original solid leaf plus a removed compiler ORIGIN pivot brush."""
    lo = tuple(hinge[k] + LEAF_MINS[k] for k in range(3))
    hi = tuple(hinge[k] + LEAF_MAXS[k] for k in range(3))
    pivot_lo = tuple(v - 2 for v in hinge)
    pivot_hi = tuple(v + 2 for v in hinge)
    return [box(lo, hi, 'DPWOOD', 1), box(pivot_lo, pivot_hi, 'ORIGIN', 1)]
