# Security policy

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security-sensitive
findings. Instead, email the maintainer at
**ataknakbaba@gmail.com** with:

- A description of the issue.
- Steps to reproduce (a minimal repro is enough).
- The version / commit you tested against.
- Optionally, your proposed fix.

We aim to acknowledge a report within 72 hours and to ship a fix in
the next minor release where applicable.

## Scope

The Python package itself is the in-scope surface: `sign`, `verify`,
manifest serialization, and the `c2patool` subprocess wrapper.

Out of scope:
- Bugs in Adobe `c2patool` itself. Report those to
  [contentauth/c2patool](https://github.com/contentauth/c2patool).
- Bugs in the C2PA spec / COSE / CBOR. Report upstream.
- Performance issues without a security impact (file regular issues
  instead).

## Threat model

freshmint shells out to a trusted local `c2patool` binary and reads /
writes files on the local filesystem. It does not open network
sockets. The expected callers are:

- A renderer (e.g. Sienna) signing its own output with a key it
  controls.
- A verifier reading a third-party file and validating its manifest.

**Untrusted input:** the file passed to `verify()` is treated as
untrusted. Manifests can claim arbitrary signer identities, edit
histories, and AI attestations; callers must check
`VerifyResult.cert_chain_valid` and the signer identity against an
allowlist before trusting the claims.

**Trusted input:** the manifest passed to `sign()` and the signing
key. Don't sign data you didn't generate; don't reuse signing keys
across tenants.

## Key handling

freshmint never reads, copies, or persists signing keys outside the
file you pass to `sign()`. The key path is forwarded to `c2patool` and
nothing else.
