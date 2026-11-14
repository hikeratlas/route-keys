// npm test (in ts/): the TypeScript implementation against vectors/v1.json.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { centroidOf, decode, isRouteKey, routeKey, shapeFor } from '../src/index.ts';
import { latLngToCell } from 'h3-js';

// vectors/v1.json is the contract between implementations: this fails if
// it's edited. A tripwire: read CLAUDE.md before touching it.
const V1_SHA256 = '499a7b6db7e312ad6b153a3ceb2cfb0bc0f72aad7f22fe86379b82d29a41bd69';
const raw = readFileSync(new URL('../../vectors/v1.json', import.meta.url));
const { vectors } = JSON.parse(raw.toString('utf8'));

test('vectors unchanged', () => assert.equal(createHash('sha256').update(raw).digest('hex'), V1_SHA256));

test('keys', () => {
  for (const v of vectors) assert.equal(routeKey(v.line, v.shape), v.key, v.name);
});

test('decode', () => {
  for (const v of vectors) assert.deepEqual(decode(v.key), { version: '1', centroid: v.centroid, shape: v.shape, cells: v.cells, hash: v.hash }, v.name);
});

test('centroidOf is in the centroid cell', () => {
  for (const v of vectors) {
    const c = centroidOf(v.key);
    assert.ok(c, v.name);
    assert.equal(latLngToCell(c[1], c[0], 10), v.centroid, v.name);
  }
});

test('rounding: more decimals or float noise give the same key', () => {
  for (const v of vectors) assert.equal(routeKey(v.line.map(([lon, lat]) => [lon + 2e-7, lat - 3e-7]), v.shape), v.key, v.name);
});

test('reversed lines have the same key', () => {
  for (const v of vectors) assert.equal(routeKey([...v.line].reverse(), v.shape), v.key, v.name);
});

test('not keys', () => {
  const h = '.kbwpj6tSIEZ';
  for (const k of ['', 'abcdefghijklmnop', '1K4RjYPAwNBJ', '2K4RjYPAwNBJ' + h, '1K4RjYPAxNBJ' + h, '1K4RjYP!wNBJ' + h,
    '1K4RjYPBwNBJ' + h, '1K4RjYPAwN' + h, '1K4RjYPAwNBj' + h, '1K4RjYPAwNBJ.kbwpj6tSIE', '1K4RjYPAwNBJ.kbwpj6tSIEZx',
    '1K4RjYPAwNBJ.kbwpj6tSI!Z']) {
    assert.equal(isRouteKey(k), false, k);
    assert.throws(() => decode(k), k);
    assert.equal(centroidOf(k), null, k);
  }
});

test('bad arguments', () => {
  assert.throws(() => routeKey([[0, 0]], 'b'));
  assert.throws(() => routeKey([[0, 0], [0, 1]], 'x'));
});

test('shapes', () => {
  assert.deepEqual(['loop', 'out-and-back', 'one-way', 'point-to-point'].map(shapeFor), ['p', 'b', 'w', 'w']);
});
