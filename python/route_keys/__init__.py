"""Route keys, recipe v1 (see SPEC.md at the repository root).

A route's identity, computed from its line, so no ids are minted:

    1E57E06gbDEBBBICDGF.k3Xq9vB0aRm
    \\_ cells: decodable _/ \\_ hash _/

The cells say where the route is and roughly where it goes; the hash makes
the key an exact identity of the line.

    route_key(line, shape) -> str
        line: [[lon, lat], ...] (two points or more); shape: 'b', 'p' or 'w'
    decode(key) -> Decoded(version, centroid, shape, cells, hash)
    is_route_key(key) -> bool
    shape_for(kind) -> 'b' | 'p' | 'w'

This and the TypeScript implementation (ts/src) must agree to the
character; vectors/v1.json is the contract both are tested against. Recipe v1
is frozen: see CLAUDE.md before changing anything here.
"""
from __future__ import annotations

import base64
import hashlib
import math
import struct
from typing import NamedTuple, Sequence

import h3

__all__ = ['route_key', 'decode', 'is_route_key', 'shape_for', 'Decoded', 'VERSION', 'RESOLUTION']

VERSION = '1'
RESOLUTION = 10
GRID = 100000  # coordinates are rounded to 1 / GRID degrees (~1.1 m)
ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'  # base64url
SHAPES = 'bpw'  # out-and-back, loop, one-way
HASH_CHARS = 11
_INDEX = {ch: i for i, ch in enumerate(ALPHABET)}


class Decoded(NamedTuple):
    version: str
    centroid: str      # H3 cell (resolution 10), hex
    shape: str         # 'b', 'p' or 'w'
    cells: list[str]   # the sampled points' distinct cells, in key order
    hash: str          # the line's hash, 11 characters


def shape_for(kind: str) -> str:
    """A route's shape letter from its kind: loop -> p, out-and-back -> b,
    anything else (one-way, point-to-point) -> w."""
    return 'p' if kind == 'loop' else 'b' if kind == 'out-and-back' else 'w'


def _quantize(v: float) -> int:
    """Rounded to the nearest 1/GRID degree, halves away from zero."""
    x = v * GRID
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))


def _normalize(line) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for p in line:
        q = (_quantize(p[0]), _quantize(p[1]))
        if not out or out[-1] != q:
            out.append(q)
    return out


def _metres(a, b) -> float:
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


def _cells_part(line, shape: str) -> str:
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


def _hash_part(q: list[tuple[int, int]]) -> str:
    def digest(pts):
        return hashlib.sha256(b''.join(struct.pack('<ii', lon, lat) for lon, lat in pts)).digest()
    d = min(digest(q), digest(q[::-1]))  # either direction: the smaller digest
    return base64.urlsafe_b64encode(d[:9]).decode('ascii')[:HASH_CHARS]


def route_key(line: Sequence[Sequence[float]], shape: str) -> str:
    """The route key of a line ([[lon, lat], ...]) of the given shape."""
    if shape not in SHAPES or len(shape) != 1:
        raise ValueError("shape must be 'b', 'p' or 'w'")
    if len(line) < 2:
        raise ValueError('a line needs at least two points')
    q = _normalize(line)
    degrees = [(lon / GRID, lat / GRID) for lon, lat in q]
    return _cells_part(degrees, shape) + '.' + _hash_part(q)


def decode(key: str) -> Decoded:
    """A v1 key's parts. Raises ValueError for anything that isn't one."""
    cells_part, dot, hash_part = key.partition('.')
    if (not dot or len(hash_part) != HASH_CHARS or any(ch not in _INDEX for ch in hash_part)
            or len(cells_part) < 11 or cells_part[0] != VERSION or cells_part[8] not in SHAPES
            or any(ch not in _INDEX for ch in cells_part[1:])):
        raise ValueError('not a v1 route key')
    v = 0
    for ch in cells_part[1:8]:
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
    for ch in cells_part[9:]:
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
    return Decoded(VERSION, c, cells_part[8], cells, hash_part)


def is_route_key(key: str) -> bool:
    try:
        decode(key)
        return True
    except ValueError:
        return False
