"""Where RetroArch keeps its configuration and cores, and where Lutris keeps what it adds."""

from __future__ import annotations

import os
from pathlib import Path

from lutris import settings
from lutris.util.flatpak import get_app_dir

RETROARCH_FLATPAK_ID = "org.libretro.RetroArch"

# Core information Lutris downloads from the Libretro buildbot, to list cores and their systems
CORE_INFO_DIR = Path(settings.CACHE_DIR) / "libretro" / "info"


def get_flatpak_config_dir() -> Path:
    """Return the folder that holds the RetroArch Flatpak's configuration, cores and BIOS files."""
    return get_app_dir(RETROARCH_FLATPAK_ID) / "config" / "retroarch"


def get_native_config_dir() -> Path:
    """Return the folder that holds the configuration of a RetroArch installed on the system."""
    config_home = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(config_home) / "retroarch"
