"""Public data types for freshmint — stable contract surface.

These types stay stable across v0.x releases so callers can write
integration code today against an API the v0.1 implementation will
fulfil.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Action:
    """One step in the content's edit / capture history.

    C2PA defines a vocabulary (`c2pa.created`, `c2pa.edited`,
    `c2pa.placed`, `c2pa.cropped`, `c2pa.color_adjustments`, etc).
    Use the standard names when possible — verifiers display them
    with localised labels.
    """

    action: str
    timestamp: str | None = None
    tool: str | None = None
    device: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class AIAttestation:
    """When AI was involved, this carries the disclosure detail.

    The whole point of freshmint vs. detection-based approaches is that
    creators are *honest* about AI use. Lying here breaks the cert
    chain (or at least the trust chain — verifiers can flag mismatched
    pixel statistics vs. a "no AI" claim).
    """

    model: str
    """Model identifier (e.g. 'flux-pro-1.1', 'gpt-image-2', 'sd-xl')."""

    prompt_hash: str | None = None
    """SHA256 of the prompt — proves which prompt produced this without
    leaking the prompt itself. Useful for IP / brand-safety audits."""

    seed: int | None = None
    """Generation seed when deterministic — allows exact re-render."""

    source_image: str | None = None
    """Reference image / packshot the render was derived from."""

    extra: dict[str, Any] = field(default_factory=dict)
    """Anything else the creator wants to attest (LoRA, controlnet, etc)."""


@dataclass
class Manifest:
    """The C2PA manifest a creator embeds when signing.

    Args:
        creator: identity (email / handle / pubkey fingerprint).
        title: short human label for the asset.
        actions: edit / capture history.
        ai_used: was AI involved at any step? Be honest.
        ai_attestation: disclosure detail when ai_used=True.
        extra_assertions: caller-defined claims (cluster fields like
            `imageguard_score` or `claimcheck_verdict` go here).
    """

    creator: str
    title: str | None = None
    actions: list[Action] = field(default_factory=list)
    ai_used: bool = False
    ai_attestation: AIAttestation | None = None
    extra_assertions: dict[str, Any] = field(default_factory=dict)


@dataclass
class VerifyResult:
    """Output of `verify(path)` — what a downstream consumer sees.

    All fields are populated even when validation fails so the caller
    can show meaningful errors / partial-trust UIs.
    """

    is_valid: bool
    """Overall: signature checks out AND nothing has been tampered AND
    cert chain reaches a trusted root. False ⇒ inspect sub-fields."""

    tampered: bool
    """True iff the file bytes changed after signing."""

    cert_chain_valid: bool
    """True iff the signing cert chains to a trusted root CA."""

    creator: str | None = None
    title: str | None = None
    ai_used: bool | None = None
    ai_attestation: AIAttestation | None = None
    actions: list[Action] = field(default_factory=list)
    extra_assertions: dict[str, Any] = field(default_factory=dict)
    raw_manifest: dict[str, Any] | None = None
    """Full c2patool JSON output for callers that want to inspect
    everything (cert serial, timestamps, soft-bindings, etc)."""

    error: str | None = None
    """Populated when is_valid=False with a human-readable reason."""
