from __future__ import annotations

import os

from framework.interface import DCCRuntime

_HEADLESS_ENV_VAR = "PIPE_UE_HEADLESS"


class UnrealRuntime(DCCRuntime):
    """In-editor runtime context for Unreal.

    Deliberately does not import `unreal`: both methods answer from process
    state, so this module stays importable from anywhere (including the outer
    venv and headless tooling).
    """

    def get_main_qt_window(self) -> None:
        # Unreal's editor UI is Slate, not Qt. Pipeline UI integrates through
        # unreal.ToolMenus and Editor Utility Widgets, so there is no Qt main
        # window to parent dialogs to.
        return None

    def is_headless(self) -> bool:
        # Set by UnrealLauncher when launching the -run=pythonscript commandlet.
        return os.environ.get(_HEADLESS_ENV_VAR) == "1"


_runtime = UnrealRuntime()

get_main_qt_window = _runtime.get_main_qt_window
is_headless = _runtime.is_headless
