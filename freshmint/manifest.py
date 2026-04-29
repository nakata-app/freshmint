"""Manifest <-> c2patool JSON serialization for c2patool 0.26+.

c2patool consumes a manifest JSON with `private_key` and `sign_cert`
fields embedded directly (legacy `--key` / `--cert` CLI flags were
removed in 0.26). The shape we emit:

```jsonc
{
  "claim_generator": "freshmint/0.1.1",
  "title": "...",
  "alg": "es256",
  "private_key": "key.pem",
  "sign_cert": "chain.pem",
  "assertions": [
    {"label": "c2pa.actions", "data": {"actions": [...]}},
    {"label": "stds.schema-org.CreativeWork", "data": {...}},
    // optional: AI attestation, freshmint.extra
  ]
}
```

C2PA requires at least one action assertion; we synthesise a
`c2pa.created` action when the caller passes none, so default-shape
manifests still produce `validation_state=Valid` against a real binary.

The verify side parses the modern c2patool output schema:
```jsonc
{
  "active_manifest": "urn:c2pa:...",
  "manifests": {
    "urn:c2pa:...": {
      "claim": {"dc:title": "...", "alg": "..."},
      "assertion_store": {"<label>": {...}},
      "signature": {"issuer": "...", "common_name": "...", "alg": "..."}
    }
  },
  "validation_state": "Valid" | "Invalid",
  "validation_results": {"activeManifest": {"success": [...], "failure": [...]}}
}
```
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from freshmint.types import Action, AIAttestation, Manifest, VerifyResult

_CLAIM_GENERATOR = "freshmint/0.1.1"

# Custom assertion label for the AI attestation fields freshmint cares
# about beyond what c2pa.actions captures. Keeping it under our own
# namespace avoids collision with stds.* labels that the Adobe spec
# may evolve.
_AI_ATTESTATION_LABEL = "org.nakata.freshmint.ai_attestation"

# Custom label for caller-provided extras (cluster fields).
_EXTRA_ASSERTIONS_LABEL = "org.nakata.freshmint.extra"


def manifest_to_c2pa_json(
    manifest: Manifest,
    *,
    signing_key: str | Path,
    cert: str | Path | None = None,
    alg: str = "es256",
) -> dict[str, Any]:
    """Serialize a `Manifest` into the c2patool 0.26+ input JSON shape.

    Args:
        manifest: pythonic manifest to serialize.
        signing_key: PEM key path, embedded as `private_key`.
        cert: PEM cert (or chain) path, embedded as `sign_cert`. c2patool
            rejects self-signed certs, callers must supply a CA-issued
            leaf for `validation_state=Valid`.
        alg: signature algorithm matching the key. Default `es256`
            (NIST P-256). Override with e.g. `ed25519`, `ps256`.
    """
    payload: dict[str, Any] = {
        "claim_generator": _CLAIM_GENERATOR,
        "title": manifest.title or "Untitled",
        "alg": alg,
        "private_key": str(signing_key),
        "assertions": _build_assertions(manifest),
    }
    if cert is not None:
        payload["sign_cert"] = str(cert)
    return payload


def _build_assertions(manifest: Manifest) -> list[dict[str, Any]]:
    assertions: list[dict[str, Any]] = []

    actions = list(manifest.actions)
    needs_synth = (
        not actions or actions[0].action not in {"c2pa.created", "c2pa.opened"}
    )
    if needs_synth:
        # C2PA validation requires the first action be `c2pa.created`
        # or `c2pa.opened`. Synthesise one so callers don't have to. We
        # leave `tool` unset on purpose: when ai_used=True,
        # `_action_to_dict` fills softwareAgent with the AI model so
        # verifiers see the model identity instead of a freshmint banner.
        synth = Action(
            action="c2pa.created",
            tool=None if manifest.ai_used else _CLAIM_GENERATOR,
        )
        if not actions:
            actions.append(synth)
        else:
            actions.insert(0, synth)

    assertions.append(
        {
            "label": "c2pa.actions",
            "data": {"actions": [_action_to_dict(a, manifest) for a in actions]},
        }
    )

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

    if manifest.ai_used and manifest.ai_attestation is not None:
        assertions.append(
            {
                "label": _AI_ATTESTATION_LABEL,
                "data": _ai_attestation_to_dict(manifest.ai_attestation),
            }
        )

    if manifest.extra_assertions:
        assertions.append(
            {
                "label": _EXTRA_ASSERTIONS_LABEL,
                "data": dict(manifest.extra_assertions),
            }
        )

    return assertions


def _action_to_dict(action: Action, manifest: Manifest) -> dict[str, Any]:
    out: dict[str, Any] = {"action": action.action}
    if action.timestamp:
        out["when"] = action.timestamp
    if action.tool:
        out["softwareAgent"] = {"name": action.tool}
    elif action.action == "c2pa.created" and manifest.ai_used and manifest.ai_attestation:
        # Surface the AI model in the action's softwareAgent so verifiers
        # that only read c2pa.actions still see "AI was used".
        out["softwareAgent"] = {"name": manifest.ai_attestation.model}
    if action.device:
        out["digitalSourceType"] = action.device
    if action.action == "c2pa.created" and manifest.ai_used and "digitalSourceType" not in out:
        # https://cv.iptc.org/newscodes/digitalsourcetype/
        out["digitalSourceType"] = (
            "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"
        )
    if action.parameters:
        out["parameters"] = dict(action.parameters)
    return out


def _ai_attestation_to_dict(att: AIAttestation) -> dict[str, Any]:
    out: dict[str, Any] = {"model": att.model}
    if att.prompt_hash:
        out["prompt_hash"] = att.prompt_hash
    if att.seed is not None:
        out["seed"] = att.seed
    if att.source_image:
        out["source_image"] = att.source_image
    if att.extra:
        out["extra"] = dict(att.extra)
    return out


# ---- Parse c2patool 0.26+ verify output -> VerifyResult ------------------


def parse_verify_output(c2pa_output: dict[str, Any]) -> VerifyResult:
    """Translate c2patool verify JSON (0.26+ schema) into a VerifyResult.

    The legacy `validation_status` array is gone; the modern shape uses
    `validation_state` ("Valid" | "Invalid") plus
    `validation_results.activeManifest.{success, failure}`.
    """
    validation_state = c2pa_output.get("validation_state")
    results = c2pa_output.get("validation_results") or {}
    active_results = results.get("activeManifest") or {}
    failures: list[dict[str, Any]] = list(active_results.get("failure") or [])

    is_valid = validation_state == "Valid"
    tampered = any(
        _failure_code(f).startswith("assertion.dataHash") for f in failures
    )
    cert_chain_valid = is_valid or not any(
        _failure_code(f).startswith("signingCredential.") for f in failures
    )

    manifests = c2pa_output.get("manifests", {}) or {}
    active = c2pa_output.get("active_manifest") or next(iter(manifests), None)

    title: str | None = None
    creator: str | None = None
    ai_used: bool | None = None
    ai_attestation: AIAttestation | None = None
    actions: list[Action] = []
    extra: dict[str, Any] = {}

    if active and active in manifests:
        m = manifests[active]
        title = _extract_title(m)
        store = m.get("assertion_store") or {}

        cw = store.get("stds.schema-org.CreativeWork")
        if isinstance(cw, dict):
            authors = cw.get("author") or []
            if authors and isinstance(authors[0], dict):
                creator = authors[0].get("name")

        c2pa_actions = store.get("c2pa.actions") or store.get("c2pa.actions.v2")
        if isinstance(c2pa_actions, dict):
            for a in c2pa_actions.get("actions", []) or []:
                if not isinstance(a, dict):
                    continue
                actions.append(_dict_to_action(a))
                dst = (a.get("digitalSourceType") or "").lower()
                if "algorithmicmedia" in dst or "trainedalgorithmic" in dst:
                    ai_used = True

        ai_data = store.get(_AI_ATTESTATION_LABEL)
        if isinstance(ai_data, dict):
            ai_used = True
            ai_attestation = AIAttestation(
                model=str(ai_data.get("model", "unknown")),
                prompt_hash=ai_data.get("prompt_hash"),
                seed=ai_data.get("seed"),
                source_image=ai_data.get("source_image"),
                extra=dict(ai_data.get("extra") or {}),
            )

        extras_data = store.get(_EXTRA_ASSERTIONS_LABEL)
        if isinstance(extras_data, dict):
            extra.update(extras_data)

    return VerifyResult(
        is_valid=is_valid,
        tampered=tampered,
        cert_chain_valid=cert_chain_valid,
        creator=creator,
        title=title,
        ai_used=ai_used,
        ai_attestation=ai_attestation,
        actions=actions,
        extra_assertions=extra,
        raw_manifest=c2pa_output,
        error=_summarise_failures(failures) if not is_valid else None,
    )


def _failure_code(f: dict[str, Any]) -> str:
    return str(f.get("code") or "")


def _summarise_failures(failures: list[dict[str, Any]]) -> str | None:
    if not failures:
        return None
    return "; ".join(
        str(f.get("explanation") or f.get("code") or "unknown") for f in failures
    )


def _extract_title(manifest: dict[str, Any]) -> str | None:
    claim = manifest.get("claim") or {}
    # c2patool 0.26+ stores the title under `dc:title` inside `claim`.
    title = claim.get("dc:title") or manifest.get("title")
    return str(title) if title is not None else None


def _dict_to_action(a: dict[str, Any]) -> Action:
    sw = a.get("softwareAgent")
    tool: str | None
    if isinstance(sw, dict):
        tool = sw.get("name")
    elif isinstance(sw, str):
        tool = sw
    else:
        tool = None
    return Action(
        action=str(a.get("action", "unknown")),
        timestamp=a.get("when"),
        tool=tool,
        device=a.get("digitalSourceType"),
        parameters=dict(a.get("parameters") or {}),
    )


__all__ = [
    "manifest_to_c2pa_json",
    "parse_verify_output",
]
