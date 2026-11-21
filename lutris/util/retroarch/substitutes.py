"""The libretro cores that replace the standalone emulators Lutris used to run.

Games and install scripts that name one of these runners run through RetroArch with
the matching core instead. Their game options move to the libretro runner, and the
runner's own options, which configured the standalone emulator, are dropped.
"""

from __future__ import annotations

import shlex
from typing import Any

LIBRETRO = "libretro"

# The core that replaces each removed runner
RUNNER_CORES: dict[str, str] = {
    "atari800": "atari800",
    "azahar": "azahar",
    "blastem": "blastem",
    "cemu": "cemu",
    "citra": "azahar",
    "colem": "gearcoleco",
    "desmume": "melondsds",
    "dgen": "genesis_plus_gx",
    "dolphin": "dolphin",
    "dosbox": "dosbox_pure",
    "duckstation": "swanstation",
    "easyrpg": "easyrpg",
    "flycast": "flycast",
    "fsuae": "puae",
    "gzdoom": "uzdoom",
    "hatari": "hatarib",
    "jzintv": "freeintv",
    "mame": "mame",
    "mednafen": "mednafen_psx_hw",
    "melonds": "melondsds",
    "mgba": "mgba",
    "microm8": "applewin",
    "minivmac": "minivmac",
    "mupen64plus": "mupen64plus_next",
    "o2em": "o2em",
    "openmsx": "openmsx",
    "osmose": "genesis_plus_gx",
    "pcsx2": "pcsx2",
    "ppsspp": "ppsspp",
    "redream": "flycast",
    "reicast": "flycast",
    "rosaliesmupengui": "mupen64plus_next",
    "rpcs3": "rpcs3",
    "scummvm": "scummvm",
    "snes9x": "snes9x",
    "speccy": "fuse",
    "stella": "stella",
    "supermodel": "supermodel",
    "tic80": "tic80",
    "uzdoom": "uzdoom",
    "vice": "vice_x64",
    "virtualjaguar": "virtualjaguar",
    "vita3k": "vita3k",
    "xemu": "xemu",
    "xenia": "xenia_edge",
    "zdoom": "uzdoom",
}

# Mednafen and VICE emulate several machines, which have a core each
_MACHINE_CORES: dict[str, dict[str, str]] = {
    "mednafen": {
        "gb": "gambatte",
        "gba": "mgba",
        "gg": "genesis_plus_gx",
        "lynx": "mednafen_lynx",
        "md": "genesis_plus_gx",
        "nes": "mesen",
        "ngp": "mednafen_ngp",
        "pce": "mednafen_pce",
        "pce_fast": "mednafen_pce_fast",
        "pcfx": "mednafen_pcfx",
        "psx": "mednafen_psx_hw",
        "sms": "genesis_plus_gx",
        "snes": "mednafen_snes",
        "ss": "mednafen_saturn",
        "vb": "mednafen_vb",
        "wswan": "mednafen_wswan",
    },
    "vice": {
        "c128": "vice_x128",
        "c64": "vice_x64",
        "pet": "vice_xpet",
        "plus4": "vice_xplus4",
        "vic20": "vice_xvic",
    },
}

# Runners renamed when their emulator's project was succeeded
RUNNER_RENAMES: dict[str, str] = {"yuzu": "eden", "ryujinx": "ryubing", "frotz": "gargoyle"}

# Runners whose install script tasks moved to the libretro runner
_TASK_RUNNERS = {"dosbox": LIBRETRO}

# The option that held each runner's game, when it isn't 'main_file'
_ENTRY_POINTS = {"easyrpg": "project_path", "hatari": "disk-a", "vita3k": "title_id"}

# Options that only configured the standalone emulator
_DROPPED_OPTIONS = {
    "cemu": ("wua_rom",),
    "dolphin": ("platform",),
    "fsuae": ("cdrom_image", "disks", "model", "platform"),
    "hatari": ("disk-a", "disk-b"),
    "mednafen": ("machine",),
    "vice": ("machine",),
    "xenia": ("arch", "prefix"),
}


def is_substituted(runner: str) -> bool:
    """True if the runner was replaced by a libretro core."""
    return runner in RUNNER_CORES


def get_substitute_core(runner: str, game_config: dict[str, Any]) -> str | None:
    """Return the core that runs a game made for a removed runner, or None for another runner."""
    if (machines := _MACHINE_CORES.get(runner)) and (machine := game_config.get("machine")) in machines:
        return machines[str(machine)]
    return RUNNER_CORES.get(runner)


def translate_game_config(runner: str, game_config: dict[str, Any]) -> dict[str, Any]:
    """Return the libretro game options for a game made for a removed runner."""
    core = get_substitute_core(runner, game_config)
    if core is None:
        return game_config
    config = dict(game_config)
    entry_point = _ENTRY_POINTS.get(runner)
    if entry_point and entry_point in config:
        config["main_file"] = config.pop(entry_point)
    if runner == "cemu" and config.get("wua_rom"):
        config["main_file"] = config["wua_rom"]
    if runner == "fsuae" and not config.get("main_file") and config.get("cdrom_image"):
        config["main_file"] = config["cdrom_image"]
    if runner == "dosbox" and (extra := get_dosbox_config_files(str(config.get("args") or ""))):
        config.setdefault("config_file", extra[-1])
    for option in _DROPPED_OPTIONS.get(runner, ()):
        config.pop(option, None)
    config["core"] = core
    return config


def get_dosbox_config_files(args: str) -> list[str]:
    """Return the files a DOSBox command line loads with -conf."""
    try:
        words = shlex.split(args)
    except ValueError:
        words = args.split()
    files = [words[index + 1] for index, word in enumerate(words[:-1]) if word.casefold() == "-conf"]
    # Launchers written for Windows give paths Lutris can't resolve
    return [path for path in files if "\\" not in path]


def translate_runner(runner: str) -> str:
    """Return the runner that replaced a removed or renamed one."""
    if is_substituted(runner):
        return LIBRETRO
    return RUNNER_RENAMES.get(runner, runner)


def translate_task_name(name: str) -> str:
    """Return the name of an install script task once its runner's tasks moved elsewhere."""
    runner, separator, task = name.partition(".")
    if separator and runner in _TASK_RUNNERS:
        return f"{_TASK_RUNNERS[runner]}.{task}"
    return name


def translate_script(runner: str, script: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Return the runner and script that install a game the way the script did with a removed runner.

    The script's game options become libretro options, the removed runner's own section is
    dropped, and tasks of runners that moved are renamed."""
    script = dict(script)
    if commands := script.get("installer"):
        script["installer"] = [_translate_command(command) for command in commands]
    if not is_substituted(runner):
        new_runner = RUNNER_RENAMES.get(runner, runner)
        if new_runner != runner and runner in script:
            script[new_runner] = script.pop(runner)
        return new_runner, script
    script.pop(runner, None)
    script["game"] = translate_game_config(runner, dict(script.get("game") or {}))
    return LIBRETRO, script


def _translate_command(command: Any) -> Any:
    if isinstance(command, dict) and isinstance(task := command.get("task"), dict) and "name" in task:
        return {**command, "task": {**task, "name": translate_task_name(str(task["name"]))}}
    return command
