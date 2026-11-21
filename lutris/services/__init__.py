"""Service package"""

from typing import TYPE_CHECKING

from lutris import settings
from lutris.services.amazon import AmazonService
from lutris.services.battlenet import BattleNetService
from lutris.services.dlsite import DlsiteService
from lutris.services.ea_app import EAAppService
from lutris.services.egs import EpicGamesStoreService
from lutris.services.gamejolt import GameJoltService
from lutris.services.gog import GOGService
from lutris.services.humblebundle import HumbleBundleService
from lutris.services.itchio import ItchIoService
from lutris.services.steam import SteamService
from lutris.services.ubisoft import UbisoftConnectService
from lutris.services.xdg import XDGService
from lutris.services.zoom import ZoomService
from lutris.util.linux import LINUX_SYSTEM

if TYPE_CHECKING:
    from lutris.services.base import BaseService

DEFAULT_SERVICES = ["gog", "egs", "ea_app", "ubisoft", "steam"]


def get_services() -> dict[str, "type[BaseService]"]:
    """Return a mapping of available services"""
    _services = {
        "gog": GOGService,
        "zoomplatform": ZoomService,
        "humblebundle": HumbleBundleService,
        "egs": EpicGamesStoreService,
        "gamejolt": GameJoltService,
        "itchio": ItchIoService,
        "ea_app": EAAppService,
        "ubisoft": UbisoftConnectService,
        "amazon": AmazonService,
        "dlsite": DlsiteService,
    }
    _services["battlenet"] = BattleNetService
    if not LINUX_SYSTEM.is_flatpak():
        _services["xdg"] = XDGService
    if LINUX_SYSTEM.has_steam():
        _services["steam"] = SteamService
    return _services


SERVICES = get_services()


def get_enabled_services():
    return {
        key: _class
        for key, _class in SERVICES.items()
        if settings.read_setting(key, section="services").lower() == "true"
    }
