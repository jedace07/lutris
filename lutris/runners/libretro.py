"""Run games through the RetroArch Flatpak and its libretro cores."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from gettext import gettext as _
from io import BytesIO
from operator import itemgetter
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any
from zipfile import BadZipFile, ZipFile

import requests

from lutris.config import LutrisConfig
from lutris.exceptions import GameConfigError, MissingBiosError, UnspecifiedVersionError
from lutris.runners import RunnerInstallationError
from lutris.runners.commands.dosbox import dosexec, makeconfig  # noqa: F401 Install script tasks
from lutris.runners.runner import Runner
from lutris.util import async_choices, cache_single, system
from lutris.util.libretro import RetroConfig
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import logger
from lutris.util.retroarch.content import GENERATED_CONTENT_DIR, get_content_path
from lutris.util.retroarch.firmware import get_firmware, scan_firmware_directory
from lutris.util.retroarch.locations import (
    CORE_INFO_DIR,
    RETROARCH_FLATPAK_ID,
    get_flatpak_config_dir,
    get_native_config_dir,
)

if TYPE_CHECKING:
    from lutris.delegates import InstallUIDelegate
    from lutris.installer.installer import LutrisInstaller
    from lutris.installer.interpreter import ScriptInterpreter

RETROARCH_TO_LUTRIS_PLATFORM_MAP = {
    "2048 Game Clone": "",
    "3D Engine": "",
    "3DO": "",
    "3DS": "Nintendo 3DS",
    "Advanced Test Core": "",
    "Amiga": "Commodore Amiga",
    "Arcade (various)": "Arcade",
    "Atari 2600": "Atari 2600",
    "Atari 5200": "",
    "Atari 7800": "",
    "Atari ST/STE/TT/Falcon": "Atari ST",
    "BK-0010/BK-0011(M)": "",
    "C128": "",
    "C64": "",
    "C64 SuperCPU": "",
    "Cave Story Game Engine": "",
    "CBM-5x0": "",
    "CBM-II": "",
    "ChaiLove": "",
    "CHIP-8": "",
    "Classic Tomb Raider engine": "",
    "ColecoVision": "",
    "Commodore Amiga": "",
    "CPC": "",
    "CP System I": "",
    "CP System II": "",
    "CP System III": "",
    "Cruzes": "",
    "Dinothawr Game Engine": "",
    "Doom 3 Game Engine": "",
    "Doom 3 XP Game Engine": "",
    "DOOM Game Engine": "",
    "DOS": "MS-DOS",
    "DS": "",
    "FFmpeg": "",
    "Flashback Game Engine": "",
    "FreeChaF": "",
    "Game Boy Advance": "Nintendo Game Boy Advance",
    "Game Boy/Game Boy Color": "Nintendo Game Boy (Color)",
    "Game Boy/Game Boy Color/Game Boy Advance": "Nintendo Game Boy Advance",
    "GameCube / Wii": "Nintendo Wii",
    "Game engine": "",
    "Handheld Electronic": "",
    "Intellivision": "",
    "J2ME": "",
    "Jaguar": "",
    "Java ME": "",
    "LowRes NX": "",
    "Lutro": "",
    "Lynx": "",
    "Mac68k": "Macintosh",
    "Magnavox Odyssey2 / Phillips Videopac+": "",
    "Mega Duck": "",
    "Model 3": "Arcade",
    "Minecraft Game Clone": "",
    "Moonlight": "",
    "MPV": "",
    "Mr.Boom": "",
    "MSX": "Microsoft MSX",
    "MSX/MSX2/MSX2+/turbo R": "Microsoft MSX",
    "MSX/SVI/ColecoVision/SG-1000": "",
    "Multi (various)": "",
    "Music": "",
    "Neo Geo": "",
    "Neo Geo Pocket (Color)": "SNK Neo Geo Pocket (Color)",
    "Nintendo 64": "Nintendo 64",
    "Nintendo DS": "Nintendo DS",
    "Nintendo Entertainment System": "Nintendo NES",
    "Oberon RISC machine": "",
    "Outrun Game Engine": "",
    "Palm OS": "",
    "PC": "",
    "PC-8000 / PC-8800 series": "",
    "PC-98": "",
    "PC Engine/PCE-CD": "",
    "PC Engine SuperGrafx": "",
    "PC Engine/SuperGrafx/CD": "",
    "PC-FX": "",
    "PET": "",
    "Physics Toy": "",
    "PICO8": "",
    "PlayStation": "Sony PlayStation",
    "PlayStation 3": "Sony PlayStation 3",
    "PlayStation Vita": "Sony PlayStation Vita",
    "PLUS/4": "",
    "Pokemon Mini": "",
    "Pong Game Clone": "",
    "PSP": "Sony Playstation Portable",
    "Quake 3 Game Engine": "",
    "Quake Game Engine": "",
    "Quake II Game Engine": "",
    "Redbook": "",
    "Rick Dangerous Game Engine": "",
    "RPG Maker 2000/2003 Game Engine": "",
    "SAM coupe": "",
    "Saturn": "Sega Saturn",
    "Sega 8/16-bit + 32X (Various)": "",
    "Sega 8/16-bit (Various)": "Sega Genesis",
    "Sega 8-bit": "",
    "Sega 8-bit (MS/GG/SG-1000)": "",
    "Sega Dreamcast": "Sega Dreamcast",
    "Sega Genesis": "Sega Genesis/Mega Drive",
    "Sega Master System": "Sega Master System",
    "SEGA Visual Memory Unit": "",
    "Sharp X1": "",
    "Sharp X68000": "",
    "SNK Neo Geo CD": "",
    "Sony PlayStation 2": "Sony PlayStation 2",
    "Super Nintendo Entertainment System": "Nintendo SNES",
    "Super Nintendo Entertainment System / Game Boy / Game Boy Color": "",
    "Supervision": "",
    "Test for netplay": "",
    "Thomson MO/TO": "",
    "TIC-80": "",
    "Tyrian Game Engine": "",
    "Uzebox": "",
    "Vectrex": "",
    "VIC-20": "",
    "Virtual Boy": "Nintendo Virtual Boy",
    "Wolfenstein 3D Game Engine": "",
    "Wii U": "Nintendo Wii U",
    "WonderSwan/Color": "Bandai WonderSwan Color",
    "Xbox": "Microsoft Xbox",
    "Xbox 360": "Microsoft Xbox 360",
    "ZX81": "",
    "ZX Spectrum (various)": "",
}


def _download_libretro_info() -> bool:
    """Download the libretro core info archive from the buildbot. Run on a worker thread."""
    try:
        response = requests.get("https://buildbot.libretro.com/assets/frontend/info.zip", timeout=5)
        response.raise_for_status()
        CORE_INFO_DIR.parent.mkdir(parents=True, exist_ok=True)
        with (
            TemporaryDirectory(dir=CORE_INFO_DIR.parent) as staging_dir,
            ZipFile(BytesIO(response.content)) as archive,
        ):
            staged = Path(staging_dir) / "info"
            archive.extractall(staged)
            try:
                staged.replace(CORE_INFO_DIR)
            except OSError:
                if not CORE_INFO_DIR.is_dir():
                    raise
    except (requests.RequestException, BadZipFile, OSError) as ex:
        logger.warning("Could not download Libretro core information: %s", ex)
        return False
    return True


@cache_single
def get_libretro_cores() -> list[tuple[str, str, str]]:
    """Return the list of available libretro cores by reading installed info files.

    If the info archive hasn't been downloaded yet, performs a synchronous download. Callers on
    the UI thread should prefer triggering the async download via get_core_choices() first, so
    this fallback is rarely reached in practice.
    """
    if not CORE_INFO_DIR.is_dir() and not _download_libretro_info():
        return []
    cores: list[tuple[str, str, str]] = []
    for info_file in os.listdir(CORE_INFO_DIR):
        if "_libretro.info" not in info_file:
            continue
        core_identifier = info_file.replace("_libretro.info", "")
        core_config = RetroConfig(str(CORE_INFO_DIR / info_file))
        if "categories" in core_config.keys() and "Emulator" in core_config["categories"]:
            core_label = str(core_config["display_name"] or "")
            core_system = str(core_config["systemname"] or "")
            cores.append((core_label, core_identifier, core_system))
    cores.sort(key=itemgetter(0))
    return cores


@async_choices(
    generate=_download_libretro_info,
    ready=CORE_INFO_DIR.is_dir,
    invalidate=get_libretro_cores.cache_clear,
    error_message="Failed to download libretro info archive",
)
def get_core_choices() -> list[tuple[str, str]]:
    """Return (label, identifier) pairs for all libretro cores, for use as a choices callable.

    If the info archive hasn't been downloaded yet, kicks off a background download and returns
    [] immediately. Any callbacks registered via register_reload_callback() are invoked on the
    UI thread when the download completes, so dropdowns can repopulate without the user having
    to close and reopen the dialog.
    """
    return [(core[0], core[1]) for core in get_libretro_cores()]


def _resolve_config_path(value: str, config_file: str) -> str:
    """Expand a path from a RetroArch config, where a leading ':' stands for the config's folder."""
    if value.startswith(":"):
        value = os.path.join(os.path.dirname(config_file), value[1:].lstrip("/\\"))
    return os.path.expanduser(value)


class libretro(Runner):
    human_name = _("RetroArch")
    description = _("Multi-system emulator")
    runnable_alone = True
    flatpak_id = RETROARCH_FLATPAK_ID

    game_options = [
        {"option": "main_file", "type": "file", "label": _("ROM file")},
        {
            "option": "core",
            "type": "choice",
            "label": _("Core"),
            "choices": get_core_choices,
        },
    ]

    runner_options = [
        {
            "option": "config_file",
            "type": "file",
            "label": _("Config file"),
            "help": _("A RetroArch configuration file to use instead of RetroArch's own."),
        },
        {
            "option": "fullscreen",
            "type": "bool",
            "label": _("Fullscreen"),
            "default": True,
        },
        {
            "option": "verbose",
            "type": "bool",
            "label": _("Verbose logging"),
            "default": False,
        },
    ]

    def __init__(self, config: LutrisConfig | None = None) -> None:
        super().__init__(config)
        self.platform_dict = {}
        for core in get_libretro_cores():
            platform = core[2]
            if lutris_platform := RETROARCH_TO_LUTRIS_PLATFORM_MAP.get(platform):
                self.platform_dict[lutris_platform] = platform
            else:
                self.platform_dict[platform] = platform

    def get_platform(self) -> str:
        game_core = self.game_config.get("core")
        if not game_core:
            logger.warning("Game don't have a core set")
            return ""
        for core in get_libretro_cores():
            if core[1] == game_core and core[2] in self.platform_dict:
                return self.platform_dict[core[2]]
        logger.warning("'%s' not found in Libretro cores", game_core)
        return ""

    @property
    def uses_flatpak(self) -> bool:
        """True unless the user set a RetroArch executable of their own."""
        executable = self.runner_config.get("runner_executable")
        return not (executable and os.path.isfile(executable))

    def get_config_file(self) -> str:
        """Return the configuration RetroArch reads: the one set in the runner's options, or its own."""
        if config_file := self.runner_config.get("config_file"):
            return os.path.expanduser(config_file)
        config_dir = get_flatpak_config_dir() if self.uses_flatpak else get_native_config_dir()
        return str(config_dir / "retroarch.cfg")

    def _get_config_directory(self, key: str, default: str) -> str:
        config_file = self.get_config_file()
        if system.path_exists(config_file):
            value = RetroConfig(config_file).get(key)
            if value and value != "default":
                return _resolve_config_path(value, config_file)
        return os.path.join(os.path.dirname(config_file), default)

    def get_cores_directory(self) -> str:
        """Return the directory RetroArch loads cores from, as its configuration sets it."""
        return self._get_config_directory("libretro_directory", "cores")

    def get_system_directory(self) -> str:
        """Return the directory RetroArch looks for BIOS and firmware files in."""
        return self._get_config_directory("system_directory", "system")

    def get_core_path(self, core: str) -> str:
        """Return the path of a core within the configured cores directory."""
        return os.path.join(self.get_cores_directory(), f"{core}_libretro.so")

    def get_version(self, use_default: bool = True) -> str | None:
        return self.game_config.get("core")

    def is_installed(self, flatpak_allowed: bool = True, core: str | None = None) -> bool:
        if not core and self.has_explicit_config and self.game_config.get("core"):
            core = self.game_config["core"]
        if not super().is_installed(flatpak_allowed=flatpak_allowed):
            return False
        return not core or system.path_exists(self.get_core_path(core))

    def is_installed_for(self, interpreter: ScriptInterpreter) -> bool:
        core = interpreter.installer.script["game"].get("core")
        return self.is_installed(core=core)

    def get_installer_runner_version(self, installer: LutrisInstaller, use_runner_config: bool = True) -> str:
        version = installer.script["game"].get("core")
        if not version:
            raise UnspecifiedVersionError(_("The installer does not specify the libretro 'core' version."))
        return version

    def install(
        self,
        install_ui_delegate: InstallUIDelegate,
        version: str | None = None,
        callback: Callable[[], None] | None = None,
    ) -> None:
        """Install RetroArch from Flathub if it's missing, then the core, the way RetroArch's
        own updater does: from the Libretro buildbot into RetroArch's cores directory."""
        if not super().is_installed():
            super().install(install_ui_delegate)
        core = version or self.get_version(use_default=False)
        if not core or system.path_exists(self.get_core_path(core)):
            if callback:
                callback()
            return
        platform_dir = {"x86_64": "x86_64", "i386": "x86", "aarch64": "aarch64"}.get(LINUX_SYSTEM.arch or "")
        if platform_dir is None or not re.fullmatch(r"[a-zA-Z0-9_-]+", core):
            raise RunnerInstallationError(_("No upstream Libretro build for core '%s' on this architecture.") % core)
        executable = f"{core}_libretro.so"
        url = f"https://buildbot.libretro.com/nightly/linux/{platform_dir}/latest/{executable}.zip"
        self.download_and_extract(url, install_ui_delegate, self.get_cores_directory(), executable, callback)

    def get_flatpak_filesystems(self) -> list[str]:
        return [*super().get_flatpak_filesystems(), str(GENERATED_CONTENT_DIR)]

    def get_run_data(self) -> dict[str, Any]:
        return {
            "command": self.get_command() + self.get_runner_parameters(),
            "env": self.get_env(),
        }

    def prelaunch(self) -> None:
        super().prelaunch()
        core = self.game_config.get("core")
        info_file = CORE_INFO_DIR / f"{core}_libretro.info"
        if not core or not info_file.is_file():
            return
        core_info = RetroConfig(str(info_file))
        try:
            firmware_count = int(core_info["firmware_count"])
            mandatory_firmware_count = sum(1 for i in range(firmware_count) if not core_info.get("firmware%d_opt" % i))
        except ValueError, TypeError:
            firmware_count = 0
            mandatory_firmware_count = 0
        system_path = self.get_system_directory()
        notes = str(core_info["notes"] or "")
        checksums = {}
        if notes.startswith("(!)"):
            for part in notes.split("|"):
                try:
                    filename, checksum = part.split(" (md5): ")
                except ValueError:
                    logger.warning("Unable to parse firmware info: %s", notes)
                    continue
                checksums[filename.replace("(!) ", "")] = checksum

        # If this requires firmware, confirm we have the firmware folder configured in the first place
        # then rescan it in case the user added anything since the last time they changed it
        if mandatory_firmware_count > 0:
            firmware_directory = LutrisConfig().raw_system_config.get("bios_path")
            if not firmware_directory:
                raise MissingBiosError(
                    _("The emulator files BIOS location must be configured in the Preferences dialog.")
                )
            scan_firmware_directory(firmware_directory)

        for index in range(firmware_count):
            optional_prefix = "Optional firmware" if core_info.get("firmware%d_opt" % index) else "Firmware"
            firmware_filename = core_info["firmware%d_path" % index]
            firmware_path = os.path.join(system_path, firmware_filename)
            firmware_name = firmware_filename.split("/")[-1]
            firmware_checksum = checksums.get(firmware_name)
            if system.path_exists(firmware_path):
                if firmware_checksum:
                    checksum = system.get_md5_hash(firmware_path)
                    checksum_status = "Checksum good" if checksum == firmware_checksum else "Checksum failed"
                else:
                    checksum_status = "No checksum info"
                logger.info("%s '%s' found (%s)", optional_prefix, firmware_filename, checksum_status)
            else:
                logger.warning("%s '%s' not found!", optional_prefix, firmware_filename)
                if firmware_checksum:
                    get_firmware(firmware_name, firmware_checksum, os.path.dirname(firmware_path))

    def get_runner_parameters(self) -> list[str]:
        parameters = []
        if self.runner_config.get("fullscreen"):
            parameters.append("--fullscreen")
        if self.runner_config.get("verbose"):
            parameters.append("--verbose")
        if config_file := self.runner_config.get("config_file"):
            parameters.append("--config={}".format(os.path.expanduser(config_file)))
        return parameters

    def play(self) -> dict[str, Any]:
        core = self.game_config.get("core")
        if not core:
            raise GameConfigError(_("No core has been selected for this game"))
        content = get_content_path(core, self.game_config)
        command = self.get_command() + self.get_runner_parameters()
        command += ["--libretro={}".format(self.get_core_path(core)), content]
        result: dict[str, Any] = {"command": command}
        # DOSBox games ported from the standalone runner mount drives relative to their working directory
        if working_dir := self.game_config.get("working_dir"):
            result["working_dir"] = os.path.expanduser(working_dir)
        return result
