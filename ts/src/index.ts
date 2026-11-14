// Route keys, recipe v1 (see SPEC.md at the repository root).
//
// A route's identity, computed from its line, so no ids are minted: the same
// line always gives the same key.
//
//   routeKey(line, shape): string   line: [[lon, lat], ...]; shape: 'b' | 'p' | 'w'
//   decode(key): Decoded            throws for anything not a v1 key
//   isRouteKey(key): boolean
//   centroidOf(key): [lon, lat] | null
//   shapeFor(kind): Shape
//
// This and the Python implementation (python/route_keys) must agree to the
// character; vectors/v1.json is the contract both are tested against. Recipe
// v1 is frozen: see CLAUDE.md before changing anything here.
import { cellToLatLng, cellToLocalIj, isValidCell, latLngToCell, localIjToCell } from 'h3-js';

export type Shape = 'b' | 'p' | 'w';
export type Point = readonly [number, number] | readonly number[]; // [lon, lat]

export const VERSION = '1';
export const RESOLUTION = 10;
const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'; // base64url

export interface Decoded {
  version: string;
  centroid: string; // H3 cell (resolution 10), hex
  shape: Shape;
  cells: string[]; // the sampled points' distinct cells, in key order
}

// A route's shape letter from its kind: loop -> p, out-and-back -> b,
// anything else (one-way, point-to-point) -> w.
export const shapeFor = (kind: string): Shape => (kind === 'loop' ? 'p' : kind === 'out-and-back' ? 'b' : 'w');

function metres(a: Point, b: Point): number {
  const k = Math.cos((((a[1] + b[1]) / 2) * Math.PI) / 180);
  const dx = (a[0] - b[0]) * k;
  const dy = a[1] - b[1];
  return Math.sqrt(dx * dx + dy * dy) * 111320;
}

function along(line: readonly Point[], frac: number, segs: number[], total: number): [number, number] {
  const goal = total * frac;
  let run = 0;
  for (let i = 0; i < segs.length; i++) {
    const s = segs[i];
    if (run + s >= goal && s > 0) {
      const t = (goal - run) / s;
      const a = line[i], b = line[i + 1];
      return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
    }
    run += s;
  }
  const last = line[line.length - 1];
  return [last[0], last[1]];
}

const cell = (p: Point) => latLngToCell(p[1], p[0], RESOLUTION);
const zigzag = (v: number) => (v >= 0 ? 2 * v : -2 * v - 1);
const unzigzag = (z: number) => (z % 2 === 0 ? z / 2 : -(z + 1) / 2);

export function routeKey(line: readonly Point[], shape: Shape): string {
  if (shape !== 'b' && shape !== 'p' && shape !== 'w') throw new Error("shape must be 'b', 'p' or 'w'");
  if (line.length < 2) throw new Error('a line needs at least two points');
  const segs: number[] = [];
  for (let i = 0; i + 1 < line.length; i++) segs.push(metres(line[i], line[i + 1]));
  let total = 0;
  for (const s of segs) total += s;
  if (total === 0) total = 1;
  let sx = 0, sy = 0;
  for (let i = 0; i < 21; i++) {
    const q = along(line, i / 20, segs, total);
    sx += q[0];
    sy += q[1];
  }
  const c = cell([sx / 21, sy / 21]);
  const n = BigInt(`0x${c}`);
  let v = (n >> 45n) & 0x7fn;
  for (let r = 1; r <= RESOLUTION; r++) v = (v << 3n) | ((n >> BigInt((15 - r) * 3)) & 7n);
  v <<= 5n;
  let out = VERSION;
  for (let k = 0; k < 7; k++) out += ALPHABET[Number((v >> BigInt(6 * (6 - k))) & 63n)];
  out += shape;
  const o = cellToLocalIj(c, c);
  const seen = new Set<string>();
  const offs: [number, number][] = [];
  for (let k = 0; k < 9; k++) {
    const ij = cellToLocalIj(c, cell(along(line, k / 8, segs, total)));
    const off: [number, number] = [ij.i - o.i, ij.j - o.j];
    const id = `${off[0]},${off[1]}`;
    if (!seen.has(id)) { seen.add(id); offs.push(off); }
  }
  offs.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  for (const off of offs) {
    for (let z of off.map(zigzag)) {
      for (;;) {
        const d = z % 32;
        z = Math.floor(z / 32);
        out += ALPHABET[d | (z ? 32 : 0)];
        if (!z) break;
      }
    }
  }
  return out;
}

const bad = () => new Error('not a v1 route key');

export function decode(key: string): Decoded {
  if (key.length < 11 || key[0] !== VERSION || !'bpw'.includes(key[8])) throw bad();
  const digits: number[] = [];
  for (const ch of key) {
    const d = ALPHABET.indexOf(ch);
    if (d < 0) throw bad();
    digits.push(d);
  }
  let v = 0n;
  for (const d of digits.slice(1, 8)) v = (v << 6n) | BigInt(d);
  if (v & 31n) throw bad();
  v >>= 5n;
  let n = (1n << 59n) | (BigInt(RESOLUTION) << 52n) | ((v >> 30n) << 45n);
  for (let r = 1; r <= 15; r++) {
    const d = r <= RESOLUTION ? (v >> BigInt(3 * (RESOLUTION - r))) & 7n : 7n;
    n |= d << BigInt((15 - r) * 3);
  }
  const c = n.toString(16);
  if (!isValidCell(c)) throw bad();
  const zs: number[] = [];
  let z = 0, mul = 1;
  for (const d of digits.slice(9)) {
    z += (d & 31) * mul;
    mul *= 32;
    if (!(d & 32)) { zs.push(z); z = 0; mul = 1; }
  }
  if (mul !== 1 || !zs.length || zs.length % 2) throw bad();
  const o = cellToLocalIj(c, c);
  const cells: string[] = [];
  try {
    for (let k = 0; k < zs.length; k += 2) cells.push(localIjToCell(c, { i: o.i + unzigzag(zs[k]), j: o.j + unzigzag(zs[k + 1]) }));
  } catch {
    throw bad();
  }
  return { version: VERSION, centroid: c, shape: key[8] as Shape, cells };
}

export function isRouteKey(key: string): boolean {
  try { decode(key); return true; } catch { return false; }
}

// The centre of a key's centroid cell, [lon, lat]: where its route roughly
// is. Null for anything not a v1 key.
export function centroidOf(key: string): [number, number] | null {
  try {
    const [lat, lon] = cellToLatLng(decode(key).centroid);
    return [lon, lat];
  } catch {
    return null;
  }
}
