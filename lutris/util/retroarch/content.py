"""The file RetroArch loads for a game.

Most cores load the game's own file. Some load a small file that describes the game
instead, like the ScummVM core's .scummvm files or MAME's .cmd command lines; Lutris
writes those from the game's options, which may come from the standalone emulator
the core replaced.
"""

from __future__ import annotations

import hashlib
import os
import shlex
from gettext import gettext as _
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lutris import settings
from lutris.exceptions import GameConfigError, MissingGameExecutableError
from lutris.util.log import logger

if TYPE_CHECKING:
    from collections.abc import Mapping

# Description files Lutris writes for cores that need them
GENERATED_CONTENT_DIR = Path(settings.CACHE_DIR) / "libretro" / "content"

_DOSBOX_CORES = frozenset({"dosbox_pure", "dosbox_core", "dosbox_svn"})


def get_content_path(core: str, game_config: Mapping[str, Any]) -> str:
    """Return the file the core should load for a game, writing it first if Lutris generates it."""
    if core == "scummvm" and not game_config.get("main_file"):
        return _write_scummvm_file(game_config)
    if core == "mame" and game_config.get("machine"):
        return _write_mame_command(game_config)
    path = _get_main_file(game_config)
    if core in _DOSBOX_CORES and game_config.get("config_file"):
        if path.suffix.casefold() == ".conf":
            return _write_dosbox_config(path, game_config)
        logger.warning("The DOSBox core runs %s without the settings in %s", path, game_config["config_file"])
    if core == "cemu" and path.is_dir():
        return str(_find_one(path, "code/*.rpx"))
    if core == "easyrpg" and path.is_dir():
        return str(_find_one(path, "RPG_RT.ldb"))
    if core == "uzdoom" and game_config.get("files"):
        logger.warning("The UZDoom core loads only %s, not the extra files the game lists", path)
    return str(path)


def _get_main_file(game_config: Mapping[str, Any]) -> Path:
    main_file = game_config.get("main_file")
    if not main_file:
        raise GameConfigError(_("No game file specified"))
    path = Path(str(main_file)).expanduser()
    if not path.exists():
        raise MissingGameExecutableError(filename=str(path))
    return path


def _find_one(folder: Path, pattern: str) -> Path:
    """Find the file matching a pattern, ignoring case, in a game folder."""
    matches = sorted(folder.glob(pattern, case_sensitive=False))
    if not matches:
        raise MissingGameExecutableError(filename=str(folder / pattern))
    return matches[0]


def _write_scummvm_file(game_config: Mapping[str, Any]) -> str:
    """The ScummVM core runs the game in the folder of the .scummvm file it loads, which
    names the game's ScummVM ID; without an ID, ScummVM detects the game."""
    folder = Path(str(game_config.get("path") or "")).expanduser()
    if not game_config.get("path") or not folder.is_dir():
        raise MissingGameExecutableError(filename=str(folder))
    game_id = str(game_config.get("game_id") or "").strip()
    target = folder / f"{game_id or 'lutris'}.scummvm"
    _write_if_changed(target, game_id)
    return str(target)


def _write_mame_command(game_config: Mapping[str, Any]) -> str:
    """The MAME core takes a machine and its media from a .cmd file holding a MAME command line."""
    machine = str(game_config["machine"])
    words = [machine]
    if main_file := game_config.get("main_file"):
        path = Path(str(main_file)).expanduser()
        if not path.exists():
            raise MissingGameExecutableError(filename=str(path))
        words += [f"-{game_config.get('device') or 'cart'}", str(path)]
    if slots := game_config.get("slots"):
        words += shlex.split(str(slots))
    if args := game_config.get("args"):
        words += shlex.split(str(args))
    target = GENERATED_CONTENT_DIR / f"{_safe_name(machine, words)}.cmd"
    _write_if_changed(target, shlex.join(words) + "\n")
    return str(target)


def _write_dosbox_config(main_file: Path, game_config: Mapping[str, Any]) -> str:
    """DOSBox cores load one .conf file, so a game's settings file and its launch file
    (GOG ships one each) are merged, next to the folder DOSBox mounts drives from."""
    extra = Path(str(game_config["config_file"])).expanduser()
    if not extra.is_absolute():
        extra = main_file.parent / extra
    if not extra.is_file():
        raise MissingGameExecutableError(filename=str(extra))
    # The launch file mounts drives, so its [autoexec] section has to come last
    folder = Path(str(game_config.get("working_dir") or main_file.parent)).expanduser()
    target = folder / ".lutris-dosbox.conf"
    _write_if_changed(
        target, "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in (extra, main_file))
    )
    return str(target)


def _safe_name(machine: str, words: list[str]) -> str:
    stem = "".join(char if char.isalnum() else "_" for char in machine)
    return f"{stem}-{hashlib.sha256(shlex.join(words).encode()).hexdigest()[:12]}"


def _write_if_changed(target: Path, content: str) -> None:
    try:
        if target.is_file() and target.read_text(encoding="utf-8") == content:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as ex:
        raise GameConfigError(_("Could not write %s: %s") % (target, ex)) from ex
    os.chmod(target, 0o644)
