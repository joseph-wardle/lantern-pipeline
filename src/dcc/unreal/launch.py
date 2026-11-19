from __future__ import annotations

import logging
import platform
from pathlib import Path

from core.util.paths import get_shared_telemetry_spool_dir, resolve_mapped_path
from env import Executables
from framework.launcher import Launcher

from dcc.unreal.paths import resolve_uproject

log = logging.getLogger(__name__)


class UnrealLauncher(Launcher):
    """Unreal Editor outer-process launcher.

    Unlike the other DCCs, Unreal runs an *isolated* embedded interpreter that
    ignores `PYTHONPATH`, hosts Slate (not Qt), and is version-locked to the
    project. So the pipeline is surfaced through Unreal-native mechanisms:
    `UE_PYTHONPATH` for the shared `src/` modules and `UE_ADDITIONAL_PLUGIN_PATHS`
    for the bundled `LanternPipeline` plugin (which enables Python and runs the
    pipeline's `init_unreal.py`). The Perforce game repo is never modified.
    """

    def __init__(
        self, is_python_shell: bool = False, extra_args: list[str] | None = None
    ) -> None:
        this_path = Path(__file__).resolve()
        # this_path = `<repo>/src/dcc/unreal/launch.py`. `.resolve()` expands the
        # mapped network drive to a UNC path; resolve_mapped_path() maps it back
        # to the short drive (e.g. G:) that Unreal handles most predictably.
        src_path = resolve_mapped_path(this_path.parents[2])
        plugins_path = resolve_mapped_path(this_path.parent / "site" / "Plugins")

        editor = Executables.unreal_cmd if is_python_shell else Executables.unreal
        if editor is None:
            raise RuntimeError(
                f"Unreal Engine is only configured for Windows in this pipeline "
                f"(platform={platform.system()})."
            )

        uproject = resolve_uproject()
        log.info("Launching Unreal for project %s", uproject)

        env_vars: dict[str, int | str | None] = {
            "DCC": this_path.parent.name,
            # UE's isolated interpreter ignores PYTHONPATH; UE_PYTHONPATH is the
            # documented escape hatch and its entries are also scanned for
            # init_unreal.py. src/ makes core/framework/env/dcc importable.
            "UE_PYTHONPATH": str(src_path),
            # Editor-only (UE 5.3+): discovers the LanternPipeline plugin without
            # copying anything into the Perforce game repo. That plugin depends
            # on PythonScriptPlugin, so enabling it turns Python on.
            "UE_ADDITIONAL_PLUGIN_PATHS": str(plugins_path),
            "PIPE_LOG_LEVEL": log.getEffectiveLevel(),
            "PIPE_TELEMETRY_SPOOL_DIR": str(get_shared_telemetry_spool_dir()),
            # Read by UnrealRuntime.is_headless(); set only on the commandlet path.
            "PIPE_UE_HEADLESS": 1 if is_python_shell else None,
        }

        if is_python_shell:
            # No interactive REPL exists for the editor; run the pythonscript
            # commandlet, with the caller supplying `-script=...` via extra_args.
            launch_args = [str(uproject), "-run=pythonscript", *(extra_args or [])]
        else:
            launch_args = [str(uproject), *(extra_args or [])]

        super().__init__(str(editor), launch_args, env_vars)
