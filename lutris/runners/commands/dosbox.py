"""DOSBox install script tasks, which run through RetroArch's DOSBox Pure core."""

from __future__ import annotations

import os
from gettext import gettext as _

from lutris.exceptions import MissingExecutableError
from lutris.util import system
from lutris.util.log import logger

DOSBOX_CORE = "dosbox_pure"


def dosexec(
    config_file: str | None = None,
    executable: str | None = None,
    args: str | None = None,
    close_on_exit: bool = True,
    working_dir: str | None = None,
) -> None:
    """Run a DOS program, or a DOSBox config file, and wait until RetroArch is closed.

    DOSBox's own command line arguments, and closing when the program exits, don't apply to
    the DOSBox Pure core, so 'args' and 'close_on_exit' are ignored."""
    if config_file:
        content = config_file
    elif executable:
        if not system.path_exists(executable):
            raise OSError("Can't find file {}".format(executable))
        content = executable
    else:
        raise ValueError("Neither a config file or an executable were provided")
    if args or not close_on_exit:
        logger.debug("The DOSBox core ignores the arguments '%s' and close_on_exit=%s", args, close_on_exit)
    working_dir = system.create_folder(working_dir or os.path.dirname(content))
    # The libretro runner offers these tasks, so it's imported here instead of at the top
    from lutris.runners.libretro import libretro  # noqa: PLC0415

    retroarch = libretro()
    core_path = retroarch.get_core_path(DOSBOX_CORE)
    if not system.path_exists(core_path):
        raise MissingExecutableError(_("RetroArch's DOSBox Pure core is not installed."))
    logger.debug("Running %s with DOSBox Pure", content)
    command = retroarch.get_command() + [f"--libretro={core_path}", content]
    system.execute(command, cwd=working_dir)


def makeconfig(path: str, drives: dict[str, str], commands: list[str]) -> None:
    system.create_folder(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as config_file:
        config_file.write("[autoexec]\n")
        for drive in drives:
            config_file.write('mount {} "{}"\n'.format(drive, drives[drive]))
        for command in commands:
            config_file.write("{}\n".format(command))
