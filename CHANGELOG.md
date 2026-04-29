# Changelog

All notable changes to **freshmint** are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versions follow
[SemVer](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-04-29

First working release. Sign and verify both produce real C2PA manifests
when an Adobe `c2patool` binary is present on the host.

### Added
- `freshmint.sign()`, embed a `Manifest` into an image / video / audio
  file, signed with a PEM key. Optional X.509 cert chain; falls back to
  c2patool's self-signed prototype cert when omitted.
- `freshmint.verify()`, read and validate a C2PA manifest, returning a
  `VerifyResult` (signer identity, edit history, AI attestation, validity
  flags). Never raises on validation failure, always returns a populated
  result.
- `freshmint.binary.find_c2patool()`, locate the Adobe binary via
  `FRESHMINT_C2PATOOL` env override, `PATH`, Homebrew, or common Linux
  install paths. Clear `C2PAToolNotFound` error with install hints when
  missing.
- `Manifest`, `Action`, `AIAttestation`, `VerifyResult` dataclasses.
- Manifest ↔ c2patool JSON serialization, including `extra_assertions`
  for cluster-specific metadata (e.g. halluguard scores, source image
  hashes).

### Internals
- 16 unit tests, mypy `--strict` clean, ruff clean.
- No runtime dependencies; `c2patool` is the only external requirement.

[0.1.0]: https://github.com/nakata-app/freshmint/releases/tag/v0.1.0
