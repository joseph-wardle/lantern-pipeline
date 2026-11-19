"""Unreal auto-runs this file at editor startup for every Python sys.path root.

The pipeline launcher sets `UE_PYTHONPATH` to `<repo>/src`, so `dcc.unreal` is
importable here. Keep this thin: defer all logic to `dcc.unreal.bootstrap` so it
stays reloadable and testable. A failure is logged but never re-raised, so a
tooling bug can never stop the editor from opening.
"""

import unreal

try:
    from dcc.unreal import bootstrap

    bootstrap.main()
except Exception as exc:  # noqa: BLE001 - never let tooling block the editor
    import traceback

    unreal.log_error(f"Lantern pipeline failed to load: {exc}")
    unreal.log_error(traceback.format_exc())
