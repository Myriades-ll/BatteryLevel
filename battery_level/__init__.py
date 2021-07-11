#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# pylint: disable=no-member
"""Wrapper pour le plugin"""

__all__ = ['Wrapper']

# standards libs
import json
from collections import namedtuple
from datetime import datetime, timedelta
from inspect import stack
from operator import attrgetter, itemgetter
from queue import Queue
from statistics import mean
from time import strptime, time
from typing import Iterable, List, Mapping, Optional, Tuple, Union
from urllib.parse import quote_plus

# Domoticz lib
import Domoticz


def debug(*args):
    """Extended debug"""
    func_list = []
    stack_ = stack()
    for frame in stack_:
        func_list.append(frame.function)
    func_list.pop(0)
    func_list.pop()
    func_list.reverse()
    Domoticz.Debug('Caller: {}'.format('.'.join(func_list)))
    for arg in args:
        Domoticz.Debug('{}'.format(arg))


def last_update_2_datetime(last_update: str) -> datetime:
    """conversion de la valeur last_update de domoticz en datetime"""
    if isinstance(last_update, type(None)):
        return datetime.now()
    if isinstance(last_update, datetime):
        return last_update
    dz_format = r'%Y-%m-%d %H:%M:%S'
    try:  # python > 3.7
        last_update_dt = datetime.strptime(
            last_update,
            dz_format
        )
    except TypeError:  # python < 3.8
        try:
            last_update_dt = datetime(
                *(strptime(last_update, dz_format)[0:6])
            )
        except AttributeError:
            Domoticz.Error("datetime.strptime('{}', '{}')".format(
                last_update,
                dz_format
            ))
            Domoticz.Error("time.strptime('{}', '{}')".format(
                last_update,
                dz_format
            ))
            last_update_dt = datetime.now()
    return last_update_dt


class _Images():
    """Collection des images"""
    _images: Mapping[str, Domoticz.Image] = {}
    _icons_files = {
        "pyBattLev": "pyBattLev icons.zip",
        "pyBattLev_ok": "pyBattLev_ok icons.zip",
        "pyBattLev_low": "pyBattLev_low icons.zip",
        "pyBattLev_empty": "pyBattLev_empty icons.zip",
        "pyBattLev_ko": "pyBattLev_ko icons.zip"
    }

    def __init__(self: object, images: Mapping[str, Domoticz.Image]) -> None:
        """Initialisation de la classe"""
        self._images = images
        # populate image list
        for key, value in self._icons_files.items():
            if key not in self._images:
                Domoticz.Image(value).Create()

    def __str__(self: object) -> str:
        """Wrapper pour str()"""

    def __repr__(self: object) -> str:
        """Wrapper pour repr()"""


class _Bounces():
    """Gestion des rebonds des valeurs"""
    _BOUNCEMODES = namedtuple(
        'Modes', ['DISABLED', 'SYSTEMATIC', 'POND_1H', 'POND_1D'])
    _MINMAX = namedtuple('minmax', ['MIN', 'MAX', 'MIN_RESET', 'MAX_RESET'])

    def __init__(
            self: object,
            mode: int,
            mini: Union[str, int, float] = 0,
            maxi: Union[str, int, float] = 100,
            reset: Union[int, float] = 80) -> None:
        """Initialisation de la classe"""
        assert 0 < reset <= 100
        self._modes = self._BOUNCEMODES(0, 1, 2, 4)
        self._bounce_mode = mode
        if 0 < reset <= 1:
            reset *= 100
        self._min_max = self._MINMAX(mini, maxi, reset, 100 - reset)
        self._datas = []
        self.last_value_out = 100.0
        self.last_value_in = 100.0

    def _update(self: object, new_data: Union[str, int, float]) -> float:
        """Mise à jour des données"""
        try:
            assert type(new_data) in [str, int, float]
        except AssertionError:
            return self.last_value_out
        self.last_value_in = float(new_data)
        # reset system
        if (
                self.last_value_in >= self._min_max.MAX_RESET
                and self.last_value_out <= self._min_max.MIN_RESET
        ):
            self._datas.clear()
            self.last_value_out = self.last_value_in
        # return as is
        if self._bounce_mode == self._modes.DISABLED:
            self.last_value_out = self.last_value_in
        # no bounce; always remembering the lowest value
        elif self._bounce_mode & self._modes.SYSTEMATIC:
            if self.last_value_in < self.last_value_out:
                self.last_value_out = self.last_value_in
        else:
            self._datas.append(self.last_value_in)
            # default
            pond = 12
            # 1 hour weighted bounce (last 12 values; 1h/5mn)
            if self._bounce_mode & self._modes.POND_1H:
                pond = 12
            # 1 day weighted bounce (last 288 values; 24h/5mn)
            elif self._bounce_mode & self._modes.POND_1D:
                pond = 288
            while len(self._datas) > pond:
                self._datas.pop(0)
            self.last_value_out = mean(self._datas)
        return self.last_value_out

    def __str__(self: object) -> str:
        """Wrapper pour str()"""
        return '{} {}'.format(self._modes, self._bounce_mode)

    def __repr__(self: object) -> str:
        """Wrapper pour repr()"""
        return str(self)

    def __float__(self: object) -> float:
        """Wrapper pour float()"""
        return self.last_value_out

    def __int__(self: object) -> int:
        """Wrapper pour int()"""
        return int(self.last_value_out)


class _PluginConfig():
    """Configuration du plugin"""
    level_delta = empty_level = 25
    use_every_devices = False
    notify_all = False
    create_plan = False
    sort_ascending = False
    sort_descending = False
    sort_plan = False
    plan_name = ''
    debug_level = 0
    _init_done = False

    @classmethod
    def __init__(cls: object, parameters: dict = None) -> None:
        """Initialisation de la classe"""
        if not isinstance(parameters, dict) or cls._init_done:
            return
        cls.empty_level = int(parameters.get('Mode1', 25))
        # fix: incorrect empty level
        try:
            assert 3 <= cls.empty_level <= 97
        except AssertionError:
            debug(
                'Mauvais réglage plugin; empty level: {} set @ 25%'.format(cls.empty_level))
            cls.empty_level = 25
        cls.level_delta = (100 - cls.empty_level) / 3
        cls.use_every_devices = bool(int(parameters.get('Mode2', True)))
        cls.notify_all = bool(int(parameters.get('Mode3', True)))
        cls.plan_name = str(parameters.get('Mode4', 'Batteries'))
        cls.create_plan = bool(cls.plan_name)
        mode5 = int(parameters.get('Mode5', 1))
        if mode5 == 1:
            cls.sort_ascending = True
        elif mode5 == 0:
            cls.sort_descending = True
        cls.sort_plan = cls.sort_ascending != cls.sort_descending
        cls.debug_level = int(parameters.get('Mode6', 0))
        cls._init_done = True

    @classmethod
    def __str__(cls: object) -> str:
        """Wrapper pour str()"""
        return '{}% - {} - {} - {} - {} - {} - {}'.format(
            cls.empty_level,
            cls.use_every_devices,
            cls.notify_all,
            cls.create_plan,
            cls.sort_plan,
            cls.sort_ascending,
            cls.sort_descending
        )

    @classmethod
    def __repr__(cls: object) -> str:
        """Wrapper pour repr()"""
        return str(cls)


class _OrderedListItem():
    """Elément de la liste ordonnée"""

    def __init__(self: object, devidx: int, name: str, bat_lev: int) -> None:
        """Initialisation de la classe"""
        self.devidx = devidx
        self.name = name
        self.bat_lev = bat_lev

    def __str__(self: object) -> str:
        """Wrapper pour str()"""
        return '{}({}): {}%'.format(
            self.name,
            self.devidx,
            self.bat_lev
        )

    def __repr__(self: object) -> str:
        """Wrapper pour repr()"""
        return str(self)


class _OrderedDevices(_PluginConfig):
    """Collection ordonnée des devices"""
    _ordered_list: Iterable[_OrderedListItem] = []
    _device_dict: Mapping[int, _OrderedListItem] = {}
    _devices: Mapping[str, Domoticz.Device] = None
    is_updated = False

    @classmethod
    def __init__(cls: object, devices: Mapping[str, Domoticz.Device]) -> None:
        """Initialisation de la classe"""
        _PluginConfig.__init__()
        cls._devices = devices
        cls._init_devices()

    @classmethod
    def _init_devices(cls: object) -> None:
        """Remplissage des listes"""
        for device in cls._devices.values():
            cls.update(device.ID, device.Name, device.nValue)
        cls._sort()

    @classmethod
    def update(cls: object, devidx: int, name: str, bat_lev: int, sort: bool = False) -> None:
        """Ajoute un device"""
        cls.is_updated = True
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
        if cls.sort_descending:
            reverse = True
        cls._ordered_list = sorted(
            cls._device_dict.values(),
            key=attrgetter('bat_lev', 'name'),
            reverse=reverse
        )

    @classmethod
    def __getitem__(cls: object, key: int) -> _OrderedListItem:
        """Retourne le device à l'index 'key'"""
        return cls._ordered_list[key]

    @classmethod
    def __next__(cls: object) -> _OrderedListItem:
        """Wrapper pour for ... in ... loop"""
        for item in cls._ordered_list:
            yield item
        cls.is_updated = False

    @classmethod
    def __repr__(cls: object) -> str:
        """Wrapper pour repr()"""
        return str(cls)

    @classmethod
    def __str__(cls: object) -> str:
        """Wrapper pour str()"""
        return "Ordered list: {}".format(cls._ordered_list)


class _Requests():
    """Queue FIFO des requètes JSON API"""
    _queue = Queue()
    _queue_length = 0
    _last_in_datas = {}
    _last_out_datas = {}

    @classmethod
    def add(cls: object, verb: str, url: str) -> None:
        """Ajoute un élément à la queue"""
        debug('Ajout: {} - {}'.format(verb, url))
        cls._last_in_datas = {
            "Verb": verb,
            "URL": url
        }
        cls._queue.put(cls._last_in_datas)
        cls._queue_length += 1

    @classmethod
    def get(cls: object) -> dict:
        """Renvoie le premier élément inséré dans la queue"""
        cls._last_out_datas = cls._queue.get()
        cls._queue_length -= 1
        debug('Sortie: {}'.format(cls._last_out_datas))
        return cls._last_out_datas

    @classmethod
    def last_in(cls: object) -> Optional[dict]:
        """Renvoie le dernier élément inséré"""
        return cls._last_in_datas

    @classmethod
    def last_out(cls: object) -> Optional[dict]:
        """Renvoie le dernier élément sorti"""
        return cls._last_out_datas

    @classmethod
    def __bool__(cls: object) -> bool:
        """[return]: False if empty, else True"""
        return bool(cls._queue_length)

    @classmethod
    def __len__(cls: object) -> bool:
        """[return]: size of queue"""
        return cls._queue_length

    @classmethod
    def __repr__(cls: object) -> str:
        """Wrapper pour repr()"""
        return str(cls)

    @classmethod
    def __str__(cls: object) -> str:
        """Wrapper pour str()"""
        return '{} in requests queue'.format(cls._queue_length)


class _Plans(_PluginConfig):
    """Gestion des emplacments"""
    INIT_PLANS = 0x0
    GET_PLANS = 0x1
    ADD_PLAN = 0x2
    GET_PLAN_DEVICES = 0x4
    MOVE_PLAN_DEVICE = 0x8
    _requests: _Requests = None
    _devices: Mapping[str, Domoticz.Device] = None
    _plan_devices_set = set()
    _urls = {
        "plans": "/json.htm?type=plans",
        "getplandevices": "/json.htm?idx={}&param=getplandevices&type=command",
        "addplanactivedevice": [
            "/json.htm?",
            "activeidx={}&",  # device_id
            "activetype=0&",
            "idx={}&",  # plan_id
            "param=addplanactivedevice&type=command"
        ],
        "addplan": "/json.htm?name={}&param=addplan&type=command"
    }
    _plan_id = 0
    _widget_sort_progress = False
    _status = INIT_PLANS

    def __init__(self: object, devices: Mapping[str, Domoticz.Device]) -> None:
        """Initialisation de la classe"""
        _PluginConfig.__init__()
        self._requests = _Requests()
        self._devices = devices
        self._ordered_devices = _OrderedDevices(devices)
        self._init_plan()

    def _init_plan(self: object) -> None:
        """Initialisation du plan des devices"""
        if 'plan_id' in Domoticz.Configuration():
            self._plan_id = int(Domoticz.Configuration()['plan_id'])
            self._status |= self.GET_PLANS & self.ADD_PLAN
            Domoticz.Status('Battery plan id acquired')
        # launch plan creation
        if self._plan_id == 0 and self._status == self.INIT_PLANS:
            self._status |= self.GET_PLANS
            self._requests.add("GET", self._urls.get("plans"))

    def update(self: object) -> None:
        """Appel de mise à jour"""
        if not self._status & self.GET_PLAN_DEVICES:
            self._status |= self.GET_PLAN_DEVICES
            self._requests.add(
                'GET', self._urls['getplandevices'].format(self._plan_id)
            )

    def check_plans(self: object, datas: Iterable[dict]) -> None:
        """vérifie la liste des plans la liste des plans"""
        # Vérifier l'existence du plan
        for value in datas:
            if value.get('Name') == self.plan_name:
                self._status |= self.ADD_PLAN
                self._plan_id = value.get('idx')
                Domoticz.Configuration({'plan_id': self._plan_id})
                Domoticz.Status('Battery plan id acquired')
                self.update()
                return
        # Création du 'plan'
        # /json.htm?name=&param=addplan&type=command
        if not self._status & self.ADD_PLAN:
            self._status |= self.ADD_PLAN
            self._requests.add(
                'GET',
                self._urls['addplan'].format(self.plan_name)
            )

    def check_plans_devices(self: object, datas: list) -> None:
        """Reçoit la liste des devices dans le plan"""
        has_to_be_updated = False
        # enregistrement local du plan des devices
        for data in datas:
            self._plan_devices_set.add(int(data['devidx']))
        # Vérification présence device dans le plan
        for device in self._devices.values():
            devidx = device.ID
            if devidx not in self._plan_devices_set:
                has_to_be_updated = True
                # /json.htm?activeidx=211&activetype=0&idx=13&param=addplanactivedevice&type=command
                self._requests.add(
                    'GET',
                    (''.join(self._urls['addplanactivedevice'])).format(
                        devidx,
                        self._plan_id
                    )
                )
        self._status ^= self.GET_PLAN_DEVICES
        # si besoin, lancement d'une vérification du plan
        if has_to_be_updated:
            self.update()
        # sinon on commence le tri
        elif self.sort_plan and self._ordered_devices.is_updated:
            self._order_plan_devices(datas)

    def _order_plan_devices(self: object, datas: Iterable[dict]) -> None:
        """Tri des devices dans le plan"""
        def move_down(down: bool) -> None:
            """bouge l'emplacement du device dans la plan"""
            nonlocal plan_device
            # vers le haut: way = 0
            # /json.htm?idx=117&param=changeplandeviceorder&planid=13&type=command&way=0
            # vers le bas: way = 1
            # /json.htm?idx=117&param=changeplandeviceorder&planid=13&type=command&way=1
            if not self._status & self.MOVE_PLAN_DEVICE:
                self._status |= self.MOVE_PLAN_DEVICE
                Domoticz.Status('Début de tri des widgets')
                Domoticz.Heartbeat(1)
            way = 1 if down else 0
            self._requests.add(
                'GET',
                '/json.htm?idx={}&param=changeplandeviceorder&planid={}&type=command&way={}'.format(
                    plan_device['idx'],  # pylint:disable=undefined-loop-variable
                    self._plan_id,
                    way
                )
            )
            self.update()

        order_index = 0
        for item in self._ordered_devices:
            plan_index = 0
            for plan_device in datas:
                if item.devidx == int(plan_device['devidx']):
                    if order_index > plan_index:
                        move_down(True)
                        return
                    if order_index < plan_index:
                        move_down(False)
                        return
                plan_index += 1
            order_index += 1
        if self._status & self.MOVE_PLAN_DEVICE:
            self._status ^= self.MOVE_PLAN_DEVICE
        Domoticz.Heartbeat(10)
        Domoticz.Status('Tri des widgets terminé')

    def __str__(self: object) -> str:
        """Wrapper pour str()"""

    def __repr__(self: object) -> str:
        """Wrapper pour repr()"""


class _HardWares():
    """Collections des matériels"""
    _materials: Mapping[str, Tuple[float, str, datetime]] = {}

    def items(self: object) -> Tuple[str, float, str, datetime]:
        """for...in... extended wrapper"""
        for key, value in self._materials.items():
            yield (key, *value)

    def update(self: object, datas: dict) -> bool:
        """Ajoute ou met à jour un matériel"""
        battery_level = float(datas['BatteryLevel'])
        if 0 < battery_level <= 100:
            brand = datas['HardwareType'].split()[0]
            hw_id = self._build_hw_id(datas)
            # first time hw_id is found
            last_updated = last_update_2_datetime(datas['LastUpdate'])
            if hw_id not in self._materials:
                name = '{}: {}'.format(brand, datas['Name'])
            else:
                name = self._refactor_name(hw_id, brand, datas['Name'])
                old_last_updated = self._materials[hw_id][2]
                if last_updated < old_last_updated:
                    last_updated = old_last_updated
            # update _materials
            self._materials.update({
                hw_id: [
                    battery_level,
                    name,
                    last_updated
                ]
            })
        elif battery_level == 0:
            Domoticz.Error('({}){} @ 0%'.format(datas['ID'], datas['Name']))

    def __iter__(self: object) -> None:
        """for...in... wrapper"""
        for key in self._materials:
            yield key

    def __repr__(self: object) -> str:
        """repr() Wrapper"""
        return str(self._materials)

    def __str__(self: object) -> str:
        """str() Wrapper"""
        return str(self._materials)

    def _build_hw_id(self: object, datas: dict) -> str:
        """[DOCSTRING]"""
        return '{}{}{}'.format(
            ('0{}'.format(datas['HardwareTypeVal']))[-2:],
            ('0{}'.format(datas['HardwareID']))[-2:],
            self._decode_hw_id(datas)
        )

    def _refactor_name(self: object, hw_id: str, brand: str, name: str) -> str:
        """Re-construit le nom du device"""
        old_list = self._materials[hw_id][1].split()
        common_list = list(set(old_list) & set(
            ('{}: {}'.format(brand, name)).split()))
        new_list = []
        for word in old_list:
            if word in common_list:
                new_list.append(word)
        new_str = ' '.join(new_list).rstrip(" -")
        if new_str == "{}: ".format(brand):
            new_str += '{}'.format(hw_id)
        return new_str

    @staticmethod
    def _decode_hw_id(datas: dict) -> str:
        """[DOCSTRING]"""
        hw_id = datas['ID']
        # openzwave
        if datas['HardwareTypeVal'] in (21, 94):
            hw_id = '00{}'.format(hw_id[-4:-2])
        return str(hw_id)[-4:]


class _Device(_Bounces, _PluginConfig):
    """Elément device"""

    def __init__(self: object, unit_id: int, name: str, last_update: str, bat_level: str) -> None:
        """Initialisation de la classe"""
        _PluginConfig.__init__()
        _Bounces.__init__(self, 2, 0, 100, self.empty_level)
        self.unit_id = int(unit_id)
        self.name = ''
        self.last_update = None
        self.bat_lev = 0
        self.update(bat_lev=bat_level, last_update=last_update, name=name)
        self.image_id = 'pyBattLev'

    def update(self: object, **kwargs: dict) -> None:
        """Mise à jour

        [kwargs]:

            - bat_lev (int, float): battery level
            - last_update (str, datetime): last time updated
            - name (str): new name
        """
        self.bat_lev = self._update(kwargs.get('bat_lev', self.bat_lev))
        self.last_update = last_update_2_datetime(kwargs.get(
            'last_update',
            self.last_update
        ))
        self.name = kwargs.get('name', self.name)
        self._detect_device_down()
        self._set_image_id()

    def _detect_device_down(self: object) -> None:
        """Detect device down"""
        max_time = self.last_update + timedelta(minutes=30)
        if max_time < datetime.now():
            Domoticz.Error('batterie déchargée: {}'.format(
                self.name
            ))
            self.bat_lev = self._update(0)

    def _set_image_id(self: object) -> None:
        """Define Domoticz image ID

        Returns:
            str: the Domoticz image id
        """
        if self.bat_lev > self.empty_level + 2 * self.level_delta:
            self.image_id = "pyBattLev"
        elif self.bat_lev > self.empty_level + self.level_delta:
            self.image_id = "pyBattLev_ok"
        elif self.bat_lev > self.empty_level:
            self.image_id = "pyBattLev_low"
        elif self.bat_lev > 0:
            self.image_id = "pyBattLev_empty"
        else:
            self.image_id = "pyBattLev_ko"

    def __str__(self: object) -> str:
        """Wrapper pour str()"""
        return '({}){}: {}% {}% - @{} (values in: {})'.format(
            self.unit_id,
            self.name,
            self.last_value_in,
            self.bat_lev,
            self.last_update,
            len(self._datas)
        )

    def __repr__(self: object) -> str:
        """Wrapper pour repr()"""
        return str(self)


class _Devices(_Images, _PluginConfig):
    """Collection des devices"""
    _devices: Mapping[str, Domoticz.Device] = {}
    _map_devices: Mapping[str, _Device] = {}
    _urls = {
        "notif": [
            "/json.htm?",
            "idx={}&",  # device id lors de la création
            "param=addnotification&",
            "tmsg={}&",  # message
            "tpriority=0&",
            "tsendalways=false&",
            "tsystems=&",
            "ttype=5&",
            "tvalue={}&",  # 50%
            "twhen=4&",  # less or equal
            "type=command"
        ]
    }
    _requests: _Requests = None
    _ordered_devices: _OrderedDevices = None

    def __init__(
            self: object,
            devices: Mapping[str, Domoticz.Device],
            images: Mapping[str, Domoticz.Image]) -> None:
        """Initialisation de la classe"""
        _Images.__init__(self, images)
        _PluginConfig.__init__(self)
        self._devices = devices
        self._init_map()
        self._requests = _Requests()
        self._ordered_devices = _OrderedDevices(self._devices)

    def _init_map(self: object) -> None:
        """Initialisation du mapping"""
        for device in self._devices.values():
            # v2
            self._map_devices.update({
                device.DeviceID: _Device(
                    device.Unit,
                    device.Name,
                    device.LastUpdate,
                    device.sValue
                )
            })
        debug(self._map_devices)

    def check_devices(self: object, hardwares: _HardWares) -> None:
        """Ajout/mise à jour des devices"""
        unit_ids_all = set(range(1, 255))
        unit_ids = {dev.unit_id for dev in self._map_devices.values()}
        # check devices
        for hw_key, hw_batlevel, hw_name, hw_last_update in hardwares.items():
            # Création
            if hw_key not in self._map_devices:
                unit_ids_free = unit_ids_all - unit_ids
                if len(unit_ids_free) > 0:
                    unit_id = unit_ids_free.pop()
                unit_ids.add(unit_id)
                self._map_devices.update({
                    hw_key: _Device(
                        unit_id,
                        hw_name,
                        hw_last_update,
                        hw_batlevel
                    )
                })
                Domoticz.Status('Création: {}'.format(hw_name))
                params = {
                    'Name': hw_name,
                    'Unit': unit_id,
                    'DeviceID': hw_key,
                    'TypeName': "Custom",
                    'Options': {"Custom": "1;%"}
                }
                # auto use of device
                if self.use_every_devices:
                    params.update({'Used': 1})
                Domoticz.Device(**params).Create()
                # add notification request
                if self.notify_all:
                    self._requests.add(
                        verb="GET",
                        url=''.join(self._urls["notif"]).format(
                            self._devices[unit_id].ID,
                            quote_plus(
                                '{} batterie déchargée!'.format(hw_name)),
                            self.empty_level
                        )
                    )

            # Mise à jour
            int_device = self._map_devices[hw_key]
            dom_device = self._devices[int_device.unit_id]
            int_device.update(
                bat_lev=hw_batlevel,
                last_update=hw_last_update
            )
            debug('V2 - {}'.format(int_device))
            # batt level change
            if float(dom_device.sValue) != int_device.bat_lev:
                dom_device.Update(
                    0,
                    str(round(int_device.bat_lev, 1)),
                    Image=self._images[int_device.image_id].ID
                )
            elif int_device.bat_lev > 0:
                dom_device.Touch()
            # pour le tri des widgets
            self._ordered_devices.update(
                dom_device.ID,
                dom_device.Name,
                int_device.bat_lev,
                True
            )
        debug(self._ordered_devices)

    def remove(self: object, unit_id: int) -> None:
        """Retire le device"""
        remove = 0
        for key, value in self._map_devices.items():
            if value.unit_id == unit_id:
                remove = key
                break
        if remove:
            Domoticz.Status('Removing: {}'.format(
                self._devices[self._map_devices[remove]].Name
            ))
            self._map_devices.pop(remove)
            return
        Domoticz.Error('Device not found! ({})'.format(unit_id))


class Wrapper():
    """Wrapper pour le plugin"""
    _last_value_update: float = None
    _bat_lev_conn: Domoticz.Connection = None
    _five_m_datas = (
        "GET",
        "/json.htm?type=devices&used=true"
    )
    _hardwares: _HardWares = None
    _devices: _Devices = None
    _plans: _Plans = None
    _requests: _Requests = None
    _plugin_config: _PluginConfig = None

    def __init__(self: object) -> None:
        """Initialisation de la classe"""
        self._hardwares = _HardWares()
        self._last_value_update = time()
        self._requests = _Requests()

    def on_start(self: object, **kwargs: dict) -> None:
        """Event démarrage"""
        self._plugin_config = _PluginConfig(kwargs['parameters'])
        Domoticz.Debugging(self._plugin_config.debug_level)
        debug('plugin config: {}'.format(self._plugin_config))
        self._devices = _Devices(
            kwargs['devices'],
            kwargs['images']
        )
        if self._plugin_config.create_plan:
            self._plans = _Plans(kwargs['devices'])
        self._bat_lev_conn = Domoticz.Connection(
            Name='bat_lev_conn',
            Transport='TCP/IP',
            Protocol='HTTP',
            Address='127.0.0.1',
            Port='8080'
        )

    def on_stop(self: object) -> None:
        """Event arrêt"""
        if self._bat_lev_conn.Connected():
            self._bat_lev_conn.Disconnect()

    def on_connect(self: object, *args: Tuple[Domoticz.Connection, int, str]) -> None:
        """Event connection

        [args]:

            - connection: Domoticz.Connection object
            - status: 0 if no error
            - description: failure reason
        """
        connection, status, description = args
        if connection.Name == 'bat_lev_conn':
            if status == 0:
                self._bat_lev_conn.Send(self._requests.get())
            else:
                Domoticz.Error('Erreur: {} - {}'.format(status, description))

    def on_message(self: object, *args: Tuple[Domoticz.Connection, dict]) -> None:
        """Event message

        [args]:

            - connection: Domoticz.Connection
            - dict containing:
                - status: (str)
                - headers: (dict)
                - datas: (dict)

        """
        connection, datas_1 = args
        if connection.Name == 'bat_lev_conn':
            status, _, byte_datas = datas_1.values()
            if status == '200':
                datas_2: dict = json.loads(byte_datas)
                if datas_2['status'] == 'OK':
                    self._dispatch_request(datas_2)
                else:
                    Domoticz.Error('Erreur: {}'.format(datas_2))
            else:
                Domoticz.Error('{}'.format(self._requests.last_out()))
                Domoticz.Error('Erreur: {}'.format(status))

    def on_heartbeat(self: object) -> None:
        """Event heartbeat"""
        if self._last_value_update <= time():
            self._last_value_update += 60 * 5
            self._requests.add(*self._five_m_datas)
            if self._plugin_config.create_plan:
                self._plans.update()
        if self._requests:
            if self._bat_lev_conn.Connected():
                self._bat_lev_conn.Send(self._requests.get())
            else:
                self._bat_lev_conn.Connect()

    def on_device_removed(self: object, unit_id) -> None:
        """Event device removed"""
        self._devices.remove(unit_id)
        self._requests.add(*self._five_m_datas)

    def _dispatch_request(self: object, datas: dict) -> None:
        """"""
        # FIX: missing result; happens when there's no item
        if 'result' not in datas:
            datas.update({'result': {}})
        debug(datas['title'])
        # Device
        if datas['title'] == 'Devices':
            for data in datas['result']:
                self._hardwares.update(data)
            debug('{}'.format(self._hardwares))
            self._devices.check_devices(self._hardwares)
        # Notifications
        elif datas['title'] == 'AddNotification':
            Domoticz.Status('Notification successfully added')
        # Plan of devices
        if self._plugin_config.create_plan:
            if datas['title'] == "Plans":
                self._plans.check_plans(datas['result'])
            elif datas['title'] == "GetPlanDevices":
                self._plans.check_plans_devices(datas['result'])
            elif datas['title'] == 'AddPlanActiveDevice':
                Domoticz.Status('Device successfully added to plan')
            elif datas['title'] == 'AddPlan':
                self._requests.add("GET", self._urls["plans"])
                Domoticz.Status('Plan successfully added')
