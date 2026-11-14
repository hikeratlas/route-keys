#!/usr/bin/env python3
"""Writes vectors/v1.json, once. Kept for the record of how the vectors were
made: they're frozen now (tests check the file's hash), and the real routes
came from a Hiker Atlas build that this script can't fetch again.

    python3 scripts/make_vectors.py OLD_VECTORS.json > vectors/v1.json
"""
import json, math, sys
sys.path.insert(0, 'python')
from route_keys import route_key, decode

def line_east(lon, lat, km, n=2):
    k = 1000 / (111320 * math.cos(math.radians(lat)))
    return [[round(lon + km * k * i / (n - 1), 6), lat] for i in range(n)]

real = json.load(open(sys.argv[1]))['vectors']
lake_agnes_like = real[0]['line']
synth = [
    ('synthetic: two points, 1 km due east', 'w', line_east(-116.2, 51.4, 1.0)),
    ('synthetic: zero length (every point the same)', 'b', [[-116.2, 51.4]] * 3),
    ('synthetic: repeated points along a line', 'w', [[-116.2, 51.4], [-116.2, 51.4], [-116.19, 51.405], [-116.19, 51.405], [-116.18, 51.41]]),
    ('synthetic: the first real vector, reversed (same key)', real[0]['shape'], lake_agnes_like[::-1]),
    ('synthetic: southern and eastern hemispheres (New Zealand)', 'b', [[168.1265, -44.7244], [168.1301, -44.7187], [168.1356, -44.7121], [168.1420, -44.7080]]),
    ('synthetic: a 300 km one-way line', 'w', line_east(-120.0, 49.0, 300.0, n=31)),
]
vs = [{k: v[k] for k in ('name', 'shape', 'line', 'key')} for v in real]
for name, shape, line in synth:
    vs.append({'name': name, 'shape': shape, 'line': line, 'key': route_key(line, shape)})
for v in vs:
    d = decode(v['key'])
    v['centroid'], v['cells'] = d.centroid, d.cells
assert vs[len(real) + 3]['key'] == real[0]['key']
doc = {
    'recipe': 1,
    'description': "Route keys, recipe v1 (SPEC.md): lines and the keys they give, with each key's decoded centroid cell and points' cells (H3 resolution 10). line is [[lon, lat], ...]; shape is b (out-and-back), p (loop) or w (one-way). The real routes are Hiker Atlas's, from its 13 November 2026 north-america build. Frozen: never edit; a new recipe gets a new file.",
    'vectors': vs,
}
json.dump(doc, sys.stdout, separators=(',', ':'))
