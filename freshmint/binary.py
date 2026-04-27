"""Locate the Adobe c2patool binary on the host system.

Order of resolution:
  1. FRESHMINT_C2PATOOL env var (explicit override, takes precedence)
  2. `which c2patool` on PATH
  3. Homebrew default (`/opt/homebrew/bin/c2patool` on Apple silicon,
     `/usr/local/bin/c2patool` on Intel)
  4. Linux package paths (`/usr/local/bin`, `/usr/bin`)

Caller gets a clear error message + install hint when the binary is
missing — no silent fallback to a degraded path.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path


_FALLBACK_PATHS: tuple[Path, ...] = (
    Path("/opt/homebrew/bin/c2patool"),  # Mac Apple silicon (brew)
    Path("/usr/local/bin/c2patool"),     # Mac Intel + Linux /usr/local
    Path("/usr/bin/c2patool"),           # Linux distros
)


class C2PAToolNotFound(RuntimeError):
    """Raised when no c2patool binary is found on the system."""


def find_c2patool() -> Path:
    """Return a Path to the c2patool binary, or raise C2PAToolNotFound.

    Resolution order is documented at the module level.
    """
    # 1. Explicit env override.
    explicit = os.environ.get("FRESHMINT_C2PATOOL")
    if explicit:
        p = Path(explicit)
        if p.is_file() and os.access(p, os.X_OK):
            return p
        raise C2PAToolNotFound(
            f"FRESHMINT_C2PATOOL={explicit} but the file is missing or not executable."
        )

    # 2. PATH lookup.
    on_path = shutil.which("c2patool")
    if on_path:
        return Path(on_path)

    # 3-4. Common install locations.
    for candidate in _FALLBACK_PATHS:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate

    raise C2PAToolNotFound(
        "c2patool not found. Install one of:\n"
        "  brew install c2patool                              (Mac)\n"
        "  download from https://github.com/contentauth/c2patool/releases  (Linux/Windows)\n"
        "  set FRESHMINT_C2PATOOL=/path/to/c2patool to override the search."
    )
