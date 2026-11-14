# Route keys: recipe v1

This is the normative definition. `python/route_keys` and `ts/src` implement
it, and `vectors/v1.json` is the contract between them: an implementation is
correct when it gives every vector's key from its line and shape, and
decodes every key to its centroid and cells.

Recipe v1 is frozen. A change to anything below that changes a key would
make a different recipe. That would be v2, with its own version character,
document and vectors; v1 keys stay valid forever (see CLAUDE.md).

## Input

- **line:** two or more points, `[longitude, latitude]` in degrees (WGS 84).
- **shape:** one character:
  - `b`: out-and-back;
  - `p`: loop;
  - `w`: one-way (anything else, such as point-to-point).

  `shape_for(kind)` maps a kind: `loop` gives `p`, `out-and-back` gives `b`, anything else gives `w`.

## Arithmetic

Use IEEE 754 doubles, operations in the order written here, and:

- **Distance** between points `a` and `b`, in metres:
  - `k = cos(radians((a.lat + b.lat) / 2))`
  - `dx = (a.lon − b.lon) × k`
  - `dy = a.lat − b.lat`
  - distance = `sqrt(dx × dx + dy × dy) × 111320`

  Use `sqrt`, not `hypot`, whose rounding varies between libraries.
- **Sums** are plain, left to right. Python's `sum()` of floats is compensated, so don't use it.

A rounding difference can move a point across a cell boundary, and so change a key.

## Points along the line

1. Let `seg[i]` be the distance from point `i` to point `i+1`, and `total` their plain sum.
2. If `total` is 0, use 1.
3. The point at fraction `f` is found as follows:
   - Let `goal = total × f`.
   - Walk the segments in order, keeping `run`, the sum of the segments before the current one.
   - Stop at the first segment with `run + seg[i] ≥ goal` and `seg[i] > 0`.
   - The point is `a + (b − a) × t`, with `t = (goal − run) / seg[i]`, interpolating longitude and latitude linearly between the segment's ends `a` and `b`.
   - If no segment qualifies, it's the line's last point.

## The key

All characters come from the base64url alphabet (RFC 4648 §5):
`ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_`. Character
`n` of the alphabet is digit `n`.

1. **Version:** the character `1`.
2. **Centroid** (7 characters):
   - Take the points at fractions `i / 20` for `i = 0 … 20`, and average their longitudes and latitudes (plain sums, divided by 21).
   - Take the H3 cell containing the average, at resolution 10 (`latLngToCell(lat, lon, 10)`).
   - Take its 37 meaningful bits: the 7-bit base cell, then resolution digits 1 to 10, 3 bits each, most significant first.
   - Shift left by 5 (to 42 bits) and write as 7 digits, most significant first. The key's prefix is then a coarser area.
3. **Shape:** the shape character.
4. **Points:**
   - Take the points at fractions `k / 8` for `k = 0 … 8`, and their resolution-10 cells.
   - For each cell, take its offset from the centroid's cell in H3's local IJ coordinates: `cellToLocalIj(centroid, cell)` minus `cellToLocalIj(centroid, centroid)`.
   - Keep the distinct offsets, sorted by `i`, then `j`.
   - Write each offset's `i`, then its `j`:
     - zigzag-encode the integer: `v ≥ 0` gives `2v`, otherwise `−2v − 1`;
     - write the result as a varint: 5 bits a digit, least significant first, adding 32 to every digit but the last.

Every key has at least one offset, so at least 11 characters. Reversing a
line gives the same key: the points at `k/8` of the line are the points at
`1 − k/8` of its reverse, and they're kept as a set. This is by design: a key
names a path, not a direction of travel (README, "How keys behave"). A loop's
start does change its key.

## Decoding

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

Anything else is not a v1 key.

## Properties, measured

All measured on Hiker Atlas's 59,256 curated routes of its 13 November 2026
north-america build, by `scripts/corpus.py` and the earlier analysis in
hikeratlas/website#130:

- **Length:** median 23 characters, 95th percentile 31, maximum 45. Record keys in AT Protocol may be up to 512, and under 80 is recommended.
- **Distinctness:** no two routes whose lines overlap less than 70% share a key. 222 keys are shared, all by the same route twice: one route listed in two overlapping parks, or near-identical variants.
- **Exactness:** a key identifies a line, not a route in the abstract. Moving every point by up to 1 m changes 12% of keys, by up to 3 m 31%, by up to 10 m 68%. Even then the centroid cell is kept 95–100% of the time, and most points' cells too. So find nearby keys by their decoded cells, not by equality.
