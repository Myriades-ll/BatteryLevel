#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""Gestion du plan"""

# standards libs
from operator import attrgetter
from typing import List, Mapping

# Domoticz lib
import Domoticz

# local libs
from battery_level.common import debug
from battery_level.devices import Devices
from battery_level.plugin_config import PluginConfig
from battery_level.requests import Requests


class _OrderedListItem:
    """Elément de la liste ordonnée"""

    def __init__(self: object, devidx: int, name: str, bat_lev: int) -> None:
        """Initialisation de la classe"""
        self.devidx = devidx
        self.name = name
        self.bat_lev = bat_lev

    def __str__(self: object) -> str:
        """Wrapper pour str()"""
        return '({}){}: {}%'.format(
            self.devidx,
            self.name,
            self.bat_lev
        )

    def __repr__(self: object) -> str:
        """Wrapper pour repr()"""
        return str(self)


class _OrderedDevices:
    """Collection ordonnée des devices"""
    ordered_list: List[_OrderedListItem] = []
    _device_dict: Mapping[int, _OrderedListItem] = {}

    def __new__(cls: object) -> object:
        """Initialisation de la classe"""
        cls.init_devices()
        return super(_OrderedDevices, cls).__new__(cls)

    @classmethod
    def init_devices(cls: object) -> None:
        """Remplissage des listes"""
        for device in Devices():
            cls._update(device.ID, device.Name, float(device.sValue))
        cls._sort()

    @classmethod
    def values(cls: object) -> List[_OrderedListItem]:
        """Wrapper pour for ... in ... loop"""
        return cls.ordered_list

    @classmethod
    def _update(cls: object, devidx: int, name: str, bat_lev: int, sort: bool = False) -> None:
        """Ajoute un device"""
        # mise à jour du dictionnaire des devices
        cls._device_dict.update({
            devidx: _OrderedListItem(devidx, name, bat_lev)
        })
        if sort:
            cls._sort()

    @classmethod
    def _sort(cls: object) -> None:
        """Tri des données

        tri par niveau de batterie puis nom
        """
        reverse = False
        if PluginConfig.sort_descending:
            reverse = True
        cls.ordered_list = sorted(
            cls._device_dict.values(),
            key=attrgetter('bat_lev', 'name'),
            reverse=reverse
        )

    @classmethod
    def __getitem__(cls: object, key: int) -> _OrderedListItem:
        """Retourne le device à l'index 'key'"""
        return cls.ordered_list[key]

    @classmethod
    def __repr__(cls: object) -> str:
        """Wrapper pour repr()"""
        return str(cls)

    @classmethod
    def __str__(cls: object) -> str:
        """Wrapper pour str()"""
        return "Ordered list: {}".format(cls.ordered_list)


class Plans:
    """Gestion des emplacements"""
    INIT_PLANS = 0x0
    GET_PLANS = 0x1
    ADD_PLAN = 0x2
    GET_PLAN_DEVICES = 0x4
    MOVE_PLAN_DEVICE = 0x8
    _plan_devices_set = set()
    urls = {
        "plans": "/json.htm?type=plans",
        "getplandevices": "/json.htm?idx={}&param=getplandevices&type=command",
        "addplanactivedevice": [
            "/json.htm?",
            "activeidx={}&",  # device_id
            "activetype=0&",
            "idx={}&",  # plan_id
            "param=addplanactivedevice&type=command"
        ],
        "addplan": "/json.htm?name={}&param=addplan&type=command",
        'changeplandeviceorder': [
            '/json.htm?',
            'idx={}',  # device_idx
            '&param=changeplandeviceorder&',
            'planid={}',  # plan_id
            '&type=command&way={}'  # move up/down
        ]
    }
    _plan_id = 0
    _widget_sort_progress = False
    _status = INIT_PLANS
    _init_done = False

    def __new__(cls: object) -> object:
        """Initialisation de la classe"""
        if not cls._init_done:
            _OrderedDevices()
            cls._init_plan()
            cls._init_done = True
        return super(Plans, cls).__new__(cls)

    @classmethod
    def _init_plan(cls: object) -> None:
        """Initialisation du plan des devices"""
        if 'plan_id' in Domoticz.Configuration():
            cls._plan_id = int(Domoticz.Configuration()['plan_id'])
            cls._status |= cls.GET_PLANS | cls.ADD_PLAN
            Domoticz.Status('Battery plan id acquired')
        # launch plan creation
        if cls._plan_id == 0 and cls._status == cls.INIT_PLANS:
            cls._status |= cls.GET_PLANS
            Requests.add("GET", cls.urls.get("plans"))

    @classmethod
    def update(cls: object, force: bool = False) -> None:
        """Appel de mise à jour

        Args:

                - force (bool): si True force la mise à jour
        """
        if not cls._status & cls.GET_PLAN_DEVICES or force:
            cls._status |= cls.GET_PLAN_DEVICES
            Requests.add(
                'GET', cls.urls['getplandevices'].format(cls._plan_id)
            )

    @classmethod
    def check_plans(cls: object, datas: List[Mapping[str, str]]) -> None:
        """vérifie l'existence du plans dans la liste des plans, si non création"""
        # Vérifier l'existence du plan
        for value in datas:
            if value.get('Name') == PluginConfig.plan_name:
                cls._status |= cls.ADD_PLAN
                cls._plan_id = value.get('idx')
                Domoticz.Configuration({'plan_id': cls._plan_id})
                Domoticz.Status('Battery plan id acquired')
                cls.update()
                return
        # Création du 'plan'
        # /json.htm?name=&param=addplan&type=command
        if not cls._status & cls.ADD_PLAN:
            cls._status |= cls.ADD_PLAN
            Requests.add(
                'GET',
                cls.urls['addplan'].format(PluginConfig.plan_name)
            )

    @classmethod
    def check_plans_devices(cls: object, datas: list) -> None:
        """Reçoit la liste des devices dans le plan"""
        has_to_be_updated = False
        # enregistrement local du plan des devices
        for data in datas:
            cls._plan_devices_set.add(int(data['devidx']))
        # Vérification présence device dans le plan
        for device in Devices():
            devidx = device.ID
            if devidx not in cls._plan_devices_set:
                has_to_be_updated = True
                # /json.htm?activeidx=211&activetype=0&idx=13&param=addplanactivedevice&type=command
                Requests.add(
                    'GET',
                    (''.join(cls.urls['addplanactivedevice'])).format(
                        devidx,
                        cls._plan_id
                    )
                )
        # si besoin, lancement d'une vérification du plan
        if has_to_be_updated:
            cls.update(True)
        # sinon on commence le tri
        elif PluginConfig.sort_plan:
            if not cls._status & cls.MOVE_PLAN_DEVICE:
                _OrderedDevices.init_devices()
                debug('Ordered list', *_OrderedDevices.ordered_list)
            cls._order_plan_devices(datas)

    @classmethod
    def _order_plan_devices(cls: object, datas: List[Mapping[str, str]]) -> None:
        """Tri des devices dans le plan"""
        def move_down(down: bool, plan_device: Mapping[str, str]) -> None:
            """bouge l'emplacement du device dans la plan"""
            # vers le haut: way = 0
            # /json.htm?idx=117&param=changeplandeviceorder&planid=13&type=command&way=0
            # vers le bas: way = 1
            # /json.htm?idx=117&param=changeplandeviceorder&planid=13&type=command&way=1
            if not cls._status & cls.MOVE_PLAN_DEVICE:
                cls._status |= cls.MOVE_PLAN_DEVICE
                Domoticz.Status('Début de tri des widgets')
                Domoticz.Heartbeat(1)
            way = 1 if down else 0
            Requests.add(
                'GET',
                ''.join(cls.urls['changeplandeviceorder']).format(
                    plan_device['idx'],
                    cls._plan_id,
                    way
                )
            )
            cls.update(True)

        order_index = 0
        for item in _OrderedDevices.values():
            plan_index = 0
            for plan_device in datas:
                if item.devidx == int(plan_device['devidx']):
                    if order_index > plan_index:
                        move_down(True, plan_device)
                        return
                    if order_index < plan_index:
                        move_down(False, plan_device)
                        return
                plan_index += 1
            order_index += 1
        if cls._status & cls.MOVE_PLAN_DEVICE:
            cls._status ^= cls.MOVE_PLAN_DEVICE
            Domoticz.Heartbeat(10)
            Domoticz.Status('Tri des widgets terminé')
        # on autorise de nouveau la mise à jour cyclique
        cls._status ^= cls.GET_PLAN_DEVICES

    @classmethod
    def __str__(cls: object) -> str:
        """Wrapper pour str()"""
        return 'Plan ID: {} - Status: {}'.format(
            cls._plan_id,
            cls._status
        )

    @classmethod
    def __repr__(cls: object) -> str:
        """Wrapper pour repr()"""
        return str(cls)
