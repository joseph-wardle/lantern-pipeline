"""Resolve the machine-specific Unreal game project at launch time.

The `.uproject` lives in a Perforce workspace whose root encodes the machine
name (e.g. `C:\\w-y27-101446-lanturn\\...`, see the project's own
`documentation.md`), so its path is never the same twice. It is discovered by
scanning the workspace roots — or set explicitly via `LANTERN_UE_PROJECT`.

The engine itself is pinned per machine in `env.py` (`Executables.unreal` /
`Executables.unreal_cmd`), exactly like every other DCC binary.
"""

from __future__ import annotations

import logging
import os
import platform
from pathlib import Path

log = logging.getLogger(__name__)

# Absolute override that wins over auto-discovery.
PROJECT_ENV_VAR = "LANTERN_UE_PROJECT"

_PROJECT_NAME = "LanternOfSouls"
# Perforce workspace roots sit at the root of C: as `w-<...>` (per the project
# documentation). The `.uproject` is one or two levels below the workspace root.
_WORKSPACE_GLOBS = ("w-*/*.uproject", "w-*/*/*.uproject")

_IS_WINDOWS = platform.system() == "Windows"


def resolve_uproject() -> Path:
    """Return the absolute path to the game's `.uproject`.

    Resolution order: `LANTERN_UE_PROJECT` env override, then a scan of the
    Perforce workspace roots on C:.
    """
    override = os.environ.get(PROJECT_ENV_VAR, "").strip()
    if override:
        path = Path(override)
        if not path.is_file():
            raise FileNotFoundError(
                f"{PROJECT_ENV_VAR} points at {path}, which does not exist."
            )
        return path

    discovered = _discover_uproject()
    if discovered is not None:
        log.info("Discovered Unreal project at %s", discovered)
        return discovered

    raise FileNotFoundError(
        f"Could not locate {_PROJECT_NAME}.uproject. The game lives in a "
        f"Perforce workspace whose path varies per machine; set "
        f"{PROJECT_ENV_VAR} to the absolute path of your .uproject."
    )


def _discover_uproject() -> Path | None:
    if not _IS_WINDOWS:
        return None
    search_root = Path("C:/")
    candidates: list[Path] = []
    for pattern in _WORKSPACE_GLOBS:
        candidates.extend(search_root.glob(pattern))
    if not candidates:
        return None

    # Prefer a project that matches the expected name; otherwise pick the first
    # match in a stable (sorted) order so the result is deterministic.
    preferred = [c for c in candidates if c.stem == _PROJECT_NAME]
    return sorted(preferred or candidates)[0]
