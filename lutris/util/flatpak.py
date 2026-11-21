"""Run and install the Flathub apps that Lutris uses as runners."""

from __future__ import annotations

import os
import shutil
import subprocess
from gettext import gettext as _
from pathlib import Path
from typing import TYPE_CHECKING

from lutris.exceptions import LutrisError, UnavailableRunnerError
from lutris.util import cache_single
from lutris.util.log import logger
from lutris.util.system import read_process_output

if TYPE_CHECKING:
    from collections.abc import Iterable

FLATHUB_REMOTE = "flathub"
FLATHUB_REPO_URL = "https://dl.flathub.org/repo/flathub.flatpakrepo"

# Variables that point at libraries or drivers outside the app's sandbox, which would break it
UNFORWARDED_ENV = frozenset(
    {
        "LD_LIBRARY_PATH",
        "LD_PRELOAD",
        "PATH",
        "PYTHONPATH",
        "VK_ICD_FILENAMES",
        "VK_DRIVER_FILES",
        "__GL_SHADER_DISK_CACHE_PATH",
    }
)

# Folders that belong to a sandbox or to the system, which Flatpak won't share with an app
_UNSHAREABLE_ROOTS = (Path("/app"), Path("/usr"), Path("/etc"), Path("/proc"), Path("/sys"))


class FlatpakError(LutrisError):
    """Raised when Flatpak fails to install an app."""


@cache_single
def get_executable() -> str | None:
    """Return the executable used to access Flatpak. None if Flatpak is not installed.

    In the case where Lutris is a Flatpak, we use flatpak-spawn. Some systems install
    flatpak-spawn outside of any sandbox too, where it can't reach the host's Flatpak.
    """
    if os.path.exists("/.flatpak-info"):
        return shutil.which("flatpak-spawn")
    return shutil.which("flatpak")


def is_installed() -> bool:
    """Returns Flatpak is installed"""
    return bool(get_executable())


def get_command() -> list[str]:
    """Return the full command used to interact with Flatpak."""
    exe = get_executable()
    if not exe:
        raise UnavailableRunnerError(_("Flatpak is not installed"))
    if "flatpak-spawn" in exe:
        return [exe, "--host", "flatpak"]
    return [exe]


@cache_single
def get_installed_apps() -> list[dict[str, str]]:
    if not is_installed():
        return []

    command = get_command() + ["list", "--columns=name,application,version,branch,arch,origin,installation"]
    package_list = read_process_output(command)
    packages = []
    for package in package_list.split("\n"):
        if package:
            try:
                name, appid, version, branch, arch, origin, installation = package.split("\t")
            except ValueError:
                logger.error("Not able to parse Flatpak output: %s", package)
                continue
            packages.append(
                {
                    "name": name,
                    "appid": appid,
                    "version": version,
                    "branch": branch,
                    "arch": arch,
                    "origin": origin,
                    "installation": installation,
                }
            )
    return packages


def is_app_installed(appid: str | None) -> bool:
    """Return whether an app is installed"""
    if not appid:
        return False
    return any(app["appid"] == appid for app in get_installed_apps())


def get_app_dir(appid: str) -> Path:
    """Return the folder that holds an app's own configuration and data, as the host sees it."""
    return Path.home() / ".var" / "app" / appid


def get_shareable_paths(paths: Iterable[str]) -> list[str]:
    """Return the existing folders that hold the paths, in the order given, for sharing with an app."""
    folders: list[str] = []
    for path in paths:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute() or not candidate.exists():
            continue
        folder = candidate if candidate.is_dir() else candidate.parent
        if folder == Path("/") or any(folder.is_relative_to(root) for root in _UNSHAREABLE_ROOTS):
            continue
        if str(folder) not in folders:
            folders.append(str(folder))
    return folders


def get_run_command(appid: str, filesystems: Iterable[str] = ()) -> list[str]:
    """Return the command that launches a Flatpak app, sharing the folders given with it."""
    # The explicit mode keeps a ':' in a folder's name from being read as one
    shares = [f"--filesystem={folder}:rw" for folder in get_shareable_paths(filesystems)]
    return [*get_command(), "run", *shares, appid]


def add_environment(command: list[str], appid: str, env: dict[str, str]) -> list[str]:
    """Pass the game's environment to the app a 'flatpak run' command launches.

    When Lutris is itself a Flatpak, flatpak-spawn starts the app with the host's environment,
    so the variables have to be given to 'flatpak run'. Variables that describe libraries or
    drivers outside the app's sandbox are removed from env and not passed on."""
    try:
        run_index = command.index("run")
        app_index = command.index(appid, run_index)
    except ValueError:
        return command
    for key in UNFORWARDED_ENV:
        env.pop(key, None)
    variables = [f"--env={key}={value}" for key, value in env.items()]
    return [*command[:app_index], *variables, *command[app_index:]]


def install_app(appid: str) -> None:
    """Install an app from Flathub for the current user, adding the Flathub remote if needed."""
    command = get_command()
    steps = (
        [*command, "remote-add", "--user", "--if-not-exists", FLATHUB_REMOTE, FLATHUB_REPO_URL],
        [*command, "install", "--user", "--noninteractive", "-y", FLATHUB_REMOTE, appid],
    )
    logger.info("Installing %s from Flathub", appid)
    try:
        for step in steps:
            subprocess.run(step, check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as ex:
        details = ex.stderr.strip() if isinstance(ex, subprocess.CalledProcessError) else str(ex)
        raise FlatpakError(_("Flatpak could not install %s: %s") % (appid, details)) from ex
    finally:
        get_installed_apps.cache_clear()
