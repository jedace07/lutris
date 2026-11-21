"""Runners that launch, and install, an emulator's Flathub build."""

import re
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lutris.delegates import InstallUIDelegate
from lutris.runners import RunnerInstallationError
from lutris.runners.eden import eden
from lutris.runners.json import load_json_runners
from lutris.util import flatpak


@pytest.fixture
def host_flatpak(monkeypatch: pytest.MonkeyPatch) -> set[str]:
    """Pretend Flatpak is on the system, with the returned set of apps installed."""
    installed: set[str] = set()
    monkeypatch.setattr(flatpak, "get_executable", lambda: "/usr/bin/flatpak")
    monkeypatch.setattr(flatpak, "is_app_installed", lambda appid: appid in installed)
    return installed


def make_eden(rom: Path) -> eden:
    runner = eden()
    runner._config = MagicMock(game_config={"main_file": str(rom)}, runner_config={}, system_config={})
    runner.has_explicit_config = True
    return runner


def test_flatpak_runner_launches_its_flatpak_with_the_game_folder_shared(
    tmp_path: Path, host_flatpak: set[str]
) -> None:
    host_flatpak.add("dev.eden_emu.eden")
    rom = tmp_path / "games" / "game.nsp"
    rom.parent.mkdir()
    rom.write_bytes(b"")

    command = make_eden(rom).play()["command"]

    assert command[:4] == ["/usr/bin/flatpak", "run", f"--filesystem={rom.parent}:rw", "dev.eden_emu.eden"]
    assert command[-2:] == ["-g", str(rom)]


def test_flatpak_runner_passes_the_game_environment_to_the_app(tmp_path: Path, host_flatpak: set[str]) -> None:
    host_flatpak.add("dev.eden_emu.eden")
    rom = tmp_path / "game.nsp"
    rom.write_bytes(b"")
    runner = make_eden(rom)
    env = {"DRI_PRIME": "1", "VK_ICD_FILENAMES": "/usr/share/vulkan/icd.d/nvidia.json", "LC_ALL": "C"}

    command = runner.prepare_game_command(runner.play()["command"], env)

    app = command.index("dev.eden_emu.eden")
    assert command[app - 2 : app] == ["--env=DRI_PRIME=1", "--env=LC_ALL=C"]
    # Driver paths from outside the app's sandbox would break it
    assert "VK_ICD_FILENAMES" not in env


def test_missing_flatpak_names_the_flathub_app(tmp_path: Path, host_flatpak: set[str]) -> None:
    runner = make_eden(tmp_path / "game.nsp")
    assert not runner.is_installed()
    assert runner.can_install
    with pytest.raises(Exception, match=re.escape("dev.eden_emu.eden")):
        runner.get_command()


def test_install_adds_flathub_for_the_user_and_installs_the_app(
    host_flatpak: set[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    commands: list[list[str]] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if command[1] == "install":
            host_flatpak.add(command[-1])
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)
    callback = MagicMock()
    ruffle = load_json_runners()["ruffle"]()

    ruffle.install(InstallUIDelegate(), callback=callback)

    assert commands[0][:5] == ["/usr/bin/flatpak", "remote-add", "--user", "--if-not-exists", "flathub"]
    assert commands[1] == [
        "/usr/bin/flatpak",
        "install",
        "--user",
        "--noninteractive",
        "-y",
        "flathub",
        "rs.ruffle.Ruffle",
    ]
    assert ruffle.is_installed()
    callback.assert_called_once()


def test_failed_flatpak_install_reports_flatpaks_error(host_flatpak: set[str], monkeypatch: pytest.MonkeyPatch) -> None:
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(1, command, "", "error: No remote refs found")

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(RunnerInstallationError, match="No remote refs found"):
        eden().install(InstallUIDelegate())


def test_flatpak_spawn_reaches_the_hosts_flatpak(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flatpak, "get_executable", lambda: "/usr/bin/flatpak-spawn")
    assert flatpak.get_run_command("org.libretro.RetroArch") == [
        "/usr/bin/flatpak-spawn",
        "--host",
        "flatpak",
        "run",
        "org.libretro.RetroArch",
    ]


def test_system_folders_are_not_shared(tmp_path: Path) -> None:
    game = tmp_path / "game.rom"
    game.write_bytes(b"")
    assert flatpak.get_shareable_paths(["/", "/usr/share", str(game), str(tmp_path), "relative", "/missing"]) == [
        str(tmp_path)
    ]
