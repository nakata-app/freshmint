"""Smoke tests for v0.0 — confirm types + API surface are wired up."""
from __future__ import annotations

import pytest


def test_imports_and_version():
    import freshmint

    assert freshmint.__version__ == "0.0.1"
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
    assert m.actions[0].action == "c2pa.created"


def test_sign_raises_not_implemented_until_v0_1():
    from freshmint import Manifest, sign

    m = Manifest(creator="x")
    with pytest.raises(NotImplementedError, match="v0.0"):
        sign("/tmp/whatever.jpg", m, signing_key="/tmp/key.pem")


def test_verify_raises_not_implemented_until_v0_1():
    from freshmint import verify

    with pytest.raises(NotImplementedError, match="v0.0"):
        verify("/tmp/whatever.jpg")


def test_verify_result_default_state():
    from freshmint import VerifyResult

    v = VerifyResult(is_valid=False, tampered=False, cert_chain_valid=False)
    assert v.creator is None
    assert v.actions == []
    assert v.error is None


def test_ai_attestation_extra_field_round_trips():
    from freshmint import AIAttestation

    a = AIAttestation(
        model="flux-pro",
        extra={"lora": "fashion-v3", "controlnet": "openpose"},
    )
    assert a.extra["lora"] == "fashion-v3"
