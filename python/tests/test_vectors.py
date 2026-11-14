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
# vectors/v1.json is the contract between implementations, and frozen: this
# fails if it's edited. Read CLAUDE.md before touching it.
V1_SHA256 = '1fc2c62e7daa06ceb8fdcfcc3f326ed72ac5a4bda459ad271f4592e80efe6e3f'

with open(VECTORS, 'rb') as f:
    RAW = f.read()
VS = json.loads(RAW)['vectors']


class Vectors(unittest.TestCase):
    def test_frozen(self):
        self.assertEqual(hashlib.sha256(RAW).hexdigest(), V1_SHA256)

    def test_keys(self):
        for v in VS:
            self.assertEqual(route_key(v['line'], v['shape']), v['key'], v['name'])

    def test_decode(self):
        for v in VS:
            d = decode(v['key'])
            self.assertEqual((d.version, d.centroid, d.shape, d.cells), ('1', v['centroid'], v['shape'], v['cells']), v['name'])

    def test_reversed_lines_have_the_same_key(self):
        for v in VS:
            self.assertEqual(route_key(v['line'][::-1], v['shape']), v['key'], v['name'])


class Inputs(unittest.TestCase):
    def test_not_keys(self):
        for k in ['', 'abcdefghijklmnop', '2K4RjYPAwNBJ', '1K4RjYPAxNBJ', '1K4RjYP!wNBJ', '1K4RjYPBwNBJ', '1K4RjYPAwN', '1K4RjYPAwNBj']:
            self.assertFalse(is_route_key(k), k)
            with self.assertRaises(ValueError):
                decode(k)

    def test_bad_arguments(self):
        with self.assertRaises(ValueError):
            route_key([[0, 0]], 'b')
        with self.assertRaises(ValueError):
            route_key([[0, 0], [0, 1]], 'x')

    def test_shapes(self):
        self.assertEqual([shape_for(k) for k in ['loop', 'out-and-back', 'one-way', 'point-to-point']], ['p', 'b', 'w', 'w'])


if __name__ == '__main__':
    unittest.main()
