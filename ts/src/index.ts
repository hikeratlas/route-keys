// Route keys, recipe v1 (see SPEC.md at the repository root).
//
// A route's identity, computed from its line, so no ids are minted:
//
//   1E57E06gbDEBBBICDGF.k3Xq9vB0aRm
//   \_ cells: decodable _/ \_ hash _/
//
// The cells say where the route is and roughly where it goes; the hash makes
// the key an exact identity of the line.
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
import { sha256 } from '@noble/hashes/sha2';

export type Shape = 'b' | 'p' | 'w';
export type Point = readonly [number, number] | readonly number[]; // [lon, lat]

export const VERSION = '1';
export const RESOLUTION = 10;
const GRID = 100000; // coordinates are rounded to 1 / GRID degrees (~1.1 m)
const HASH_CHARS = 11;
const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'; // base64url

export interface Decoded {
  version: string;
  centroid: string; // H3 cell (resolution 10), hex
  shape: Shape;
  cells: string[]; // the sampled points' distinct cells, in key order
  hash: string; // the line's hash, 11 characters
}

// A route's shape letter from its kind: loop -> p, out-and-back -> b,
// anything else (one-way, point-to-point) -> w.
export const shapeFor = (kind: string): Shape => (kind === 'loop' ? 'p' : kind === 'out-and-back' ? 'b' : 'w');

// Rounded to the nearest 1/GRID degree, halves away from zero.
function quantize(v: number): number {
  const x = v * GRID;
  return x >= 0 ? Math.floor(x + 0.5) : -Math.floor(-x + 0.5);
}

function normalize(line: readonly Point[]): [number, number][] {
  const out: [number, number][] = [];
  for (const p of line) {
    const q: [number, number] = [quantize(p[0]), quantize(p[1])];
    const last = out[out.length - 1];
    if (!last || last[0] !== q[0] || last[1] !== q[1]) out.push(q);
  }
  return out;
}

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

function cellsPart(line: readonly Point[], shape: Shape): string {
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

function digest(q: [number, number][]): Uint8Array {
  const bytes = new Uint8Array(q.length * 8);
  const view = new DataView(bytes.buffer);
  q.forEach(([lon, lat], i) => { view.setInt32(i * 8, lon, true); view.setInt32(i * 8 + 4, lat, true); });
  return sha256(bytes);
}

function hashPart(q: [number, number][]): string {
  const a = digest(q), b = digest([...q].reverse());
  let d = a;
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) { d = a[i] < b[i] ? a : b; break; }
  }
  // base64url of the first 9 bytes (72 bits, 12 characters), cut to 11.
  let out = '';
  for (let i = 0; i < 9; i += 3) {
    const n = (d[i] << 16) | (d[i + 1] << 8) | d[i + 2];
    out += ALPHABET[(n >> 18) & 63] + ALPHABET[(n >> 12) & 63] + ALPHABET[(n >> 6) & 63] + ALPHABET[n & 63];
  }
  return out.slice(0, HASH_CHARS);
}

export function routeKey(line: readonly Point[], shape: Shape): string {
  if (shape !== 'b' && shape !== 'p' && shape !== 'w') throw new Error("shape must be 'b', 'p' or 'w'");
  if (line.length < 2) throw new Error('a line needs at least two points');
  const q = normalize(line);
  return `${cellsPart(q.map(([lon, lat]) => [lon / GRID, lat / GRID]), shape)}.${hashPart(q)}`;
}

const bad = () => new Error('not a v1 route key');

export function decode(key: string): Decoded {
  const dot = key.indexOf('.');
  if (dot < 0) throw bad();
  const cells = key.slice(0, dot), hash = key.slice(dot + 1);
  if (hash.length !== HASH_CHARS || [...hash].some((ch) => ALPHABET.indexOf(ch) < 0)) throw bad();
  if (cells.length < 11 || cells[0] !== VERSION || !'bpw'.includes(cells[8])) throw bad();
  const digits: number[] = [];
  for (const ch of cells) {
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
  const out: string[] = [];
  try {
    for (let k = 0; k < zs.length; k += 2) out.push(localIjToCell(c, { i: o.i + unzigzag(zs[k]), j: o.j + unzigzag(zs[k + 1]) }));
  } catch {
    throw bad();
  }
  return { version: VERSION, centroid: c, shape: cells[8] as Shape, cells: out, hash };
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
