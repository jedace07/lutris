"""Run the shadPS4 SDL emulator."""

from gettext import gettext as _
from pathlib import Path

from lutris.exceptions import MissingGameExecutableError
from lutris.runners.runner import GamePlayInfoDict, Runner


class shadps4(Runner):
    human_name = _("shadPS4")
    description = _("PlayStation 4 emulator")
    platform_dict = Runner.to_platform_dict([_("Sony PlayStation 4")])
    runnable_alone = True
    flatpak_id = "net.shadps4.shadPS4"

    game_options = [
        {
            "option": "main_file",
            "type": "directory",
            "label": _("Game folder"),
            "help": _("Path to the game folder containing eboot.bin"),
        }
    ]
    runner_options = [
        {
            "option": "fullscreen",
            "type": "bool",
            "label": _("Fullscreen"),
            "default": True,
        }
    ]

    def play(self) -> GamePlayInfoDict:
        executable = Path(self.game_config.get("main_file") or "").expanduser() / "eboot.bin"
        if not executable.is_file():
            raise MissingGameExecutableError(filename=str(executable))
        fullscreen = "true" if self.runner_config.get("fullscreen") else "false"
        return {"command": [*self.get_command(), "--game", str(executable), "--fullscreen", fullscreen]}
