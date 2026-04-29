"""Real-binary integration tests.

These exercise freshmint against a live c2patool installation. They
auto-skip when:
  - `c2patool` is not on the host (PATH / Homebrew / fallback paths).
  - `openssl` is not on the host (needed to mint the test CA chain).

To run locally: `brew install c2patool`, then `pytest -q
tests/test_integration.py`.
"""
from __future__ import annotations

import shutil
import struct
import subprocess
import textwrap
import zlib
from pathlib import Path

import pytest

from freshmint import AIAttestation, Manifest, sign, verify
from freshmint.binary import C2PAToolNotFound, find_c2patool


def _have_c2patool() -> bool:
    try:
        find_c2patool()
        return True
    except C2PAToolNotFound:
        return False


pytestmark = [
    pytest.mark.skipif(not _have_c2patool(), reason="c2patool not installed"),
    pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl not installed"),
]


def _make_png(path: Path, width: int = 8, height: int = 8) -> None:
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes((200, 50, 50)) * width for _ in range(height))
    idat = zlib.compress(raw)
    path.write_bytes(sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b""))


def _mint_test_chain(work: Path) -> tuple[Path, Path]:
    """Mint a CA-issued leaf cert chain. c2patool 0.26+ rejects
    self-signed certs at sign time, so we need a real chain even for
    tests."""
    ca_key = work / "ca-key.pem"
    ca_cert = work / "ca-cert.pem"
    leaf_key = work / "leaf-key.pem"
    leaf_csr = work / "leaf.csr"
    leaf_cert = work / "leaf-cert.pem"
    chain = work / "chain.pem"

    def run(*args: str, **kw: str) -> None:
        subprocess.run(args, check=True, capture_output=True, text=True, **kw)

    run("openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", str(ca_key))
    run(
        "openssl", "req", "-new", "-x509", "-key", str(ca_key),
        "-out", str(ca_cert), "-days", "30",
        "-subj", "/CN=freshmint-test-CA/O=freshmint-tests",
    )
    run("openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", str(leaf_key))
    run(
        "openssl", "req", "-new", "-key", str(leaf_key),
        "-out", str(leaf_csr),
        "-subj", "/CN=freshmint-leaf/O=freshmint-tests",
    )
    extfile = work / "ext.cnf"
    extfile.write_text(textwrap.dedent("""
        keyUsage=digitalSignature
        extendedKeyUsage=emailProtection
    """).strip())
    run(
        "openssl", "x509", "-req", "-in", str(leaf_csr),
        "-CA", str(ca_cert), "-CAkey", str(ca_key), "-CAcreateserial",
        "-out", str(leaf_cert), "-days", "30",
        "-extfile", str(extfile),
    )
    chain.write_bytes(leaf_cert.read_bytes() + ca_cert.read_bytes())
    return leaf_key, chain


def test_real_sign_verify_roundtrip_minimal(tmp_path: Path) -> None:
    """End-to-end sign + verify against the real c2patool binary."""
    src = tmp_path / "source.png"
    _make_png(src)
    key, chain = _mint_test_chain(tmp_path)

    manifest = Manifest(
        creator="atakan@freshmint-tests.local",
        title="freshmint integration test",
    )
    signed = sign(src, manifest, signing_key=key, cert=chain)
    assert signed.exists()
    assert signed.stat().st_size > src.stat().st_size  # manifest embedded

    result = verify(signed)
    assert result.is_valid is True, f"verify failed: {result.error!r}"
    assert result.tampered is False
    assert result.cert_chain_valid is True
    assert result.title == "freshmint integration test"
    assert result.creator == "atakan@freshmint-tests.local"


def test_real_sign_verify_with_ai_attestation(tmp_path: Path) -> None:
    """AI attestation round-trips through sign + verify."""
    src = tmp_path / "render.png"
    _make_png(src)
    key, chain = _mint_test_chain(tmp_path)

    manifest = Manifest(
        creator="sienna@nakata-app.local",
        title="render of SKU-1002",
        ai_used=True,
        ai_attestation=AIAttestation(
            model="flux-pro-1.1",
            prompt_hash="sha256:integration-test",
            seed=4839,
            source_image="SKU-1002.jpg",
        ),
    )
    signed = sign(src, manifest, signing_key=key, cert=chain)
    result = verify(signed)

    assert result.is_valid is True, f"verify failed: {result.error!r}"
    assert result.ai_used is True
    assert result.ai_attestation is not None
    assert result.ai_attestation.model == "flux-pro-1.1"
    assert result.ai_attestation.seed == 4839
    assert result.ai_attestation.source_image == "SKU-1002.jpg"
    # The synthesised c2pa.created action should declare AI provenance.
    assert any(
        a.action == "c2pa.created"
        and (a.device or "").lower().endswith("trainedalgorithmicmedia")
        for a in result.actions
    )


def test_real_verify_detects_tamper(tmp_path: Path) -> None:
    """Mutating bytes after signing should flip is_valid to False."""
    src = tmp_path / "src.png"
    _make_png(src)
    key, chain = _mint_test_chain(tmp_path)

    signed = sign(
        src,
        Manifest(creator="x@y.z", title="tamper test"),
        signing_key=key,
        cert=chain,
    )

    # Corrupt the IDAT chunk content. We avoid touching the embedded
    # manifest itself so the failure shows up as a hash / data
    # mismatch rather than a parse error.
    raw = bytearray(signed.read_bytes())
    # Find the last few bytes of pixel data (well past the manifest
    # JUMBF box near the start of a PNG c2patool produces).
    idx = max(len(raw) - 30, 0)
    raw[idx] ^= 0xFF
    signed.write_bytes(bytes(raw))

    result = verify(signed)
    assert result.is_valid is False
    assert result.error is not None
