## What this changes

<!-- one-paragraph summary; link to a tracking issue if there is one -->

## How it was tested

<!-- pytest output, a manual sign / verify repro, or a manifest fixture -->

## Checklist

- [ ] `ruff check freshmint tests` is clean
- [ ] `mypy --strict freshmint` is clean
- [ ] `pytest -q` passes locally
- [ ] CHANGELOG entry added (under `[Unreleased]`)
- [ ] If this changes the public API (`sign`, `verify`, `Manifest`,
      `VerifyResult`): README updated
- [ ] If this adds a dependency: it's an `[optional]` extra unless
      truly core
