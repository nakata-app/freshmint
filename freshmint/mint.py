"""sign / verify entry points — skeleton, raises NotImplementedError until v0.1.

v0.1 will wrap the Adobe `c2patool` binary via subprocess. v1.0 may
move to a pure-Python COSE/CBOR implementation to drop the binary
dependency. Either way the signatures below stay stable.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from freshmint.types import Manifest, VerifyResult


def sign(
    input_path: str | Path,
    manifest: Manifest,
    signing_key: str | Path,
    output_path: str | Path | None = None,
    *,
    cert: str | Path | None = None,
    **_: Any,
) -> Path:
    """Embed a C2PA manifest into ``input_path`` and write the signed file.

    Args:
        input_path: image / video / audio to sign (must be a C2PA-supported
            container — JPEG, PNG, WebP, MP4, WAV, etc).
        manifest: declarations to embed (creator, actions, ai_used, …).
        signing_key: path to a PEM private key.
        output_path: where to write the signed file. Defaults to
            ``<input>.signed.<ext>`` next to the source.
        cert: optional X.509 cert chain (PEM). When omitted, a self-
            signed cert is generated — fine for prototypes, useless for
            external trust.

    Returns:
        Path to the signed file.

    Raises:
        NotImplementedError: until v0.1 lands.
    """
    raise NotImplementedError(
        "freshmint is at v0.0 — only types and the API surface are stable. "
        "v0.1 will wrap Adobe `c2patool` to do real signing. Track progress "
        "at https://github.com/nakata-app/freshmint (when public)."
    )


def verify(input_path: str | Path, **_: Any) -> VerifyResult:
    """Read and validate the C2PA manifest in ``input_path``.

    Returns:
        ``VerifyResult`` populated with signer identity, edit history,
        AI attestation (if present), and validation flags. Always
        returns — never raises on validation failure; check
        ``result.is_valid`` and ``result.error`` instead.

    Raises:
        FileNotFoundError: if ``input_path`` doesn't exist (v0.1).
        NotImplementedError: until v0.1 lands.
    """
    raise NotImplementedError(
        "freshmint is at v0.0 — only types and the API surface are stable. "
        "v0.1 will wrap Adobe `c2patool` to read C2PA manifests. Track "
        "progress at https://github.com/nakata-app/freshmint (when public)."
    )
