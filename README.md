# freshmint

**Pythonic C2PA, sign every AI-generated image with verifiable provenance, no detection arms race, just cryptographic truth.**

[![CI](https://github.com/nakata-app/freshmint/actions/workflows/ci.yml/badge.svg)](https://github.com/nakata-app/freshmint/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

7th sibling in the no-LLM-judge cluster. Where halluguard / imageguard /
promptguard catch AI **mistakes**, freshmint shifts the conversation:
**stop asking "is this AI?", start cryptographically signing every output
with what it actually is.**

---

## The problem detection can't solve

In 2026, no AI image detector reliably tells AI apart from real:

- 2023 detectors: ~90% accurate
- 2024: ~70%
- 2025-2026: ~55-60% (coin flip)

Modern Flux / MJ v7 / gpt-image-2 outputs evade every classical signal
(GAN artifacts, frequency analysis, CLIP fingerprints). Watermark
attempts (C2PA, SynthID) only get adopted by a few large labs, open
models bypass them.

**Detection lost. Provenance can win.**

## What freshmint does

Adopts the **C2PA standard** (Coalition for Content Provenance and
Authenticity, Adobe + Microsoft + Sony + Nikon + BBC + Truepic + Intel
since 2021). Cryptographically signs every image / video / audio with:

- Who made it (cert chain, optional pseudonymous identity)
- What tool / device captured it
- Whether AI was involved (and which model, prompt hash)
- Edit history (each transformation logged)
- Tamper detection (any pixel change after signing breaks the seal)

Verifiers (browsers, journalism tools, courts) read the manifest, see
**proof** rather than guess.

## Install

```bash
pip install freshmint
```

freshmint shells out to Adobe's `c2patool` for sign / verify, install it
once on the host:

```bash
# Mac
brew install c2patool

# Linux / Windows: download a release binary
# https://github.com/contentauth/c2patool/releases
# and either put it on PATH or set FRESHMINT_C2PATOOL=/path/to/c2patool
```

The Python package itself has zero runtime dependencies.

## Usage

```python
from freshmint import AIAttestation, Manifest, sign, verify

# Sign, AI render side, be honest about it
manifest = Manifest(
    creator="sienna@nakata-app.com",
    title="Render of SKU-1002",
    ai_used=True,
    ai_attestation=AIAttestation(
        model="flux-pro-1.1",
        prompt_hash="sha256:abc...",
        source_image="SKU-1002.jpg",
        seed=4839,
    ),
)
signed_path = sign("render.png", manifest, signing_key="key.pem")

# Verify, any consumer side
result = verify(signed_path)
result.is_valid           # cryptographic signature OK
result.tampered           # bytes changed since signing
result.creator            # signer identity
result.ai_used            # was AI involved?
result.ai_attestation     # which model, what prompt, what source
result.actions            # full edit history
result.cert_chain_valid   # chain back to a trusted root CA
```

`sign()` falls back to c2patool's self-signed prototype cert when no
`cert=` is passed, fine for development, swap in a real X.509 chain
before shipping signed artifacts to consumers.

## Why this approach actually works

1. **Standard exists.** C2PA isn't speculation, Adobe Photoshop,
   Lightroom, Microsoft Edge, BBC, Sony Alpha cameras already write /
   read it.
2. **EU AI Act direction** mandates AI-content disclosure. C2PA is the
   closest thing to a working compliance answer.
3. **Detection is dead.** Every dollar spent on detection is wasted
   when the next model release breaks it. Cryptography doesn't break.
4. **Open ecosystem.** Open-source verifier means any newsroom, any
   user, can check independently, no platform monopoly.

## The market gap freshmint fills

| Language    | C2PA SDK                              |
| ----------- | ------------------------------------- |
| Rust        | official (Adobe `c2pa-rs`)            |
| JavaScript  | official (Adobe `c2pa-js`)            |
| C++ / Swift | via FFI                               |
| **Python**  | **none, just an Adobe CLI binary.**   |

Python developers (the ML / AI tooling crowd, the people who actually
need to sign AI outputs) are stuck calling `subprocess.run(["c2patool",
...])` and parsing JSON by hand.

**freshmint = pythonic wrapper + sensible defaults + cluster-friendly
extras** (`extra_assertions` plumbing for halluguard / claimcheck /
imageguard metadata).

## Cluster fit

```
adaptmem, domain-tuned retrieval
halluguard, text hallucination guard
truthcheck, open-world fact check
promptguard, input gate (prompt injection)
imageguard, image hallucination
claimcheck, orchestration
freshmint, cryptographic provenance ← bu
```

Imageguard catches AI errors after the fact. Freshmint signs **before**
distribution so consumers don't have to detect at all, they verify.

## What v0.1 ships

- Adobe `c2patool` subprocess wrapper with binary autodetect (env
  override → PATH → Homebrew → Linux package paths)
- `sign(path, manifest, signing_key)` end-to-end working
- `verify(path)` returns a populated `VerifyResult`
- Clear errors for missing binary, missing key, c2patool non-zero exit
- AI-attestation helpers (model, prompt hash, source image, seed)
- 16 unit tests, mypy `--strict`, ruff clean
- Zero runtime dependencies

## Roadmap

- **v0.2**: detached manifests, batch sign helper, more `extra_assertions`
  bindings for cluster siblings.
- **v0.3**: `freshmint serve` FastAPI daemon for batch signing.
- **v0.4**: browser-extension companion verifier.
- **v1.0**: pure-Python COSE / CBOR backend, drop the c2patool subprocess
  dependency. Public signatures stay stable across the swap.

## License

[MIT](LICENSE).

## Security

See [`SECURITY.md`](SECURITY.md). Don't open public issues for
vulnerabilities.
