"""Generate and install the Lantern of Souls DCC launchers (Linux).

Run from the "Install Lantern DCCs" entry in ``Software``, or directly:

    .venv/bin/python install_desktop_launchers.py

Pass ``--software`` to (re)publish the launchers into the shared ``Software``
folder after a redeploy.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Deliberately not `.resolve()`d: artists reach the deploy through the stable
# /groups/lantern path, and that is the path the launchers should record.
REPO_ROOT = Path(__file__).absolute().parent
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
SRC = REPO_ROOT / "src"
ICONS = REPO_ROOT / "resources" / "icon"
APPLICATIONS = Path.home() / ".local" / "share" / "applications"
# The deploy lives at <share>/.pipeline; Software is its sibling on the share.
SOFTWARE_DIR = REPO_ROOT.parent / "Software"


@dataclass(frozen=True)
class Launcher:
    filename: str  # installed .desktop name, e.g. "mayo.desktop"
    name: str  # menu display name, e.g. "Mayo"
    dcc: str  # launch target under src/dcc/, e.g. "maya"
    icon: str  # icon file in resources/icon/

    @property
    def generic_name(self) -> str:
        return f"Lantern of Souls {self.dcc.capitalize()} Launcher"

    @property
    def exec_line(self) -> str:
        # The desktop environment does not source the user's shell rc, so
        # every path here must be absolute.
        return f"{VENV_PYTHON} {SRC} {self.dcc}"


# Substance and Unreal are Windows-only and launched from .lnk shortcuts.
LAUNCHERS = [
    Launcher("mayo.desktop", "Mayo", "maya", "maya.png"),
    Launcher("panini.desktop", "Panini", "houdini", "houdini.png"),
    Launcher("toaster.desktop", "Toaster", "blender", "blender.png"),
]

INSTALLER = (
    "[Desktop Entry]\n"
    "Type=Application\n"
    "Name=Install Lantern DCCs\n"
    "GenericName=Install Lantern of Souls Launchers\n"
    f"Exec={VENV_PYTHON} {REPO_ROOT / 'install_desktop_launchers.py'}\n"
    "Icon=system-software-install\n"
    "Terminal=false\n"
    "StartupNotify=true\n"
)


def render(launcher: Launcher) -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={launcher.name}\n"
        f"GenericName={launcher.generic_name}\n"
        f"Exec={launcher.exec_line}\n"
        f"Icon={ICONS / launcher.icon}\n"
        f"StartupWMClass={launcher.name}\n"
        "StartupNotify=true\n"
        "Terminal=false\n"
    )


def _write(target: Path, text: str, verb: str) -> None:
    # Replace any prior file or the old symlink-based launchers.
    if target.is_symlink() or target.exists():
        target.unlink()
    target.write_text(text, encoding="utf-8")
    # Desktop environments refuse to run a .desktop file that isn't executable.
    target.chmod(0o775)
    print(f"{verb} {target}")


def _write_launchers(dest_dir: Path, verb: str) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    for launcher in LAUNCHERS:
        _write(dest_dir / launcher.filename, render(launcher), verb)


def install() -> None:
    """Primary path: put the launchers in the user's application menu."""
    _write_launchers(APPLICATIONS, "Installed")
    subprocess.run(["update-desktop-database", str(APPLICATIONS)], check=False)
    print("Updated desktop database")


def publish_to_software() -> None:
    """Deploy step: provision the shared Software folder.

    Writes the per-DCC launchers so artists can double-click them straight
    from the share, plus the installer entry that adds menu shortcuts.
    """
    _write_launchers(SOFTWARE_DIR, "Published")
    _write(SOFTWARE_DIR / "installer.desktop", INSTALLER, "Published")


if __name__ == "__main__":
    if not VENV_PYTHON.exists():
        sys.exit(
            f"venv python not found at {VENV_PYTHON}; run `uv sync` in {REPO_ROOT} first"
        )
    if "--software" in sys.argv[1:]:
        publish_to_software()
    else:
        install()
