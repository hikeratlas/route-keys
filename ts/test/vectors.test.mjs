// npm test (in ts/): the TypeScript implementation against vectors/v1.json.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { centroidOf, decode, isRouteKey, routeKey, shapeFor } from '../src/index.ts';
import { latLngToCell } from 'h3-js';

// vectors/v1.json is the contract between implementations, and frozen: this
// fails if it's edited. Read CLAUDE.md before touching it.
const V1_SHA256 = '1fc2c62e7daa06ceb8fdcfcc3f326ed72ac5a4bda459ad271f4592e80efe6e3f';
const raw = readFileSync(new URL('../../vectors/v1.json', import.meta.url));
const { vectors } = JSON.parse(raw.toString('utf8'));

test('vectors are frozen', () => assert.equal(createHash('sha256').update(raw).digest('hex'), V1_SHA256));

test('keys', () => {
  for (const v of vectors) assert.equal(routeKey(v.line, v.shape), v.key, v.name);
});

test('decode', () => {
  for (const v of vectors) assert.deepEqual(decode(v.key), { version: '1', centroid: v.centroid, shape: v.shape, cells: v.cells }, v.name);
});

test('centroidOf is in the centroid cell', () => {
  for (const v of vectors) {
    const c = centroidOf(v.key);
    assert.ok(c, v.name);
    assert.equal(latLngToCell(c[1], c[0], 10), v.centroid, v.name);
  }
});

test('reversed lines have the same key', () => {
  for (const v of vectors) assert.equal(routeKey([...v.line].reverse(), v.shape), v.key, v.name);
});

test('not keys', () => {
  for (const k of ['', 'abcdefghijklmnop', '2K4RjYPAwNBJ', '1K4RjYPAxNBJ', '1K4RjYP!wNBJ', '1K4RjYPBwNBJ', '1K4RjYPAwN', '1K4RjYPAwNBj']) {
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
