"""python -m unittest discover -s python/tests (from the repository root)."""
import hashlib
import json
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'python'))
from route_keys import decode, is_route_key, route_key, shape_for  # noqa: E402

VECTORS = os.path.join(ROOT, 'vectors', 'v1.json')
# vectors/v1.json is the contract between implementations: this fails if
# it's edited. A tripwire: read CLAUDE.md before touching it.
V1_SHA256 = '499a7b6db7e312ad6b153a3ceb2cfb0bc0f72aad7f22fe86379b82d29a41bd69'

with open(VECTORS, 'rb') as f:
    RAW = f.read()
VS = json.loads(RAW)['vectors']


class Vectors(unittest.TestCase):
    def test_vectors_unchanged(self):
        self.assertEqual(hashlib.sha256(RAW).hexdigest(), V1_SHA256)

    def test_keys(self):
        for v in VS:
            self.assertEqual(route_key(v['line'], v['shape']), v['key'], v['name'])

    def test_decode(self):
        for v in VS:
            d = decode(v['key'])
            self.assertEqual((d.version, d.centroid, d.shape, d.cells, d.hash), ('1', v['centroid'], v['shape'], v['cells'], v['hash']), v['name'])
            self.assertEqual(v['key'], v['key'].split('.')[0] + '.' + d.hash)

    def test_rounding(self):
        # Coordinates are rounded to 0.00001 degrees first: copies with more
        # decimals, or float noise below that, give the same key.
        for v in VS:
            noisy = [[lon + 2e-7, lat - 3e-7] for lon, lat in v['line']]
            self.assertEqual(route_key(noisy, v['shape']), v['key'], v['name'])

    def test_reversed_lines_have_the_same_key(self):
        for v in VS:
            self.assertEqual(route_key(v['line'][::-1], v['shape']), v['key'], v['name'])


class Inputs(unittest.TestCase):
    def test_not_keys(self):
        h = '.kbwpj6tSIEZ'
        for k in ['', 'abcdefghijklmnop', '1K4RjYPAwNBJ', '2K4RjYPAwNBJ' + h, '1K4RjYPAxNBJ' + h, '1K4RjYP!wNBJ' + h,
                  '1K4RjYPBwNBJ' + h, '1K4RjYPAwN' + h, '1K4RjYPAwNBj' + h, '1K4RjYPAwNBJ.kbwpj6tSIE', '1K4RjYPAwNBJ.kbwpj6tSIEZx',
                  '1K4RjYPAwNBJ.kbwpj6tSI!Z']:
            self.assertFalse(is_route_key(k), k)
            with self.assertRaises(ValueError):
                decode(k)

    def test_bad_arguments(self):
        with self.assertRaises(ValueError):
            route_key([[0, 0]], 'b')
        with self.assertRaises(ValueError):
            route_key([[0, 0], [0, 1]], 'x')
        self.assertTrue(is_route_key(VS[0]['key']))

    def test_shapes(self):
        self.assertEqual([shape_for(k) for k in ['loop', 'out-and-back', 'one-way', 'point-to-point']], ['p', 'b', 'w', 'w'])


if __name__ == '__main__':
    unittest.main()
