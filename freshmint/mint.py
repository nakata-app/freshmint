"""sign / verify entry points for c2patool 0.26+.

c2patool is the official Rust CLI from the Content Authenticity
Initiative. We translate our pythonic `Manifest` into the JSON shape
c2patool 0.26+ expects (with `private_key` / `sign_cert` embedded in
the manifest, not on the command line), shell out, and translate the
verify output back into `VerifyResult`.

v1.0 may swap subprocess for a pure-Python COSE/CBOR implementation
to drop the Adobe binary dependency. Either way the public signatures
below stay stable.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from freshmint.binary import find_c2patool
from freshmint.manifest import manifest_to_c2pa_json, parse_verify_output
from freshmint.types import Manifest, VerifyResult


def sign(
    input_path: str | Path,
    manifest: Manifest,
    signing_key: str | Path,
    output_path: str | Path | None = None,
    *,
    cert: str | Path | None = None,
    alg: str = "es256",
    **_: Any,
) -> Path:
    """Embed a C2PA manifest into ``input_path`` and write the signed file.

    Args:
        input_path: image / video / audio to sign.
        manifest: declarations to embed.
        signing_key: path to a PEM private key (embedded in the manifest
            JSON c2patool 0.26+ requires this on the manifest, not on
            the CLI).
        output_path: where to write the signed file. Defaults to
            ``<input>.signed<ext>`` next to the source.
        cert: PEM cert (or chain) path. Required for production-grade
            signing because c2patool 0.26+ rejects self-signed certs at
            the embed step (`validation_state=Invalid` otherwise). Pass
            a CA-issued leaf for `validation_state=Valid`.
        alg: signature algorithm matching the key. Default `es256`.

    Returns:
        Path to the signed file.

    Raises:
        FileNotFoundError: input or signing_key missing.
        C2PAToolNotFound: Adobe binary not on the system.
        RuntimeError: c2patool exited non-zero.
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(input_path)
    signing_key = Path(signing_key)
    if not signing_key.exists():
        raise FileNotFoundError(signing_key)
    if cert is not None:
        cert = Path(cert)
        if not cert.exists():
            raise FileNotFoundError(cert)
    if output_path is None:
        output_path = input_path.with_suffix(f".signed{input_path.suffix}")
    output_path = Path(output_path)

    binary = find_c2patool()
    payload = manifest_to_c2pa_json(
        manifest,
        signing_key=signing_key,
        cert=cert,
        alg=alg,
    )

    with tempfile.TemporaryDirectory() as td:
        manifest_file = Path(td) / "manifest.json"
        manifest_file.write_text(json.dumps(payload, indent=2))

        cmd = [
            str(binary),
            str(input_path),
            "--manifest",
            str(manifest_file),
            "--output",
            str(output_path),
            "--force",
        ]

        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"c2patool sign failed (exit {completed.returncode}): "
                f"{completed.stderr.strip() or completed.stdout.strip()}"
            )

    return output_path


def verify(input_path: str | Path, **_: Any) -> VerifyResult:
    """Read and validate the C2PA manifest in ``input_path``.

    Returns:
        ``VerifyResult`` populated with signer identity, edit history,
        AI attestation (if present), and validation flags. Always
        returns, never raises on validation failure; check
        ``result.is_valid`` and ``result.error`` instead.

    Raises:
        FileNotFoundError: input doesn't exist.
        C2PAToolNotFound: Adobe binary not on the system.
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(input_path)

    binary = find_c2patool()

    completed = subprocess.run(
        [str(binary), str(input_path), "--detailed"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0 and not completed.stdout.strip():
        return VerifyResult(
            is_valid=False,
            tampered=False,
            cert_chain_valid=False,
            error=(
                f"c2patool verify failed (exit {completed.returncode}): "
                f"{completed.stderr.strip()}"
            ),
        )

    try:
        c2pa_json = json.loads(completed.stdout)
    except json.JSONDecodeError as e:
        return VerifyResult(
            is_valid=False,
            tampered=False,
            cert_chain_valid=False,
            error=f"c2patool returned non-JSON output: {e}",
        )

    return parse_verify_output(c2pa_json)
