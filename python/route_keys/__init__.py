"""Route keys, recipe v1 (see SPEC.md at the repository root).

A route's identity, computed from its line, so no ids are minted: the same
line always gives the same key.

    route_key(line, shape) -> str
        line: [[lon, lat], ...] (two points or more); shape: 'b', 'p' or 'w'
    decode(key) -> Decoded(version, centroid, shape, cells)
    is_route_key(key) -> bool
    shape_for(kind) -> 'b' | 'p' | 'w'

This and the TypeScript implementation (src/index.ts) must agree to the
character; vectors/v1.json is the contract both are tested against. Recipe v1
is frozen: see CLAUDE.md before changing anything here.
"""
from __future__ import annotations

import math
from typing import NamedTuple, Sequence

import h3

__all__ = ['route_key', 'decode', 'is_route_key', 'shape_for', 'Decoded', 'VERSION', 'RESOLUTION']

VERSION = '1'
RESOLUTION = 10
ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'  # base64url
SHAPES = 'bpw'  # out-and-back, loop, one-way
_INDEX = {ch: i for i, ch in enumerate(ALPHABET)}


class Decoded(NamedTuple):
    version: str
    centroid: str      # H3 cell (resolution 10), hex
    shape: str         # 'b', 'p' or 'w'
    cells: list[str]   # the sampled points' distinct cells, in key order


def shape_for(kind: str) -> str:
    """A route's shape letter from its kind: loop -> p, out-and-back -> b,
    anything else (one-way, point-to-point) -> w."""
    return 'p' if kind == 'loop' else 'b' if kind == 'out-and-back' else 'w'


def _metres(a: Sequence[float], b: Sequence[float]) -> float:
    k = math.cos(math.radians((a[1] + b[1]) / 2))
    dx = (a[0] - b[0]) * k
    dy = a[1] - b[1]
    return math.sqrt(dx * dx + dy * dy) * 111320


def _along(line, frac: float, segs: list[float], total: float) -> tuple[float, float]:
    goal, run = total * frac, 0.0
    for i, s in enumerate(segs):
        if run + s >= goal and s > 0:
            t = (goal - run) / s
            a, b = line[i], line[i + 1]
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        run += s
    return (line[-1][0], line[-1][1])


def _cell(p) -> str:
    return h3.latlng_to_cell(p[1], p[0], RESOLUTION)


def _zigzag(v: int) -> int:
    return 2 * v if v >= 0 else -2 * v - 1


def _unzigzag(z: int) -> int:
    return z // 2 if z % 2 == 0 else -(z + 1) // 2


def route_key(line: Sequence[Sequence[float]], shape: str) -> str:
    """The route key of a line ([[lon, lat], ...]) of the given shape."""
    if shape not in SHAPES or len(shape) != 1:
        raise ValueError("shape must be 'b', 'p' or 'w'")
    if len(line) < 2:
        raise ValueError('a line needs at least two points')
    segs = [_metres(a, b) for a, b in zip(line, line[1:])]
    total = 0.0
    for s in segs:  # a plain sum: Python's sum() of floats is compensated
        total += s
    if total == 0:
        total = 1.0
    sx = sy = 0.0
    for i in range(21):
        q = _along(line, i / 20, segs, total)
        sx += q[0]
        sy += q[1]
    c = _cell((sx / 21, sy / 21))
    n = int(c, 16)
    v = (n >> 45) & 0x7F
    for r in range(1, RESOLUTION + 1):
        v = (v << 3) | ((n >> ((15 - r) * 3)) & 7)
    v <<= 5
    out = [VERSION] + [ALPHABET[(v >> (6 * (6 - k))) & 63] for k in range(7)] + [shape]
    i0, j0 = h3.cell_to_local_ij(c, c)
    offs = sorted({(i - i0, j - j0) for i, j in
                   (h3.cell_to_local_ij(c, _cell(_along(line, k / 8, segs, total))) for k in range(9))})
    for di, dj in offs:
        for z in (_zigzag(di), _zigzag(dj)):
            while True:
                d = z & 31
                z >>= 5
                out.append(ALPHABET[d | (32 if z else 0)])
                if not z:
                    break
    return ''.join(out)


def decode(key: str) -> Decoded:
    """A v1 key's parts. Raises ValueError for anything that isn't one."""
    if (len(key) < 11 or key[0] != VERSION or key[8] not in SHAPES
            or any(ch not in _INDEX for ch in key[1:])):
        raise ValueError('not a v1 route key')
    v = 0
    for ch in key[1:8]:
        v = (v << 6) | _INDEX[ch]
    if v & 31:
        raise ValueError('not a v1 route key')
    v >>= 5
    n = (1 << 59) | (RESOLUTION << 52) | ((v >> 30) << 45)
    for r in range(1, 16):
        d = (v >> (3 * (RESOLUTION - r))) & 7 if r <= RESOLUTION else 7
        n |= d << ((15 - r) * 3)
    c = format(n, 'x')
    if not h3.is_valid_cell(c):
        raise ValueError('not a v1 route key')
    zs: list[int] = []
    z = shift = 0
    for ch in key[9:]:
        d = _INDEX[ch]
        z |= (d & 31) << shift
        shift += 5
        if not d & 32:
            zs.append(z)
            z = shift = 0
    if shift or not zs or len(zs) % 2:
        raise ValueError('not a v1 route key')
    i0, j0 = h3.cell_to_local_ij(c, c)
    try:
        cells = [h3.local_ij_to_cell(c, i0 + _unzigzag(a), j0 + _unzigzag(b)) for a, b in zip(zs[::2], zs[1::2])]
    except Exception as e:  # an offset with no cell
        raise ValueError('not a v1 route key') from e
    return Decoded(key[0], c, key[8], cells)


def is_route_key(key: str) -> bool:
    try:
        decode(key)
        return True
    except ValueError:
        return False
