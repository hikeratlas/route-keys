# Route keys: recipe v1

This is the normative definition. `python/route_keys` and `ts/src` implement
it, and `vectors/v1.json` is the contract between them. An implementation is
correct when it gives every vector's key from its line and shape, and decodes
every key to its centroid, cells and hash.

Recipe v1 is a draft until route-keys 1.0. Until then it may change: SPEC.md,
both implementations and the vectors change together, with a minor version
bump. From 1.0 it's frozen: a change to anything below that changes a key
would make a different recipe, v2, with its own version character, document
and vectors, and v1 keys stay valid forever (see CLAUDE.md).

## The key

    1E57E06gbDEBBBICDGF.tn3dBnAuR_Q
    \_____ cells _____/ \_ hash __/

- **The cell part** is coarse geometry: where the route is and roughly where it goes. Anyone can decode it.
- **The hash** is 11 characters of a SHA-256 hash of the exact line. It makes the key an identity of the line.

All characters are base64url (RFC 4648 §5):
`ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_`, plus the
`.` between the parts. Every character is allowed in an AT Protocol record
key. Character `n` of the alphabet is digit `n`.

## Input

- **line:** two or more points, `[longitude, latitude]` in degrees (WGS 84).
- **shape:** one character:
  - `b`: out-and-back;
  - `p`: loop;
  - `w`: one-way (anything else, such as point-to-point).

  `shape_for(kind)` maps a kind: `loop` gives `p`, `out-and-back` gives `b`, anything else gives `w`.

## 1. Normalise

1. **Round** each coordinate to the nearest 0.00001° (about 1.1 m): `x = v × 100000` as a double, then `floor(x + 0.5)` if `x ≥ 0`, else `−floor(−x + 0.5)`. That gives integers, halves rounded away from zero.
2. **Drop consecutive duplicates:** a point equal to the one before it.

This makes a key independent of how a line was written down. A copy with
more decimals, or float noise below the grid, gives the same key. Lines
published with 5 decimals or fewer pass through unchanged.

## 2. The cell part

Work with the normalised points converted back to degrees, `integer / 100000`
(a double division). Use IEEE 754 doubles, operations in the order written,
and:

- **Distance** between points `a` and `b`, in metres:
  - `k = cos(radians((a.lat + b.lat) / 2))`
  - `dx = (a.lon − b.lon) × k`
  - `dy = a.lat − b.lat`
  - distance = `sqrt(dx × dx + dy × dy) × 111320`

  Use `sqrt`, not `hypot`, whose rounding varies between libraries.
- **Sums** are plain, left to right. Python's `sum()` of floats is compensated, so don't use it.

A rounding difference can move a point across a cell boundary.

**Points along the line.**
1. Let `seg[i]` be the distance from point `i` to point `i+1`, and `total` their plain sum.
2. If `total` is 0, use 1.
3. The point at fraction `f` is found as follows:
   - Let `goal = total × f`.
   - Walk the segments in order, keeping `run`, the sum of the segments before the current one.
   - Stop at the first segment with `run + seg[i] ≥ goal` and `seg[i] > 0`.
   - The point is `a + (b − a) × t`, with `t = (goal − run) / seg[i]`, interpolating longitude and latitude linearly between the segment's ends `a` and `b`.
   - If no segment qualifies, it's the last point. A line normalised to a single point gives that point at every fraction.

**Characters.**
1. **Version:** `1`.
2. **Centroid** (7 characters):
   - Take the points at fractions `i / 20` for `i = 0 … 20`, and average their longitudes and latitudes (plain sums, divided by 21).
   - Take the H3 cell containing the average, at resolution 10 (`latLngToCell(lat, lon, 10)`).
   - Take its 37 meaningful bits: the 7-bit base cell, then resolution digits 1 to 10, 3 bits each, most significant first.
   - Shift left by 5 (to 42 bits) and write as 7 digits, most significant first. The prefix is then a coarser area.
3. **Shape:** the shape character.
4. **Points:**
   - Take the points at fractions `k / 8` for `k = 0 … 8`, and their resolution-10 cells.
   - For each cell, take its offset from the centroid's cell in H3's local IJ coordinates: `cellToLocalIj(centroid, cell)` minus `cellToLocalIj(centroid, centroid)`.
   - Keep the distinct offsets, sorted by `i`, then `j`.
   - Write each offset's `i`, then its `j`:
     - zigzag-encode the integer: `v ≥ 0` gives `2v`, otherwise `−2v − 1`;
     - write the result as a varint: 5 bits a digit, least significant first, adding 32 to every digit but the last.

The cell part has at least one offset, so at least 11 characters.

## 3. The hash

1. Serialise the normalised points as consecutive pairs of 32-bit signed little-endian integers: longitude, then latitude.
2. Take SHA-256 of that, and of the same points in reverse order. Keep the smaller of the two digests, comparing byte by byte.
3. Encode its first 9 bytes as base64url, giving 12 characters, and keep the first 11 (66 bits).

## Direction

Reversing a line never changes its key:
- **The cell part:** the points at `k/8` of a line are the points at `1 − k/8` of its reverse, and they're kept as a set.
- **The hash:** it's the smaller digest of either direction.

This is by design: a key names a path, not a direction of travel (see README,
"Design decisions"). A loop's start does change its key.

## Decoding

- **Split at the `.`.** The hash part must be 11 base64url characters.
- **In the cell part:**
  - **Character 0** is the version. For v1 it's `1`.
  - **Characters 1–7** give the centroid cell:
    - Read them as a 42-bit number. It must end in 5 zero bits.
    - Shift it right by 5. That leaves the base cell (top 7 bits) and digits 1–10.
    - Build the H3 index from these:
      - mode 1 (cell), resolution 10;
      - the base cell and digits 1–10 from the 37 bits;
      - digits 11–15 all 7 (unused).
    - It must be a valid cell.
  - **Character 8** is the shape.
  - **The rest** are varints, read in pairs as `(i, j)`. Unzigzag each value: an even `z` gives `z / 2`, an odd one `−(z + 1) / 2`. `localIjToCell(centroid, origin + offset)`, where `origin` is the centroid's own local IJ, gives each point's cell.

Anything else is not a v1 key. The hash can't be decoded, only recomputed
from a line and compared.

## Properties, measured

Measured on Hiker Atlas's 59,256 curated routes of its 13 November 2026
north-america build (`scripts/corpus.py`; README, "Design decisions"):

- **Length:** median 35 characters, 95th percentile 43, maximum 57. AT Protocol record keys may be up to 512.
- **Distinctness:** 143 keys are shared, every one by the same line listed twice (in two overlapping parks, or twice in one park). 59,029 distinct cell parts among the 59,110 distinct keys: the hash tells apart lines whose cells match.
- **Exactness:** any change to a line gives a new key, except writing it with more precision. The cell part is more forgiving: moving every point by up to 1 m keeps 86% of cell parts, by up to 3 m 69%. Re-finding a changed route works from the cell part: on 233 real changes between two builds, scoring current routes by how many of the old key's cells their line passes through picked the right one 87% of the time.
