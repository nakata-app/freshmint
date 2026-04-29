# Changelog

All notable changes to **freshmint** are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versions follow
[SemVer](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-04-29

Compatibility hotfix for c2patool 0.26+. The 0.1.0 wrapper passed
`--key` / `--cert` on the command line, which the modern c2patool CLI
no longer accepts; sign / verify against a real binary failed. This
release ports the wrapper to the new shape.

### Changed (breaking against c2patool 0.x, transparent for callers)
- `sign()` now embeds `private_key` and `sign_cert` directly in the
  manifest JSON instead of passing them via removed CLI flags.
  Public Python signature is unchanged.
- `manifest_to_c2pa_json(manifest, *, signing_key, cert, alg)` now
  accepts key / cert / algorithm explicitly. The previous one-arg
  form is gone (internal helper, no public callers).
- `parse_verify_output` rewritten for the modern verify schema
  (`validation_state` + `validation_results.activeManifest` instead
  of the legacy `validation_status` array; `assertion_store` keyed
  by label instead of an `assertions` list).
- `c2pa.created` (or `c2pa.opened`) is now auto-synthesised at the
  head of `c2pa.actions` when the caller provides none. C2PA
  validation requires this for `validation_state=Valid`.
- AI attestation now lands under
  `org.nakata.freshmint.ai_attestation` (custom assertion) and the
  synthesised `c2pa.created` action declares
  `digitalSourceType=trainedAlgorithmicMedia` plus the model name in
  `softwareAgent`, so verifiers reading only `c2pa.actions` still
  see "AI was used".

### Added
- `tests/test_integration.py`, real-binary sign + verify roundtrip,
  AI attestation roundtrip, tamper detection. Auto-skips when
  `c2patool` or `openssl` is missing on the host.
- `cert` parameter is now documented as required for production
  signing (c2patool 0.26+ rejects self-signed certs at embed time).

### Internals
- 21 unit + 3 integration tests, mypy `--strict` clean, ruff clean,
  ~92% coverage.

[0.1.1]: https://github.com/nakata-app/freshmint/releases/tag/v0.1.1

## [0.1.0] - 2026-04-29, DO NOT USE, superseded by 0.1.1

> **Known broken.** Use 0.1.1 instead. This release passed `--key` and
> `--cert` to `c2patool` on the command line, but those flags were
> removed in `c2patool` 0.26 and never restored. Real-binary
> `sign()` / `verify()` calls fail with
> `unexpected argument '--key'`. Unit tests at the time of release
> mocked `subprocess.run` and were green, which masked the regression.
> Fixed in 0.1.1, which moves key / cert into the manifest JSON the
> way modern `c2patool` expects.

### Added (intent at the time of release)
- `freshmint.sign()`, embed a `Manifest` into an image / video / audio
  file, signed with a PEM key. Optional X.509 cert chain.
- `freshmint.verify()`, read and validate a C2PA manifest, returning a
  `VerifyResult` (signer identity, edit history, AI attestation,
  validity flags). Never raises on validation failure, always returns
  a populated result.
- `freshmint.binary.find_c2patool()`, locate the Adobe binary via
  `FRESHMINT_C2PATOOL` env override, `PATH`, Homebrew, or common Linux
  install paths. Clear `C2PAToolNotFound` error with install hints
  when missing.
- `Manifest`, `Action`, `AIAttestation`, `VerifyResult` dataclasses.
- Manifest ↔ c2patool JSON serialization, including `extra_assertions`
  for cluster-specific metadata (e.g. halluguard scores, source image
  hashes).

### Internals
- 16 unit tests (mocked subprocess), mypy `--strict` clean, ruff clean.
- No runtime dependencies; `c2patool` is the only external requirement.

[0.1.0]: https://github.com/nakata-app/freshmint/releases/tag/v0.1.0
