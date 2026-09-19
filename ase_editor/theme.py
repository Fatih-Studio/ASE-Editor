from __future__ import annotations

from dataclasses import dataclass

from .sector import SectorColor


VACCC_INDONESIA_PRESET_NAME = "vACC Indonesia"
UK_2026_09_PRESET_NAME = "UK 2026/09"


@dataclass(frozen=True, slots=True)
class ThemePreset:
    name: str
    colors: dict[str, int]


def preset_from_sector_colors(name: str, colors: dict[str, SectorColor]) -> ThemePreset:
    return ThemePreset(name, {color_name: color.value for color_name, color in colors.items()})


# UK_2026_09.sct uses UK-specific names such as coast, smrTaxiway, and NXsidlines.
# This preset maps those analyzed values onto the current Indonesia COLOR_* names.
UK_2026_09_INDONESIA_THEME = ThemePreset(
    UK_2026_09_PRESET_NAME,
    {
        "COLOR_APP": 15790135,
        "COLOR_AirspaceA": 11206655,
        "COLOR_AirspaceB": 7484470,
        "COLOR_AirspaceC": 6249039,
        "COLOR_AirspaceD": 7884373,
        "COLOR_AirspaceE": 5787205,
        "COLOR_AirspaceF": 4915200,
        "COLOR_AirspaceG": 3947580,
        "COLOR_ApronSurface": 5197647,
        "COLOR_Building": 10534048,
        "COLOR_Coastline": 9076039,
        "COLOR_DangerArea": 2894694,
        "COLOR_FIRBorder": 5787205,
        "COLOR_GrasSurface": 24576,
        "COLOR_HardSurface1": 13491405,
        "COLOR_HardSurface2": 5272144,
        "COLOR_HelipadSurface": 5329233,
        "COLOR_Holding": 65535,
        "COLOR_Labels": 13421772,
        "COLOR_Landmark": 3947580,
        "COLOR_ParkPos": 16777215,
        "COLOR_ProhibitedArea": 255,
        "COLOR_RestrictedArea": 2894694,
        "COLOR_RunwayBorder": 13421772,
        "COLOR_RunwayGrass": 24576,
        "COLOR_SID": 255,
        "COLOR_STAR": 16759671,
        "COLOR_TACAN-Route": 5787205,
        "COLOR_TMA": 7884373,
        "COLOR_TMZ": 43775,
        "COLOR_TWR-CTR": 5787205,
        "COLOR_Taxiway": 5272144,
        "COLOR_TaxiwayBorder": 6589540,
        "COLOR_Stands": 16777215,
        "COLOR_Terrain1": 3947580,
        "COLOR_Terrain2": 7058795,
        "COLOR_Terrain3": 6919785,
        "COLOR_Terrain4": 4551749,
        "COLOR_Terrain5": 3689771,
        "COLOR_Terrain6": 3051799,
        "COLOR_Terrain7": 29440,
        "COLOR_Terrain8": 24576,
        "COLOR_Terrain9": 18944,
        "COLOR_UpperSector": 11206655,
        "COLOR_VFR-Route": 5787205,
        "COLOR_Vectors": 15790135,
        "COLOR_Water": 9204580,
    },
)
