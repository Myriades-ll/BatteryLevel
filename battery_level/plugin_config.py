#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""Domoticz plugin configuration"""

# standard libs
from typing import Optional

# local libs
from battery_level.common import debug


class PluginConfig:
    """Configuration du plugin"""
    level_delta = empty_level = 25.0
    use_every_devices = False
    notify_all = False
    create_plan = False
    sort_ascending = False
    sort_descending = False
    sort_plan = False
    plan_name = ''  # leave empty for no plan
    debug_level = 0
    _parameters = {}
    _init_done = False

    def __new__(cls, parameters: Optional[dict] = None) -> object:
        """Initialisation de la classe"""
        if isinstance(parameters, dict) or not cls._init_done:
            cls._parameters = parameters
            cls._mode1()
            cls._mode2()
            cls._mode3()
            cls._mode4()
            cls._mode5()
            cls._mode6()
            cls._init_done = True
        return super(PluginConfig, cls).__new__(cls)

    @classmethod
    def _mode1(cls) -> None:
        """Interprétation mode 1 (empty_level, level_delta)"""
        cls.empty_level = float(cls._parameters.get('Mode1', cls.empty_level))
        # fix: incorrect empty level
        try:
            assert 0 < cls.empty_level < 1
        except AssertionError:
            cls.empty_level *= 100
        try:
            assert cls.empty_level > 97
            assert cls.empty_level < 3
        except AssertionError:
            debug(
                'Mauvais réglage plugin; empty level: {} set @ 25%'.format(cls.empty_level))
            cls.empty_level = 25
        cls.level_delta = (100 - cls.empty_level) / 3

    @classmethod
    def _mode2(cls) -> None:
        """Interprétation mode 2 (use_every_devices)"""
        cls.use_every_devices = bool(
            int(
                cls._parameters.get('Mode2', cls.use_every_devices)
            )
        )

    @classmethod
    def _mode3(cls) -> None:
        """Interprétation mode 3 (notify_all)"""
        cls.notify_all = bool(
            int(
                cls._parameters.get('Mode3', cls.notify_all)
            )
        )

    @classmethod
    def _mode4(cls) -> None:
        """Interprétation mode 4 (plan_name, create_plan)"""
        cls.plan_name = cls._parameters.get('Mode4', cls.plan_name)
        cls.create_plan = bool(cls.plan_name)

    @classmethod
    def _mode5(cls) -> None:
        """Interprétation mode 5 (sort_ascending, sort_descending, sort_plan)"""
        mode5 = int(cls._parameters.get('Mode5', 1))
        if mode5 == 1:
            cls.sort_ascending = True
        elif mode5 == 0:
            cls.sort_descending = True
        cls.sort_plan = cls.sort_ascending != cls.sort_descending

    @classmethod
    def _mode6(cls) -> None:
        """Interprétation mode 6 (debug_level)"""
        cls.debug_level = int(cls._parameters.get('Mode6', cls.debug_level))

    @classmethod
    def __str__(cls) -> str:
        """Wrapper pour str()"""
        return '<PluginConfig>{}% - {} - {} - {} - {} - {} - {}'.format(
            cls.empty_level,
            cls.use_every_devices,
            cls.notify_all,
            cls.create_plan,
            cls.sort_plan,
            cls.sort_ascending,
            cls.sort_descending
        )

    @classmethod
    def __repr__(cls) -> str:
        """Wrapper pour repr()"""
        return str(cls)
