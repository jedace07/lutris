import io
import os
import tarfile
from pathlib import Path
from zipfile import ZipFile

import pytest

from lutris import settings
from lutris.delegates import InstallUIDelegate
from lutris.runners import NonInstallableRunnerError
from lutris.runners.libretro import libretro
from lutris.runners.runner import Runner
from lutris.util import flatpak
from lutris.util.retroarch import locations


def test_download_and_extract_publishes_the_archive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path / "cache"))
    destination = tmp_path / "runner"

    def download(url: str, destination: str) -> bool:
        with tarfile.open(destination, "w:gz") as archive:
            for name in ("wrapper/runner", "wrapper/assets/data.bin"):
                data = b"fixture"
                info = tarfile.TarInfo(name)
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
        return True

    delegate = InstallUIDelegate()
    delegate.download_install_file = download
    Runner().download_and_extract("https://example.invalid/runner.tar.gz", delegate, str(destination), "runner")
    assert os.access(destination / "runner", os.X_OK)
    assert (destination / "assets" / "data.bin").read_bytes() == b"fixture"
    assert not list((tmp_path / "cache").iterdir())


def test_libretro_installs_cores_where_the_retroarch_flatpak_loads_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cores go into the RetroArch Flatpak's own cores directory, as its updater puts them."""
    monkeypatch.setattr(settings, "CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(locations, "get_app_dir", lambda appid: tmp_path / ".var" / "app" / appid)
    monkeypatch.setattr(flatpak, "is_app_installed", lambda appid: appid == "org.libretro.RetroArch")
    urls: list[str] = []

    def download(url: str, destination: str) -> bool:
        urls.append(url)
        with ZipFile(destination, "w") as archive:
            archive.writestr("mgba_libretro.so", b"core")
        return True

    delegate = InstallUIDelegate()
    delegate.download_install_file = download
    runner = libretro()
    assert runner.is_installed()
    assert not runner.is_installed(core="mgba")

    runner.install(delegate, version="mgba")

    core = tmp_path / ".var/app/org.libretro.RetroArch/config/retroarch/cores/mgba_libretro.so"
    assert core.read_bytes() == b"core"
    assert urls[0].endswith("/latest/mgba_libretro.so.zip")
    assert runner.is_installed(core="mgba")


def test_runners_without_a_flatpak_cannot_be_installed() -> None:
    runner = Runner()
    runner.system_executable = "an-emulator"
    assert not runner.can_install
    with pytest.raises(NonInstallableRunnerError):
        runner.install(InstallUIDelegate())
