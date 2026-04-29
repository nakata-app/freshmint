# Contributing to freshmint

Thanks for considering a contribution. The repo is small enough that the
review pipeline is short, keep changes focused, the bar is "honest
behavior + clear tradeoffs."

## Quickstart for a local dev loop

```bash
git clone https://github.com/nakata-app/freshmint.git
cd freshmint
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
brew install c2patool        # Mac. See README for Linux / Windows.
```

## What we run before every commit

```bash
ruff check freshmint tests             # lint
mypy --strict freshmint                # type check
pytest -q                              # unit tests (no c2patool needed)
```

CI runs the same three on Python 3.10 / 3.11 / 3.12. A PR that doesn't
pass them locally won't pass CI either.

The unit suite stubs out `c2patool` so it runs anywhere. Real
sign / verify smoke tests need the binary installed.

## What lands easily

- Bug fixes with a regression test that fails before / passes after.
- New `Manifest` / `VerifyResult` fields driven by a real C2PA spec
  field, mapped through `manifest_to_c2pa_json` / `parse_verify_output`.
- New `extra_assertions` plumbing for cluster-specific metadata
  (halluguard scores, claimcheck verdicts, source-image hashes).
- Documentation, especially worked examples for sign / verify against a
  known-good C2PA fixture.

## What needs a discussion first

- Anything that changes the public surface (`sign`, `verify`,
  `Manifest`, `VerifyResult`, `Action`, `AIAttestation`).
- Replacing the c2patool subprocess with a pure-Python COSE/CBOR
  implementation. v1.0 may do this; the public signatures must stay
  stable across the swap.
- New required dependencies. The core install has none on purpose,
  c2patool is the only external requirement.

## Style

- Match the existing code. Type hints on public surfaces; no
  speculative abstractions; comments only for non-obvious WHY.
- One commit per logical change. Squash if you accumulate "fix
  comments" commits.
- Commit messages: imperative mood, short subject ("add detached
  manifest support"), longer body if the change is non-trivial.

## Reporting bugs

GitHub Issues. Include:
- Python version + OS.
- `c2patool --version` output if the bug touches sign / verify.
- The minimum reproduction (manifest snippet + sample file path is
  enough; please don't attach signed assets that contain real keys).
- What you expected vs what you got.

## Reporting security issues

See [`SECURITY.md`](SECURITY.md). Don't open a public issue for an
unpatched vulnerability.
