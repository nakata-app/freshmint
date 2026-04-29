"""v0.1 unit tests, types + serialization + subprocess wiring.

Real c2patool isn't required: we monkey-patch `subprocess.run` and
`find_c2patool` so tests run in CI without the Adobe binary.

Real binary smoke is in `tests/test_integration.py`, which auto-skips
when c2patool is not on the host.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

# ---- Type-level / contract tests ----------------------------------------


def test_imports_and_version():
    import freshmint

    assert freshmint.__version__ == "0.1.1"
    assert freshmint.Manifest is not None
    assert freshmint.Action is not None
    assert freshmint.AIAttestation is not None
    assert freshmint.VerifyResult is not None
    assert freshmint.sign is not None
    assert freshmint.verify is not None


def test_manifest_round_trip():
    from freshmint import Action, AIAttestation, Manifest

    m = Manifest(
        creator="atakan@studio.com",
        title="render of SKU-1002",
        actions=[Action(action="c2pa.created", tool="freshmint")],
        ai_used=True,
        ai_attestation=AIAttestation(
            model="flux-pro-1.1",
            prompt_hash="sha256:abc",
            seed=4839,
            source_image="SKU-1002.jpg",
        ),
    )
    assert m.creator == "atakan@studio.com"
    assert m.ai_used is True
    assert m.ai_attestation is not None
    assert m.ai_attestation.model == "flux-pro-1.1"


def test_verify_result_default_state():
    from freshmint import VerifyResult

    v = VerifyResult(is_valid=False, tampered=False, cert_chain_valid=False)
    assert v.creator is None
    assert v.actions == []
    assert v.error is None


def test_ai_attestation_extra_field_round_trips():
    from freshmint import AIAttestation

    a = AIAttestation(model="flux-pro", extra={"lora": "fashion-v3"})
    assert a.extra["lora"] == "fashion-v3"


# ---- Manifest serialization (c2patool 0.26+ shape) ----------------------


def test_manifest_to_c2pa_json_embeds_key_and_cert():
    from freshmint import Manifest
    from freshmint.manifest import manifest_to_c2pa_json

    m = Manifest(creator="atakan@studio.com", title="test")
    payload = manifest_to_c2pa_json(m, signing_key="key.pem", cert="chain.pem")
    assert payload["title"] == "test"
    assert payload["claim_generator"].startswith("freshmint/")
    assert payload["alg"] == "es256"
    assert payload["private_key"] == "key.pem"
    assert payload["sign_cert"] == "chain.pem"


def test_manifest_to_c2pa_json_includes_creator():
    from freshmint import Action, Manifest
    from freshmint.manifest import manifest_to_c2pa_json

    m = Manifest(
        creator="atakan@studio.com",
        title="test",
        actions=[Action(action="c2pa.created", tool="freshmint")],
    )
    payload = manifest_to_c2pa_json(m, signing_key="k.pem", cert="c.pem")
    creators = [
        a for a in payload["assertions"]
        if a["label"] == "stds.schema-org.CreativeWork"
    ]
    assert len(creators) == 1
    assert creators[0]["data"]["author"][0]["name"] == "atakan@studio.com"


def test_manifest_to_c2pa_json_synthesises_created_action():
    """C2PA validation requires the first action be c2pa.created or
    c2pa.opened. We auto-add one when the caller supplies none."""
    from freshmint import Manifest
    from freshmint.manifest import manifest_to_c2pa_json

    m = Manifest(creator="x", actions=[])
    payload = manifest_to_c2pa_json(m, signing_key="k.pem", cert="c.pem")
    actions_a = next(a for a in payload["assertions"] if a["label"] == "c2pa.actions")
    actions = actions_a["data"]["actions"]
    assert len(actions) == 1
    assert actions[0]["action"] == "c2pa.created"


def test_manifest_to_c2pa_json_emits_ai_attestation_when_used():
    from freshmint import AIAttestation, Manifest
    from freshmint.manifest import manifest_to_c2pa_json

    m = Manifest(
        creator="x",
        ai_used=True,
        ai_attestation=AIAttestation(
            model="flux-pro-1.1",
            prompt_hash="sha256:abc",
            seed=4839,
        ),
    )
    payload = manifest_to_c2pa_json(m, signing_key="k.pem", cert="c.pem")
    ai = [
        a for a in payload["assertions"]
        if a["label"] == "org.nakata.freshmint.ai_attestation"
    ]
    assert len(ai) == 1
    assert ai[0]["data"]["model"] == "flux-pro-1.1"
    assert ai[0]["data"]["seed"] == 4839


def test_manifest_to_c2pa_json_marks_action_as_ai_when_used():
    """When ai_used=True, the synthesised c2pa.created action carries a
    digitalSourceType of trainedAlgorithmicMedia so verifiers reading
    only c2pa.actions still see that AI was used."""
    from freshmint import AIAttestation, Manifest
    from freshmint.manifest import manifest_to_c2pa_json

    m = Manifest(
        creator="x",
        ai_used=True,
        ai_attestation=AIAttestation(model="flux-pro-1.1"),
    )
    payload = manifest_to_c2pa_json(m, signing_key="k.pem", cert="c.pem")
    actions_a = next(a for a in payload["assertions"] if a["label"] == "c2pa.actions")
    created = actions_a["data"]["actions"][0]
    assert created["action"] == "c2pa.created"
    assert "trainedAlgorithmicMedia" in created["digitalSourceType"]
    assert created["softwareAgent"]["name"] == "flux-pro-1.1"


def test_manifest_to_c2pa_json_skips_ai_assertion_when_not_used():
    from freshmint import Manifest
    from freshmint.manifest import manifest_to_c2pa_json

    m = Manifest(creator="x", ai_used=False)
    payload = manifest_to_c2pa_json(m, signing_key="k.pem", cert="c.pem")
    assert not any(
        a["label"] == "org.nakata.freshmint.ai_attestation"
        for a in payload["assertions"]
    )


def test_extra_assertions_round_trip():
    from freshmint import Manifest
    from freshmint.manifest import manifest_to_c2pa_json

    m = Manifest(
        creator="x",
        extra_assertions={"claimcheck_verdict": 0.92, "imageguard_score": 0.84},
    )
    payload = manifest_to_c2pa_json(m, signing_key="k.pem", cert="c.pem")
    extras = [
        a for a in payload["assertions"] if a["label"] == "org.nakata.freshmint.extra"
    ]
    assert len(extras) == 1
    assert extras[0]["data"]["claimcheck_verdict"] == 0.92


# ---- Verify output parsing (c2patool 0.26+ schema) ----------------------


def test_parse_verify_output_extracts_creator_and_ai():
    from freshmint.manifest import parse_verify_output

    fake = {
        "active_manifest": "urn:uuid:abc",
        "validation_state": "Valid",
        "validation_results": {"activeManifest": {"success": [], "failure": []}},
        "manifests": {
            "urn:uuid:abc": {
                "claim": {"dc:title": "test render", "alg": "sha256"},
                "assertion_store": {
                    "stds.schema-org.CreativeWork": {
                        "@context": "https://schema.org",
                        "@type": "CreativeWork",
                        "author": [{"@type": "Person", "name": "atakan@x.com"}],
                    },
                    "c2pa.actions": {
                        "actions": [
                            {
                                "action": "c2pa.created",
                                "softwareAgent": {"name": "flux-pro-1.1"},
                                "digitalSourceType": (
                                    "http://cv.iptc.org/newscodes/digitalsourcetype"
                                    "/trainedAlgorithmicMedia"
                                ),
                            }
                        ]
                    },
                    "org.nakata.freshmint.ai_attestation": {
                        "model": "flux-pro-1.1",
                        "seed": 4839,
                    },
                },
                "signature": {
                    "issuer": "nakata-app",
                    "common_name": "sienna-signer",
                    "alg": "es256",
                },
            }
        },
    }
    result = parse_verify_output(fake)
    assert result.is_valid is True
    assert result.tampered is False
    assert result.cert_chain_valid is True
    assert result.creator == "atakan@x.com"
    assert result.title == "test render"
    assert result.ai_used is True
    assert result.ai_attestation is not None
    assert result.ai_attestation.model == "flux-pro-1.1"
    assert result.ai_attestation.seed == 4839
    assert len(result.actions) == 1
    assert result.actions[0].action == "c2pa.created"


def test_parse_verify_output_flags_tamper():
    from freshmint.manifest import parse_verify_output

    fake = {
        "active_manifest": "urn:uuid:abc",
        "validation_state": "Invalid",
        "validation_results": {
            "activeManifest": {
                "success": [],
                "failure": [
                    {
                        "code": "assertion.dataHash.mismatch",
                        "explanation": "bytes changed",
                    }
                ],
            }
        },
        "manifests": {
            "urn:uuid:abc": {
                "claim": {"dc:title": "tampered"},
                "assertion_store": {},
            }
        },
    }
    result = parse_verify_output(fake)
    assert result.is_valid is False
    assert result.tampered is True
    assert result.error == "bytes changed"


def test_parse_verify_output_actions_v2_label():
    """c2patool 0.26+ stores actions under c2pa.actions.v2 in some
    contexts. We accept either label."""
    from freshmint.manifest import parse_verify_output

    fake = {
        "active_manifest": "urn:uuid:1",
        "validation_state": "Valid",
        "validation_results": {"activeManifest": {"success": [], "failure": []}},
        "manifests": {
            "urn:uuid:1": {
                "claim": {"dc:title": "with v2"},
                "assertion_store": {
                    "c2pa.actions.v2": {
                        "actions": [
                            {"action": "c2pa.created", "softwareAgent": {"name": "x"}}
                        ]
                    },
                },
            }
        },
    }
    result = parse_verify_output(fake)
    assert result.is_valid is True
    assert len(result.actions) == 1
    assert result.actions[0].tool == "x"


# ---- Sign / verify subprocess wiring (monkey-patched) -------------------


def test_sign_invokes_c2patool_with_modern_args(tmp_path, monkeypatch):
    """c2patool 0.26+ wiring: --manifest + --output + --force, NO --key
    / --cert (those moved into the manifest JSON)."""
    from freshmint import Manifest, sign
    from freshmint import binary as binary_mod
    from freshmint import mint as mint_mod

    monkeypatch.setattr(binary_mod, "find_c2patool", lambda: Path("/usr/bin/c2patool"))
    monkeypatch.setattr(mint_mod, "find_c2patool", lambda: Path("/usr/bin/c2patool"))

    captured: dict[str, Any] = {}

    def fake_run(cmd, check=False, capture_output=False, text=False):
        captured["cmd"] = list(cmd)
        manifest_idx = cmd.index("--manifest") + 1
        captured["manifest"] = json.loads(Path(cmd[manifest_idx]).read_text())
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    inp = tmp_path / "in.jpg"
    inp.write_bytes(b"\x89PNG\r\n")
    key = tmp_path / "key.pem"
    key.write_text("---- PEM ----")
    cert = tmp_path / "cert.pem"
    cert.write_text("---- CERT ----")

    out = sign(inp, Manifest(creator="atakan@x.com"), signing_key=key, cert=cert)

    assert out.suffix == ".jpg"
    assert "--manifest" in captured["cmd"]
    assert "--output" in captured["cmd"]
    assert "--force" in captured["cmd"]
    assert "--key" not in captured["cmd"]
    assert "--cert" not in captured["cmd"]
    assert captured["manifest"]["private_key"] == str(key)
    assert captured["manifest"]["sign_cert"] == str(cert)


def test_sign_raises_when_input_missing(tmp_path):
    from freshmint import Manifest, sign

    with pytest.raises(FileNotFoundError):
        sign(
            tmp_path / "does-not-exist.jpg",
            Manifest(creator="x"),
            signing_key=tmp_path / "also-missing.pem",
        )


def test_sign_raises_when_cert_missing(tmp_path):
    from freshmint import Manifest, sign

    inp = tmp_path / "in.jpg"
    inp.write_bytes(b"\x89PNG\r\n")
    key = tmp_path / "key.pem"
    key.write_text("k")

    with pytest.raises(FileNotFoundError):
        sign(inp, Manifest(creator="x"), signing_key=key, cert=tmp_path / "missing.pem")


def test_verify_returns_diagnostic_on_subprocess_failure(tmp_path, monkeypatch):
    from freshmint import verify
    from freshmint import binary as binary_mod
    from freshmint import mint as mint_mod

    monkeypatch.setattr(binary_mod, "find_c2patool", lambda: Path("/usr/bin/c2patool"))
    monkeypatch.setattr(mint_mod, "find_c2patool", lambda: Path("/usr/bin/c2patool"))

    def fake_run(cmd, check=False, capture_output=False, text=False):
        return subprocess.CompletedProcess(
            args=cmd, returncode=2, stdout="", stderr="bad image"
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    inp = tmp_path / "broken.jpg"
    inp.write_bytes(b"")
    result = verify(inp)
    assert result.is_valid is False
    assert result.error is not None
    assert "bad image" in result.error


def test_verify_parses_c2patool_json(tmp_path, monkeypatch):
    from freshmint import verify
    from freshmint import binary as binary_mod
    from freshmint import mint as mint_mod

    monkeypatch.setattr(binary_mod, "find_c2patool", lambda: Path("/usr/bin/c2patool"))
    monkeypatch.setattr(mint_mod, "find_c2patool", lambda: Path("/usr/bin/c2patool"))

    fake = json.dumps(
        {
            "active_manifest": "urn:uuid:1",
            "validation_state": "Valid",
            "validation_results": {"activeManifest": {"success": [], "failure": []}},
            "manifests": {
                "urn:uuid:1": {
                    "claim": {"dc:title": "Verified"},
                    "assertion_store": {
                        "stds.schema-org.CreativeWork": {
                            "author": [{"name": "atakan@x.com"}],
                        },
                    },
                }
            },
        }
    )

    monkeypatch.setattr(
        subprocess, "run",
        lambda cmd, check=False, capture_output=False, text=False:
            subprocess.CompletedProcess(args=cmd, returncode=0, stdout=fake, stderr=""),
    )

    inp = tmp_path / "ok.jpg"
    inp.write_bytes(b"\x89PNG\r\n")
    result = verify(inp)
    assert result.is_valid is True
    assert result.creator == "atakan@x.com"
    assert result.title == "Verified"
    assert result.tampered is False


# ---- find_c2patool resolution -------------------------------------------


def test_find_c2patool_uses_explicit_env(monkeypatch, tmp_path):
    from freshmint.binary import find_c2patool

    fake = tmp_path / "c2patool"
    fake.write_text("#!/bin/sh\nexit 0\n")
    fake.chmod(0o755)

    monkeypatch.setenv("FRESHMINT_C2PATOOL", str(fake))
    assert find_c2patool() == fake


def test_find_c2patool_raises_when_missing(monkeypatch):
    from freshmint.binary import C2PAToolNotFound, find_c2patool

    monkeypatch.delenv("FRESHMINT_C2PATOOL", raising=False)
    monkeypatch.setattr("shutil.which", lambda _name: None)
    monkeypatch.setattr(
        "freshmint.binary._FALLBACK_PATHS",
        (Path("/nope/c2patool"),),
    )
    with pytest.raises(C2PAToolNotFound, match="not found"):
        find_c2patool()
