# freshmint

**Sign every AI-generated image with verifiable provenance — no detection arms race, just cryptographic truth.**

> Status: **early draft / vision document.** No working signer yet. v0.1
> will wrap the Adobe `c2patool` Rust SDK in a Pythonic API + add cluster-
> friendly extras (batch sign, FastAPI server, AI-attestation flag).

7th sibling in the no-LLM-judge cluster. Where halluguard / imageguard /
promptguard catch AI **mistakes**, freshmint shifts the conversation:
**stop asking "is this AI?", start cryptographically signing every output
with what it actually is.**

---

## The problem detection can't solve

In 2026, no AI image detector reliably tells AI apart from real:

- 2023 detectors: ~%90 accurate
- 2024: ~%70
- 2025-2026: ~%55-60 (coin flip)

Modern Flux / MJ v7 / gpt-image-2 outputs evade every classical signal
(GAN artifacts, frequency analysis, CLIP fingerprints). Watermark
attempts (C2PA, SynthID) only get adopted by a few large labs — open
models bypass them.

**Detection lost. Provenance can win.**

## What freshmint does

Adopts the **C2PA standard** (Coalition for Content Provenance and
Authenticity) — Adobe + Microsoft + Sony + Nikon + BBC + Truepic +
Intel since 2021. Cryptographically signs every image / video / audio
with:

- Who made it (cert chain, optional pseudonymous identity)
- What tool / device captured it
- Whether AI was involved (and which model, prompt hash)
- Edit history (each transformation logged)
- Tamper detection (any pixel change after signing breaks the seal)

Verifiers (browsers, journalism tools, courts) read the manifest, see
**proof** rather than guess.

## API sketch (v0.1 target)

```python
from freshmint import Manifest, sign, verify

# Sign — content creator side
manifest = Manifest(
    creator="atakan@studio.com",
    title="İstanbul gün batımı",
    actions=[
        {"action": "c2pa.created", "device": "Sony A7IV", "ts": "2026-04-27T14:32"},
        {"action": "c2pa.edited", "tool": "Lightroom", "edits": ["exposure"]},
    ],
    ai_used=False,  # honest — claiming false here breaks the chain
)
signed_path = sign("input.jpg", manifest, signing_key="key.pem")

# AI render side — be honest about it
manifest = Manifest(
    creator="sienna@nakata-app.com",
    title="Render of SKU-1002",
    ai_used=True,
    ai_attestation={
        "model": "flux-pro-1.1",
        "prompt_hash": "sha256:abc...",
        "packshot_source": "SKU-1002.jpg",
        "seed": 4839,
    },
)
sign("render.jpg", manifest, signing_key="key.pem")

# Verify — any consumer side
result = verify("downloaded.jpg")
result.is_valid          # cryptographic signature OK
result.tampered          # bytes changed since signing
result.creator           # signer identity
result.ai_used           # was AI involved?
result.ai_model          # which model?
result.actions           # full edit history
result.cert_chain_valid  # chain back to a trusted root CA
```

## Why this approach actually works

1. **Standard exists.** C2PA isn't speculation — Adobe Photoshop,
   Lightroom, Microsoft Edge, BBC, Sony Alpha cameras, all already
   write/read it.
2. **EU AI Act direction** mandates AI-content disclosure. C2PA is
   the closest thing to a working compliance answer.
3. **Detection is dead.** Every dollar spent on detection is wasted
   when the next model release breaks it. Cryptography doesn't break.
4. **Open ecosystem**: open-source verifier means any newsroom, any
   user, can check independently — no platform monopoly.

## The market gap freshmint fills

| Language | C2PA SDK |
|---|---|
| Rust    | ✓ official (Adobe `c2pa-rs`) |
| JavaScript | ✓ official (Adobe `c2pa-js`) |
| C++ / Swift | ✓ via FFI |
| **Python** | ❌ **none. Just an Adobe CLI binary.** |

Python developers (the ML / AI tooling crowd, the people who actually
need to sign AI outputs) are stuck calling `subprocess.run(["c2patool",
...])` and parsing JSON by hand.

**freshmint = pythonic wrapper + sensible defaults + cluster-friendly
extras** (batch sign, FastAPI server, AI-attestation helpers).

## Cluster fit

```
adaptmem    — domain-tuned retrieval
halluguard  — text hallucination guard
truthcheck  — open-world fact check
promptguard — input gate (prompt injection)
imageguard  — image hallucination
claimcheck  — orchestration
freshmint   — cryptographic provenance ← bu
```

Imageguard catches AI errors after the fact. Freshmint signs **before**
distribution so consumers don't have to detect at all — they verify.

## What v0.0 ships (this commit)

Stable types + API surface. `sign()` and `verify()` raise
`NotImplementedError` pointing at v0.1. Callers can write integration
code today against the contract that won't change.

## What v0.1 ships (1-2 weeks)

- Adobe `c2patool` subprocess wrapper (Mac/Linux binary autodetect)
- `sign(path, manifest)` end-to-end working
- `verify(path)` returns full `VerifyResult`
- Error handling for missing binary, broken cert, tampered file
- AI-attestation helpers (model, prompt hash, seed embedded automatically)
- 15+ integration tests

## Out of scope (until later)

- Pure-Python COSE/CBOR implementation (v1.0 — reduces Adobe binary dep)
- Browser extension UI for verifier (v0.4)
- Ledger-backed manifest registry (v0.5 — distributed verification)

## Open design questions

1. **Identity model**: anonymous keys (anyone can sign anything),
   pseudonymous (key tied to handle), or PKI (cert chain back to a
   real-world identity)? Default and opt-ins?
2. **Key custody**: ship with `keygen` helper? Recommend hardware key?
   Integrate with existing PKI (e.g. company CA)?
3. **Manifest schema extensions**: cluster-specific fields beyond stock
   C2PA (e.g. `claimcheck_verdict`, `imageguard_score`)?
4. **Server mode**: `freshmint serve` daemon for batch signing API,
   like `adaptmem serve`?
5. **Verifier UI**: browser extension (v0.4) or just CLI?
6. **Revocation handling**: how to mark a signed artifact as "creator
   later disowned this"? OCSP-style? Pub/sub?
7. **Storage of public keys**: local trust store, KMS, or distributed
   ledger?

## License

MIT (planned).

## Status

Pre-v0.1. README is the design doc. Atakan-gated public-flip when
the design questions are resolved + first calibration with real
signed/unsigned artifacts is done.
