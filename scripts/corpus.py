#!/usr/bin/env python3
"""The README's corpus numbers: how keys behave across many real routes.

    python3 scripts/corpus.py ROUTES.jsonl [N]

ROUTES.jsonl: one JSON array per line, [id, shape, line, ...] (made from a
Hiker Atlas routes bundle; not in this repository).
"""
import json, random, sys, statistics as st
sys.path.insert(0, 'python'); sys.path.insert(0, 'scripts')
from route_keys import route_key, decode
from examples import jitter, simplify, extend_start

rows = [json.loads(l) for l in open(sys.argv[1])]
rng = random.Random(7)
sample = rng.sample(rows, int(sys.argv[2]) if len(sys.argv) > 2 else 3000)
keys = [route_key(r[2], r[1]) for r in rows]
lens = [len(k) for k in keys]
print(f'{len(rows):,} routes; key length median {st.median(lens):.0f}, 95th {sorted(lens)[int(len(lens) * .95)]}, max {max(lens)}; '
      f'{len(set(keys)):,} distinct keys, {len(set(k.split(".")[0] for k in keys)):,} distinct cell parts')
tests = {
    'written with 7 decimals, plus float noise': lambda l: [[float(f'{x + 3e-7:.7f}'), float(f'{y - 2e-7:.7f}')] for x, y in l],
    'every point moved up to 1 m': lambda l: jitter(l, 1, rng),
    'every point moved up to 3 m': lambda l: jitter(l, 3, rng),
    'every point moved up to 10 m': lambda l: jitter(l, 10, rng),
    'simplified, 5 m': lambda l: simplify(l, 5),
    'a 250 m walk in added': lambda l: extend_start(l, 250),
}
for name, f in tests.items():
    same = cs = cen = kept = 0
    for _, sh, line, _old in sample:
        key = route_key(line, sh)
        k = route_key(f(line), sh)
        a, b = decode(key), decode(k)
        same += k == key; cs += key.split('.')[0] == k.split('.')[0]
        cen += a.centroid == b.centroid; kept += len(set(a.cells) & set(b.cells)) / len(a.cells)
    n = len(sample)
    print(f'{name}: same key {same / n:.0%}, same cell part {cs / n:.0%}, same centroid cell {cen / n:.0%}, points\' cells kept {kept / n:.0%}')
