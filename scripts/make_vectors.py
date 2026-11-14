#!/usr/bin/env python3
"""Writes vectors/v1.json: only for a deliberate recipe change, before 1.0
(see CLAUDE.md); tests check the file's hash. The real routes' lines came
from a Hiker Atlas build that this script can't fetch again: pass the
first 22 vectors of vectors/v1.json (the real routes) as LINES.json to reuse them.

    python3 scripts/make_vectors.py LINES.json > vectors/v1.json

LINES.json: {"vectors": [{"name", "shape", "line"}, ...]}, the real routes.
"""
import json, math, sys
sys.path.insert(0, 'python')
from route_keys import route_key, decode

def line_east(lon, lat, km, n=2):
    k = 1000 / (111320 * math.cos(math.radians(lat)))
    return [[round(lon + km * k * i / (n - 1), 5), lat] for i in range(n)]

real = json.load(open(sys.argv[1]))['vectors']
ex = {r['slug']: r for r in json.load(open('docs/examples.json'))['routes']}
first = real[0]
synth = [
    ('synthetic: two points, 1 km due east', 'w', line_east(-116.2, 51.4, 1.0)),
    ('synthetic: zero length (every point the same)', 'b', [[-116.2, 51.4]] * 3),
    ('synthetic: repeated points along a line', 'w', [[-116.2, 51.4], [-116.2, 51.4], [-116.19, 51.405], [-116.19, 51.405], [-116.18, 51.41]]),
    ('synthetic: the first real vector, reversed (same key)', first['shape'], first['line'][::-1]),
    ('synthetic: the first real vector, written with 7 decimals and float noise (same key)', first['shape'],
     [[float(f'{lon + 3e-7:.7f}'), float(f'{lat - 2e-7:.7f}')] for lon, lat in first['line']]),
    ('synthetic: southern and eastern hemispheres (New Zealand)', 'b', [[168.1265, -44.7244], [168.1301, -44.7187], [168.1356, -44.7121], [168.1420, -44.7080]]),
    ('synthetic: a 300 km one-way line', 'w', line_east(-120.0, 49.0, 300.0, n=31)),
    ('Mendenhall Lake from Junction / Outer Moraine Trailhead (same cells as the next, a different path)', 'b', ex['mendenhall-lake']['line']),
    ('Nugget Falls Trail (same cells as the previous, a different path)', 'b', ex['nugget-falls']['line']),
]
vs = [{'name': v['name'], 'shape': v['shape'], 'line': v['line']} for v in real]
vs += [{'name': n, 'shape': s, 'line': l} for n, s, l in synth]
for v in vs:
    v['key'] = route_key(v['line'], v['shape'])
    d = decode(v['key'])
    v['centroid'], v['cells'], v['hash'] = d.centroid, d.cells, d.hash
by = {v['name']: v['key'] for v in vs}
assert by['synthetic: the first real vector, reversed (same key)'] == vs[0]['key']
assert by['synthetic: the first real vector, written with 7 decimals and float noise (same key)'] == vs[0]['key']
a, b = vs[-2]['key'], vs[-1]['key']
assert a.split('.')[0] == b.split('.')[0] and a != b
doc = {
    'recipe': 1,
    'description': "Route keys, recipe v1 (SPEC.md): lines and the keys they give, with each key's decoded centroid cell, points' cells (H3 resolution 10) and hash. line is [[lon, lat], ...]; shape is b (out-and-back), p (loop) or w (one-way). The real routes are Hiker Atlas's, from its 13 November 2026 north-america build, derived from OpenStreetMap data (© OpenStreetMap contributors, ODbL). Changes only with the recipe (see CLAUDE.md); frozen from route-keys 1.0.",
    'vectors': vs,
}
json.dump(doc, sys.stdout, separators=(',', ':'))
