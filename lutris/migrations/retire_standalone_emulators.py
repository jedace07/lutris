"""Move the games of runners that RetroArch cores replaced to the libretro runner, and the
games of renamed runners to their successors."""

from __future__ import annotations

from pathlib import Path

from lutris import settings
from lutris.database.games import get_games, update_existing
from lutris.util.log import logger
from lutris.util.retroarch.substitutes import is_substituted, translate_game_config, translate_runner
from lutris.util.yaml import read_yaml_from_file, write_yaml_to_file


def migrate_config(runner: str, config: dict) -> dict:
    """Return a game's configuration for the runner that replaced its own."""
    new_runner = translate_runner(runner)
    config = dict(config)
    runner_section = config.pop(runner, None)
    if is_substituted(runner):
        config["game"] = translate_game_config(runner, dict(config.get("game") or {}))
    elif runner_section is not None:
        config[new_runner] = runner_section
    return config


def migrate() -> None:
    """Run migration"""
    for db_game in get_games():
        runner = db_game.get("runner") or ""
        new_runner = translate_runner(runner)
        if new_runner == runner:
            continue
        config_path = Path(settings.CONFIG_DIR) / "games" / f"{db_game.get('configpath')}.yml"
        try:
            if db_game.get("configpath") and config_path.is_file():
                config = read_yaml_from_file(str(config_path)) or {}
                write_yaml_to_file(migrate_config(runner, config), filepath=str(config_path))
            update_existing(id=db_game["id"], runner=new_runner)
        except Exception as ex:  # A broken game config must not stop the others from moving
            logger.error("Failed to move %s from %s to %s: %s", db_game.get("name"), runner, new_runner, ex)
