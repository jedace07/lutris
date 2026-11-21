"""The configuration Lutris gives an imported ROM, for each platform it recognizes."""


def _core(core: str, **options: str) -> dict[str, object]:
    return {"runner": "libretro", "game": {"core": core, "main_file": "rom", **options}}


DEFAULT_INSTALLERS = {
    "3do": _core("opera"),
    "sms": _core("genesis_plus_gx"),
    "gg": _core("genesis_plus_gx"),
    "md": _core("genesis_plus_gx"),
    "pico": _core("picodrive"),
    "segacd": _core("picodrive"),
    "saturn": _core("yabause"),
    "dc": _core("flycast"),
    "colecovision": _core("gearcoleco"),
    "atari800": _core("atari800"),
    "atari2600": _core("stella"),
    "lynx": _core("handy"),
    "atari-st": _core("hatarib"),
    "jaguar": _core("virtualjaguar"),
    "amiga": _core("puae"),
    "amiga-1200": _core("puae"),
    "amiga-cd32": _core("puae"),
    "ds": _core("melondsds"),
    "gb": _core("gambatte"),
    "gba": _core("vba_next"),
    "nes": _core("mesen"),
    "snes": _core("snes9x"),
    "n64": _core("mupen64plus_next"),
    "gamecube": _core("dolphin"),
    "wii": _core("dolphin"),
    "switch": {"runner": "ryubing", "game": {"main_file": "rom"}},
    "ps1": _core("mednafen_psx_hw"),
    "ps2": _core("pcsx2"),
    "ps3": _core("rpcs3"),
    "psp": _core("ppsspp"),
    "cdi": _core("same_cdi"),
    "msx": _core("bluemsx"),
    # MAME runs machines without a core of their own from a command line Lutris writes
    "archimedes": _core("mame", machine="aa4000", device="flop1"),
    "bbc": _core("b2"),
    "electron": _core("mame", machine="electron", device="flop1"),
    "astrocade": _core("mame", machine="astrocde", device="cart"),
    "wonderswancolor": _core("mednafen_wswan"),
    "wonderswan": _core("mednafen_wswan"),
    "cpc6128disk": _core("cap32"),
    "gx4000": _core("cap32"),
    "apple2": _core("applewin"),
    "spectrumcass": _core("fuse"),
    "c64prg": _core("vice_x64"),
    "c64g64": _core("vice_x64"),
}
