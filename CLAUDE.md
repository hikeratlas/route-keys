# Notes for agents

This repository is the canonical implementation of route keys. Other
repositories (hikeratlas/website, and later the routes build and indexers)
consume it as a library. Keys are stored in people's AT Protocol records as
record keys, so a key can never change meaning.

## Recipe v1 is frozen

- Don't change anything in `python/route_keys`, `ts/src` or `SPEC.md` that
  could change a key or a decoding. That includes "harmless" changes to
  arithmetic: `hypot` for `sqrt`, `sum()` or `fsum` for a loop, reordering
  operations, rounding. A one-ulp difference can move a point into another
  H3 cell.
- Never edit `vectors/v1.json`. Both test suites check its SHA-256; if that
  test fails, the fix is to undo the edit, not to update the hash.
- Fixes that can't change a key are fine: error messages, types,
  documentation, packaging, input validation that only rejects what was
  already invalid. Run both test suites.
- A better recipe is a new one: version character `2`, its own section in
  SPEC.md, its own `vectors/v2.json`, and code that still makes and decodes
  v1 keys unchanged. Ask the maintainer first.

## Consumers

- Use the library. Don't copy the algorithm into another repository.
- TypeScript: a release's tarball, e.g. in package.json
  `"@hikeratlas/route-keys": "https://github.com/hikeratlas/route-keys/releases/download/v1.0.0/hikeratlas-route-keys-1.0.0.tgz"`.
- Python: `pip install "route-keys @ git+https://github.com/hikeratlas/route-keys@v1.0.0#subdirectory=python"`.

## Checks

    python3 -m unittest discover -s python/tests     # from the repository root
    (cd ts && npm ci && npm test && npm run build)

`scripts/examples.py` rebuilds the README's figures and tables (needs h3).
`scripts/corpus.py` measures keys over a routes file that isn't in this
repository. Neither is part of the library.
