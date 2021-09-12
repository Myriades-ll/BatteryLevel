#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""Domoticz images"""

# standard libs
from typing import Any, Iterator, Mapping, Optional

# Domoticz lib
import Domoticz


class Images(Mapping[str, Any]):
    """Collection des images"""
    images: Mapping[str, Domoticz.Image] = {}
    _icons_files = {
        "pyBattLev": "pyBattLev icons.zip",
        "pyBattLev_ok": "pyBattLev_ok icons.zip",
        "pyBattLev_low": "pyBattLev_low icons.zip",
        "pyBattLev_empty": "pyBattLev_empty icons.zip",
        "pyBattLev_ko": "pyBattLev_ko icons.zip"
    }
    _init_done = False

    def __new__(cls, images: Optional[Mapping[str, Domoticz.Image]] = None) -> object:
        """Initialisation de la classe"""
        if not cls._init_done or isinstance(images, dict):
            cls.images = images
            # populate image list
            for key, value in cls._icons_files.items():
                if key not in cls.images:
                    Domoticz.Image(value).Create()
            cls._init_done = True
        return super(Images, cls).__new__(cls)

    @classmethod
    def __getitem__(cls, key: str) -> int:
        """Wrapper pour Images['']"""
        if key in cls.images:
            return cls.images[key].ID
        raise KeyError('Image index non trouvé: {}'.format(key))

    @classmethod
    def __len__(cls) -> int:
        return len(cls.images)

    @classmethod
    def __iter__(cls) -> Iterator[Domoticz.Image]:
        for image in cls.images.values():
            yield image

    @classmethod
    def __str__(cls) -> str:
        """Wrapper pour str()"""

    @classmethod
    def __repr__(cls) -> str:
        """Wrapper pour repr()"""
