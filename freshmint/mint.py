"""sign / verify entry points — v0.1 wraps Adobe c2patool via subprocess.

c2patool is the official Rust CLI from the Content Authenticity
Initiative. It reads a JSON manifest, applies it to a media file,
and signs the result with the supplied PEM key. We translate our
pythonic `Manifest` dataclass into the JSON shape c2patool expects,
shell out, and translate the verify output back into `VerifyResult`.

v1.0 may swap subprocess for a pure-Python COSE/CBOR implementation
to drop the Adobe binary dependency. Either way the signatures
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
    **_: Any,
) -> Path:
    """Embed a C2PA manifest into ``input_path`` and write the signed file.

    Args:
        input_path: image / video / audio to sign.
        manifest: declarations to embed.
        signing_key: path to a PEM private key.
        output_path: where to write the signed file. Defaults to
            ``<input>.signed.<ext>`` next to the source.
        cert: optional X.509 cert chain (PEM). When omitted, c2patool
            uses a self-signed cert — prototype-OK, no external trust.

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
    if output_path is None:
        output_path = input_path.with_suffix(f".signed{input_path.suffix}")
    output_path = Path(output_path)

    binary = find_c2patool()
    payload = manifest_to_c2pa_json(manifest)

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
            "--key",
            str(signing_key),
        ]
        if cert is not None:
            cmd += ["--cert", str(cert)]

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
        returns — never raises on validation failure; check
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
        # No JSON to parse — return a diagnostic VerifyResult.
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
