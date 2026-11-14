# Notes for agents

This repository is the canonical implementation of route keys. Other
repositories (hikeratlas/website, and later the routes build and indexers)
consume it as a library. Keys are stored in people's AT Protocol records as
record keys, so once recipe v1 is final, a key can never change meaning.

## Recipe v1 is a draft until 1.0

Releases are 0.x while Hiker Atlas tries route keys in a real
implementation, and recipe v1 may still change. From 1.0, it's frozen.

- **Any change that can change a key or a decoding is a recipe change.**
  That includes "harmless" changes to arithmetic: `hypot` for `sqrt`,
  `sum()` or `fsum` for a loop, reordering operations, rounding. A one-ulp
  difference can move a point into another H3 cell.
- **In 0.x, a recipe change is allowed only on purpose, and with the
  maintainer's agreement.** It has to land as one coherent change:
  - SPEC.md and both implementations together;
  - `vectors/v1.json` regenerated with `scripts/make_vectors.py`;
  - the vectors hash updated in both test suites;
  - the README's figures and tables rebuilt (`scripts/examples.py`, `scripts/corpus.py`);
  - a minor version bump.
- **The vectors hash check is a tripwire.** If it fails and you didn't mean
  to change the recipe, undo your change; don't update the hash.
- **From 1.0, never change recipe v1.** A better recipe is v2: version
  character `2`, its own section in SPEC.md, its own `vectors/v2.json`, and
  code that still makes and decodes v1 keys unchanged.
- **Fixes that can't change a key are always fine:** error messages, types,
  documentation, packaging, and input validation that only rejects what was
  already invalid. Run both test suites.

## Releases

Merging to main publishes a release when the version in `ts/package.json`
(and `python/pyproject.toml`, which must match) has none yet
(`.github/workflows/release.yml`). It creates the tag `v<version>` and attaches
the npm tarball. To release, bump both versions in the PR.

## Consumers

- Use the library. Don't copy the algorithm into another repository.
- TypeScript: a release's tarball, e.g. in package.json
  `"@hikeratlas/route-keys": "https://github.com/hikeratlas/route-keys/releases/download/v0.1.0/hikeratlas-route-keys-0.1.0.tgz"`.
- Python: `pip install "route-keys @ git+https://github.com/hikeratlas/route-keys@v0.1.0#subdirectory=python"`.

## Checks

    python3 -m unittest discover -s python/tests     # from the repository root
    (cd ts && npm ci && npm test && npm run build)

`scripts/examples.py` rebuilds the README's figures and tables (needs h3).
`scripts/corpus.py` measures keys over a routes file that isn't in this
repository. Neither is part of the library.
