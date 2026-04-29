"""freshmint — pythonic C2PA, sign every AI render with verifiable provenance."""
from freshmint.mint import sign, verify
from freshmint.types import Action, AIAttestation, Manifest, VerifyResult

__all__ = ["AIAttestation", "Action", "Manifest", "VerifyResult", "sign", "verify"]
__version__ = "0.1.0"
