#!/usr/bin/env python3
"""The README's worked examples: its figures (docs/images/*.svg) and the
numbers in its tables, from two real routes (docs/examples.json).

    python3 scripts/examples.py        (from the repository root; needs h3)
"""
import json
import math
import random
import sys

import h3

sys.path.insert(0, 'python')
from route_keys import decode, route_key, shape_for  # noqa: E402
from route_keys import _along, _metres  # noqa: E402  (the recipe's own sampling, for the figures)

EX = {r['slug']: r for r in json.load(open('docs/examples.json'))['routes']}


def samples(line):
    segs = [_metres(a, b) for a, b in zip(line, line[1:])]
    total = 0.0
    for s in segs:
        total += s
    return ([_along(line, i / 20, segs, total) for i in range(21)],
            [_along(line, k / 8, segs, total) for k in range(9)])


def offset(p, east_m, north_m):
    k = 111320 * math.cos(math.radians(p[1]))
    return [p[0] + east_m / k, p[1] + north_m / 111320]


def jitter(line, r, rng):
    out = []
    for p in line:
        a, d = rng.uniform(0, 2 * math.pi), r * math.sqrt(rng.random())
        out.append(offset(p, d * math.cos(a), d * math.sin(a)))
    return out


def extend_start(line, m):
    """A walk of m metres in to the route's start, continuing its first leg backwards."""
    a, b = line[0], line[1]
    k = math.cos(math.radians(a[1]))
    dx, dy = (a[0] - b[0]) * k, a[1] - b[1]
    n = math.hypot(dx, dy)
    return [offset(a, dx / n * m, dy / n * m)] + list(line) if n else list(line)


def rotate_loop(line, frac):
    """The same loop, started frac of the way round."""
    segs = [_metres(a, b) for a, b in zip(line, line[1:])]
    total, goal, run = sum(segs), sum(segs) * frac, 0.0
    for i, s in enumerate(segs):
        if run + s >= goal:
            start = _along(line, frac, segs, total)
            return [start] + line[i + 1:] + line[1:i + 1] + [start]
        run += s
    return line


def simplify(line, tol):
    """Douglas-Peucker, tol metres."""
    if len(line) < 3:
        return line
    a, b = line[0], line[-1]
    k = 111320 * math.cos(math.radians(a[1]))
    ax, ay, bx, by = a[0] * k, a[1] * 111320, b[0] * k, b[1] * 111320
    best, idx = -1.0, 0
    for i in range(1, len(line) - 1):
        px, py = line[i][0] * k, line[i][1] * 111320
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        t = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
        d = math.hypot(px - ax - t * dx, py - ay - t * dy)
        if d > best:
            best, idx = d, i
    if best <= tol:
        return [a, b]
    return simplify(line[:idx + 1], tol)[:-1] + simplify(line[idx:], tol)


def compare(k0, k1):
    d0, d1 = decode(k0), decode(k1)
    shared = len(set(d0.cells) & set(d1.cells))
    return {'same': k0 == k1, 'centroid': d0.centroid == d1.centroid, 'shared': shared, 'of': len(d0.cells),
            'new': len(set(d1.cells) - set(d0.cells))}


def cells(c):
    if c['shared'] == c['of'] and not c['new']:
        return f"all {c['of']} the same"
    return f"{c['shared']} of {c['of']} kept" + (f", {c['new']} new" if c['new'] else '')


# --- Figures -----------------------------------------------------------------
W, H, PAD = 720, 460, 30
INK, MUTED, BG = '#1c1917', '#78716c', '#ffffff'
BLUE, ORANGE = '#2563eb', '#ea580c'


class Fig:
    def __init__(self, pts):
        self.lat0 = sum(p[1] for p in pts) / len(pts)
        k = math.cos(math.radians(self.lat0))
        xs, ys = [p[0] * k for p in pts], [p[1] for p in pts]
        self.k, self.x0, self.y1 = k, min(xs), max(ys)
        self.s = min((W - 2 * PAD) / (max(xs) - min(xs) or 1), (H - 2 * PAD - 60) / (max(ys) - min(ys) or 1))
        self.ox = (W - (max(xs) - min(xs)) * self.s) / 2
        self.oy = PAD + 50 + ((H - 2 * PAD - 60) - (max(ys) - min(ys)) * self.s) / 2
        self.out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
                    f'font-family="ui-sans-serif, system-ui, sans-serif"><rect width="{W}" height="{H}" fill="{BG}"/>']

    def xy(self, p):
        return ((p[0] * self.k - self.x0) * self.s + self.ox, (self.y1 - p[1]) * self.s + self.oy)

    def path(self, pts):
        return ' '.join(f'{"M" if i == 0 else "L"}{x:.1f},{y:.1f}' for i, (x, y) in enumerate(map(self.xy, pts)))

    def cell(self, c, fill, stroke, opacity=0.25, dash=''):
        ring = [[lon, lat] for lat, lon in h3.cell_to_boundary(c)]
        self.out.append(f'<path d="{self.path(ring + ring[:1])}Z" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" '
                        f'stroke-width="1.5"{f" stroke-dasharray={chr(34)}{dash}{chr(34)}" if dash else ""}/>')

    def line(self, pts, color, width=3, opacity=1.0):
        self.out.append(f'<path d="{self.path(pts)}" fill="none" stroke="{color}" stroke-width="{width}" '
                        f'stroke-opacity="{opacity}" stroke-linejoin="round" stroke-linecap="round"/>')

    def dot(self, p, r, fill, stroke='#fff'):
        x, y = self.xy(p)
        self.out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')

    def label(self, p, text, dx=8, dy=-8, color=INK, size=13):
        x, y = self.xy(p)
        self.out.append(f'<text x="{x + dx:.1f}" y="{y + dy:.1f}" font-size="{size}" fill="{color}" '
                        f'paint-order="stroke" stroke="#fff" stroke-width="3">{text}</text>')

    def text(self, x, y, s, size=14, color=INK, weight='normal', family=None):
        f = f' font-family="{family}"' if family else ''
        self.out.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}"{f}>{s}</text>')

    def save(self, path):
        open(path, 'w').write('\n'.join(self.out + ['</svg>']) + '\n')


def key_spans(key, x, y, size=18):
    """The key, its parts coloured: version, centroid, shape, points."""
    parts = [(key[0], MUTED), (key[1:8], BLUE), (key[8], '#16a34a'), (key[9:], ORANGE)]
    spans = ''.join(f'<tspan fill="{c}">{s}</tspan>' for s, c in parts)
    return f'<text x="{x}" y="{y}" font-size="{size}" font-family="ui-monospace, SFMono-Regular, Menlo, monospace">{spans}</text>'


def figure_anatomy(r, path):
    line = r['line']
    key = route_key(line, shape_for(r['kind']))
    d = decode(key)
    s21, s9 = samples(line)
    cells9 = [h3.latlng_to_cell(p[1], p[0], 10) for p in s9]
    pts = line + [[lon, lat] for c in d.cells + [d.centroid] for lat, lon in h3.cell_to_boundary(c)]
    f = Fig(pts)
    for c in d.cells:
        f.cell(c, ORANGE, ORANGE)
    f.cell(d.centroid, BLUE, BLUE, 0.18, '5 3')
    f.line(line, INK, 3)
    for p in s21:
        f.dot(p, 2.5, MUTED, 'none')
    # Points that share a cell (the way up and back of an out-and-back) are labelled together.
    by_cell = {}
    for k, (p, c) in enumerate(zip(s9, cells9)):
        by_cell.setdefault(c, []).append((k, p))
    for c, ks in by_cell.items():
        for k, p in ks:
            f.dot(p, 5, ORANGE)
        f.label(ks[0][1], ', '.join(str(k) for k, _ in ks), dx=9, dy=-9)
    cx = sum(p[0] for p in s21) / 21
    cy = sum(p[1] for p in s21) / 21
    f.dot([cx, cy], 6, BLUE)
    f.label([cx, cy], 'centroid', dx=-72, dy=5, color=BLUE)
    f.text(PAD, PAD + 4, f"{r['name']}, {r['park']}: {r['km']} km {r['kind']}", 15, INK, 'bold')
    f.out.append(key_spans(key, PAD, PAD + 32))
    f.text(PAD, H - 12, 'Orange: the cells of the 9 points evenly spaced along the line (0 to 8). Blue: the centroid of the 21 grey points, and its cell.', 12, MUTED)
    f.save(path)
    return key, d, by_cell


def figure_pair(a, b, title, ka, kb, path, note, centroids=False):
    da, db = decode(ka), decode(kb)
    pts = a + b + [[lon, lat] for c in da.cells + db.cells + [da.centroid, db.centroid] for lat, lon in h3.cell_to_boundary(c)]
    f = Fig(pts)
    for c in set(da.cells) - set(db.cells):
        f.cell(c, BLUE, BLUE, 0.2)
    for c in set(db.cells) - set(da.cells):
        f.cell(c, ORANGE, ORANGE, 0.2)
    for c in set(da.cells) & set(db.cells):
        f.cell(c, '#a8a29e', '#57534e', 0.3)
    if centroids:
        f.cell(da.centroid, 'none', BLUE, 0, '6 3')
        f.cell(db.centroid, 'none', ORANGE, 0, '2 3')
    f.line(a, BLUE, 5, 0.55)
    f.line(b, ORANGE, 2.5)
    if centroids:
        f.dot(a[0], 5, BLUE)
        f.dot(b[0], 5, ORANGE)
        f.label(b[0], 'new start', dx=9, dy=16, color=ORANGE)
    f.text(PAD, PAD + 4, title, 15, INK, 'bold')
    f.out.append(key_spans(ka, PAD, PAD + 30, 15))
    f.out.append(key_spans(kb, PAD, PAD + 50, 15))
    f.text(PAD + 470, PAD + 30, 'before (blue line)', 12, MUTED)
    f.text(PAD + 470, PAD + 50, 'after (orange line)', 12, MUTED)
    f.text(PAD, H - 12, note, 12, MUTED)
    f.save(path)


def main():
    tm, fen = EX['tunnel-mountain'], EX['fenland']
    rng = random.Random(1)
    k0, d0, by_cell = figure_anatomy(tm, 'docs/images/anatomy.svg')
    print('## Anatomy:', k0, d0.centroid, len(d0.cells), 'cells;', {c: [k for k, _ in v] for c, v in by_cell.items()})

    line = tm['line']
    rows = []

    def row(label, ln, shape='b', base=k0):
        k = route_key(ln, shape)
        c = compare(base, k)
        rows.append((label, k, c))

    row('Reversed (walked the other way)', line[::-1])
    mids = [line[0]]
    for a, b in zip(line, line[1:]):
        mids += [[(a[0] + b[0]) / 2, (a[1] + b[1]) / 2], b]
    row('Densified (a point added mid-way along every segment)', mids)
    row('Simplified (Douglas-Peucker, 5 m)', simplify(line, 5))
    row('Simplified (Douglas-Peucker, 20 m)', simplify(line, 20))
    row('Every point moved 3 m', jitter(line, 3, rng))
    row('A 250 m walk in added at the start', extend_start(line, 250))
    row('Last 10% cut off (an out-and-back that turned around short)', line[:int(len(line) * 0.9)])
    row('Called a one-way instead of an out-and-back', line, 'w')
    print('\n## Tunnel Mountain perturbations')
    print('| Change | Key | Same key? | Centroid cell | Points\' cells |')
    print('|---|---|---|---|---|')
    print(f'| (none) | `{k0}` | | | |')
    for label, k, c in rows:
        print(f"| {label} | `{k}` | {'yes' if c['same'] else 'no'} | {'same' if c['centroid'] else 'moved'} | {cells(c)} |")

    print('\n## Jitter trials (Tunnel Mountain, 500 each)')
    for r in (1, 3, 10, 25):
        same = shared = cen = 0
        for _ in range(500):
            c = compare(k0, route_key(jitter(line, r, rng), 'b'))
            same += c['same']; shared += c['shared'] / c['of']; cen += c['centroid']
        print(f'up to {r} m: same key {same / 5:.0f}%, centroid cell kept {cen / 5:.0f}%, points\' cells kept {shared / 5:.0f}%')

    fl = fen['line']
    kf = route_key(fl, 'p')
    print('\n## Fenland loop:', kf)
    for label, ln in (('reversed', fl[::-1]), ('started a quarter of the way round', rotate_loop(fl, 0.25)),
                      ('started an eighth of the way round', rotate_loop(fl, 0.125)), ('started 1% of the way round', rotate_loop(fl, 0.01)), ('started 2% (54 m) of the way round', rotate_loop(fl, 0.02))):
        k = route_key(ln, 'p')
        c = compare(kf, k)
        print(f"| {label} | `{k}` | {'yes' if c['same'] else 'no'} | {'same' if c['centroid'] else 'moved'} | {cells(c)} |")

    ext = extend_start(line, 250)
    figure_pair(line, ext, 'Tunnel Mountain with a 250 m walk in added at its start', k0, route_key(ext, 'b'),
                'docs/images/walk-in.svg', 'Grey: cells in both keys. Blue: only before. Orange: only after. Every sample point slides along, so the key changes.')
    rot = rotate_loop(fl, 0.02)
    figure_pair(fl, rot, 'Fenland Trail loop, started 54 m further round', kf, route_key(rot, 'p'),
                'docs/images/loop-start.svg', 'Every sample point slides 54 m along: grey cells kept, blue lost, orange gained. Dashed: the centroid\'s cell, the same before and after.',
                centroids=True)


if __name__ == '__main__':
    main()
