"""In-editor entry point for the Lantern pipeline.

Called by the LanternPipeline plugin's `init_unreal.py` once Unreal's Python
interpreter is up. Imports `unreal`, so it is only ever imported inside the
Unreal Editor — never from the outer venv. Keeping the logic here (rather than
in `init_unreal.py`) keeps it reloadable and testable.
"""

from __future__ import annotations

import unreal

from dcc.unreal.runtime import is_headless

# ToolMenus identifiers. The owner string scopes our entries so they can be
# cleanly removed/reloaded; the menu name is Unreal's level-editor menu bar.
_MENU_OWNER = "LanternPipeline"
_MAIN_MENU_NAME = "LevelEditor.MainMenu"
_PIPELINE_MENU_NAME = "Pipeline"


def main() -> None:
    """Load the pipeline into the running editor."""
    unreal.log("Lantern pipeline loaded")
    if is_headless():
        return
    _register_pipeline_menu()


def _register_pipeline_menu() -> None:
    """Add the (currently empty) top-level "Pipeline" menu to the editor."""
    menus = unreal.ToolMenus.get()
    main_menu = menus.find_menu(_MAIN_MENU_NAME)
    if main_menu is None:
        unreal.log_warning(
            "Lantern: could not find the Level Editor main menu; "
            "the Pipeline menu was not installed."
        )
        return

    main_menu.add_sub_menu(
        owner=_MENU_OWNER,
        section_name="",
        name=_PIPELINE_MENU_NAME,
        label="Pipeline",
        tool_tip="Lantern of Souls pipeline tools",
    )
    menus.refresh_all_widgets()
