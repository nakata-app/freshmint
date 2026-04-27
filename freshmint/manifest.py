"""Manifest ↔ c2patool JSON serialization.

c2patool consumes a JSON manifest with a specific shape (claim_generator,
title, assertions[]). We translate our pythonic `Manifest` dataclass
into that shape — and parse the c2patool verify output back into a
`VerifyResult`.

The Adobe JSON spec is documented at
https://opensource.contentauthenticity.org/docs/c2patool/  — we cover
the subset that matters for freshmint's v0.1 use cases (creator,
edit history, AI attestation, free-form extras).
"""
from __future__ import annotations

from typing import Any

from freshmint.types import AIAttestation, Manifest, VerifyResult


_CLAIM_GENERATOR = "freshmint/0.1.0"


def manifest_to_c2pa_json(manifest: Manifest) -> dict[str, Any]:
    """Serialize a `Manifest` into the c2patool input JSON shape."""
    assertions: list[dict[str, Any]] = []

    # Author / creator assertion.
    assertions.append(
        {
            "label": "stds.schema-org.CreativeWork",
            "data": {
                "@context": "https://schema.org",
                "@type": "CreativeWork",
                "author": [{"@type": "Person", "name": manifest.creator}],
            },
        }
    )

    # Edit / capture actions.
    if manifest.actions:
        assertions.append(
            {
                "label": "c2pa.actions",
                "data": {
                    "actions": [
                        _action_to_dict(a) for a in manifest.actions
                    ],
                },
            }
        )

    # AI attestation — Adobe's training-and-data-mining assertion family.
    if manifest.ai_used and manifest.ai_attestation is not None:
        assertions.append(
            {
                "label": "stds.training-mining.usage",
                "data": _ai_attestation_to_dict(manifest.ai_attestation),
            }
        )

    # Caller-defined extras (cluster fields go here).
    if manifest.extra_assertions:
        assertions.append(
            {
                "label": "freshmint.extra",
                "data": dict(manifest.extra_assertions),
            }
        )

    payload: dict[str, Any] = {
        "claim_generator": _CLAIM_GENERATOR,
        "title": manifest.title or "Untitled",
        "assertions": assertions,
    }
    return payload


def _action_to_dict(action: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"action": action.action}
    if action.timestamp:
        out["when"] = action.timestamp
    if action.tool:
        out["softwareAgent"] = action.tool
    if action.device:
        out["digitalSourceType"] = action.device
    if action.parameters:
        out["parameters"] = dict(action.parameters)
    return out


def _ai_attestation_to_dict(att: AIAttestation) -> dict[str, Any]:
    out: dict[str, Any] = {
        "use": "trained",
        "model": att.model,
    }
    if att.prompt_hash:
        out["prompt_hash"] = att.prompt_hash
    if att.seed is not None:
        out["seed"] = att.seed
    if att.source_image:
        out["source_image"] = att.source_image
    if att.extra:
        out["extra"] = dict(att.extra)
    return out


# ---- Parse c2patool output → VerifyResult --------------------------------


def parse_verify_output(c2pa_output: dict[str, Any]) -> VerifyResult:
    """Translate c2patool verify JSON into freshmint's VerifyResult."""
    manifests = c2pa_output.get("manifests", {}) or {}
    active = c2pa_output.get("active_manifest") or next(iter(manifests), None)

    is_valid = bool(c2pa_output.get("validation_status", "")) is False or (
        # Adobe uses "validation_status" array — empty-or-missing means OK.
        len(c2pa_output.get("validation_status", []) or []) == 0
    )
    tampered = any(
        v.get("code") == "assertion.dataHash.mismatch"
        for v in (c2pa_output.get("validation_status") or [])
    )
    cert_chain_valid = not any(
        v.get("code", "").startswith("signingCredential.")
        for v in (c2pa_output.get("validation_status") or [])
    )

    creator: str | None = None
    title: str | None = None
    ai_used: bool | None = None
    ai_attestation: AIAttestation | None = None
    actions: list[Any] = []
    extra: dict[str, Any] = {}

    if active and active in manifests:
        m = manifests[active]
        title = m.get("title")
        for a in m.get("assertions", []):
            label = a.get("label", "")
            data = a.get("data", {})
            if label == "stds.schema-org.CreativeWork":
                authors = data.get("author") or []
                if authors and isinstance(authors[0], dict):
                    creator = authors[0].get("name")
            elif label == "c2pa.actions":
                ai_used = ai_used or False  # baseline if action assertion present
            elif label == "stds.training-mining.usage":
                ai_used = True
                ai_attestation = AIAttestation(
                    model=str(data.get("model", "unknown")),
                    prompt_hash=data.get("prompt_hash"),
                    seed=data.get("seed"),
                    source_image=data.get("source_image"),
                    extra=data.get("extra", {}) or {},
                )
            elif label == "freshmint.extra":
                extra.update(data)

    return VerifyResult(
        is_valid=is_valid and cert_chain_valid and not tampered,
        tampered=tampered,
        cert_chain_valid=cert_chain_valid,
        creator=creator,
        title=title,
        ai_used=ai_used,
        ai_attestation=ai_attestation,
        actions=actions,
        extra_assertions=extra,
        raw_manifest=c2pa_output,
        error=None if (is_valid and not tampered) else _summarise_errors(
            c2pa_output.get("validation_status") or []
        ),
    )


def _summarise_errors(statuses: list[dict[str, Any]]) -> str | None:
    if not statuses:
        return None
    return "; ".join(s.get("explanation", s.get("code", "unknown")) for s in statuses)


__all__ = [
    "manifest_to_c2pa_json",
    "parse_verify_output",
]
