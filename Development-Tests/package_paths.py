"""Resolve only packaged test inputs; never search installed games or user profiles."""
from pathlib import Path
import os
import sys

TEST_ROOT = Path(__file__).resolve().parent
PACKAGE_ROOT = TEST_ROOT.parent


def source_root():
    candidates = [PACKAGE_ROOT / name / 'msr_source' / 'src' for name in ('Source', 'Full-Source')]
    matches = [path for path in candidates if (path / 'game' / 'shared' / 'stats' / 'stats.cpp').is_file()]
    if len(matches) != 1:
        raise FileNotFoundError('Expected exactly one adjacent Source/msr_source/src or Full-Source/msr_source/src tree')
    return matches[0]


def game_root():
    return source_root() / 'game'


def baseline_game_root():
    return TEST_ROOT / 'reference' / 'baseline-game'


def script_root():
    return TEST_ROOT / 'reference' / 'scripts'


def runtime_root():
    path = PACKAGE_ROOT / 'Portable-Package' / 'game' / 'msr'
    if not (path / 'gfx' / 'vgui' / 'msr_world_atlas_0_0.tga').is_file():
        raise FileNotFoundError('Packaged runtime atlas is missing: ' + str(path))
    return path


def frozen_archive(variable):
    value = os.environ.get(variable)
    if not value:
        raise FileNotFoundError(variable + ' must point to the complete original review archive; see Development-Tests/README.md')
    path = Path(value).resolve()
    if not (path / 'bundle-manifest.json').is_file():
        raise FileNotFoundError('Missing review bundle-manifest.json in ' + str(path))
    return path


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('source', 'runtime'):
        raise SystemExit('Usage: python package_paths.py source|runtime')
    print(source_root() if sys.argv[1] == 'source' else runtime_root())
