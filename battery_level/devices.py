#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""Domoticz devices"""

# standard libs
from collections import deque, namedtuple
from datetime import datetime, timedelta
from statistics import mean
from typing import Iterable, Iterator, List, Mapping, Tuple, Union
from urllib.parse import quote_plus

# Domoticz lib
import Domoticz

# local libs
from battery_level.common import debug, last_update_2_datetime
from battery_level.images import Images
from battery_level.plugin_config import PluginConfig
from battery_level.requests import Requests


class _HardWares:
    """Collections des matériels"""
    materials: Mapping[str, Tuple[float, str, datetime]] = {}

    @classmethod
    def items(cls: object) -> Tuple[str, float, str, datetime]:
        """for...in... extended wrapper"""
        for key, value in cls.materials.items():
            yield (key, *value)

    @classmethod
    def update(cls: object, datas: dict) -> bool:
        """Ajoute ou met à jour un matériel"""
        battery_level = float(datas['BatteryLevel'])
        if 0 < battery_level <= 100:
            brand = datas['HardwareType'].split()[0]
            hw_id = cls._build_hw_id(datas)
            # first time hw_id is found
            last_updated = last_update_2_datetime(datas['LastUpdate'])
            if hw_id not in cls.materials:
                name = '{}: {}'.format(brand, datas['Name'])
            else:
                name = cls._refactor_name(hw_id, brand, datas['Name'])
                old_last_updated = cls.materials[hw_id][2]
                if last_updated < old_last_updated:
                    last_updated = old_last_updated
            # update materials
            cls.materials.update({
                hw_id: [
                    battery_level,
                    name,
                    last_updated
                ]
            })

    @classmethod
    def __repr__(cls: object) -> str:
        """repr() Wrapper"""
        return str(cls.materials)

    @classmethod
    def __str__(cls: object) -> str:
        """str() Wrapper"""
        return str(cls.materials)

    @classmethod
    def _build_hw_id(cls: object, datas: dict) -> str:
        """[DOCSTRING]"""
        return '{}{}{}'.format(
            ('0{}'.format(datas['HardwareTypeVal']))[-2:],
            ('0{}'.format(datas['HardwareID']))[-2:],
            cls._decode_hw_id(datas)
        )

    @classmethod
    def _refactor_name(cls: object, hw_id: str, brand: str, name: str) -> str:
        """Re-construit le nom du device"""
        old_list = cls.materials[hw_id][1].split()
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


class _Bounces:
    """Gestion des rebonds des valeurs"""
    _BOUNCEMODES = namedtuple(
        'Modes', ['DISABLED', 'SYSTEMATIC', 'POND_1H', 'POND_1D'])
    _MINMAX = namedtuple('minmax', ['MIN', 'MAX', 'MIN_RESET', 'MAX_RESET'])

    def __init__(
            self: object,
            mode: int,
            mini: Union[str, int, float] = 0,
            maxi: Union[str, int, float] = 100) -> None:
        """Initialisation de la classe"""
        self._modes = self._BOUNCEMODES(0, 1, 2, 4)
        self._bounce_mode = mode
        self._min_max = self._MINMAX(
            mini,
            maxi,
            PluginConfig.empty_level,
            100 - PluginConfig.empty_level
        )
        self.last_value_out = self.last_value_in = 100.0
        self._pond = 12
        if mode == 4:
            self._pond = 288
        self._datas = deque(maxlen=self._pond)

    def _update_bounce(self: object, new_data: Union[str, int, float]) -> float:
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
            if len(self._datas) == 1:
                self._datas *= self._pond
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


class _Device(_Bounces):
    """Elément device"""

    def __init__(self: object, unit_id: int, name: str, last_update: str, bat_level: str) -> None:
        """Initialisation de la classe"""
        _Bounces.__init__(self, 2, 0, 100)
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
        self.bat_lev = self._update_bounce(kwargs.get('bat_lev', self.bat_lev))
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
            self.bat_lev = self._update_bounce(0)

    def _set_image_id(self: object) -> None:
        """Define Domoticz image ID

        Returns:
            str: the Domoticz image id
        """
        if self.bat_lev > PluginConfig.empty_level + 2 * PluginConfig.level_delta:
            self.image_id = "pyBattLev"
        elif self.bat_lev > PluginConfig.empty_level + PluginConfig.level_delta:
            self.image_id = "pyBattLev_ok"
        elif self.bat_lev > PluginConfig.empty_level:
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


class Devices(_HardWares, Iterable[_Device]):
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
    _init_done = False

    def __new__(cls: object, devices: Mapping[str, Domoticz.Device] = None) -> object:
        """Initialisation de la classe"""
        if not cls._init_done or isinstance(devices, dict):
            cls._devices = devices
            cls._init_map()
            cls._init_done = True
        return super(Devices, cls).__new__(cls)

    @classmethod
    def _init_map(cls: object) -> None:
        """Initialisation du mapping"""
        for device in cls._devices.values():
            cls._map_devices.update({
                device.DeviceID: _Device(
                    device.Unit,
                    device.Name,
                    device.LastUpdate,
                    device.sValue
                )
            })
        debug(cls._map_devices)

    @classmethod
    def _check_devices(cls: object) -> None:
        """Ajout/mise à jour des devices"""
        unit_ids_all = set(range(1, 255))
        unit_ids = set(
            sorted({dev.unit_id for dev in cls._map_devices.values()}))
        # check devices
        for hw_key, hw_batlevel, hw_name, hw_last_update in cls.items():
            # Création
            if hw_key not in cls._map_devices:
                unit_ids_free = unit_ids_all - unit_ids
                if len(unit_ids_free) > 0:
                    unit_id = unit_ids_free.pop()
                    unit_ids.add(unit_id)
                else:
                    Domoticz.Error('Plus de device disponible!')
                    return
                cls._map_devices.update({
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
                if PluginConfig.use_every_devices:
                    params.update({'Used': 1})
                Domoticz.Device(**params).Create()
                # add notification request
                if PluginConfig.notify_all:
                    Requests.add(
                        verb="GET",
                        url=''.join(cls._urls["notif"]).format(
                            cls._devices[unit_id].ID,
                            quote_plus(
                                '{} batterie déchargée!'.format(hw_name)),
                            PluginConfig.empty_level
                        )
                    )
            # Mise à jour interne
            cls._map_devices[hw_key].update(
                bat_lev=hw_batlevel,
                last_update=hw_last_update
            )
        # Mise à jour Domoticz
        debug('Internal device view', **cls._map_devices)
        for device in cls._devices.values():
            int_device = cls._map_devices[device.DeviceID]
            if device.DeviceID not in cls.materials:  # device down
                int_device.update(bat_lev=0)
            if float(device.sValue) != int_device.bat_lev:
                device.Update(
                    0,
                    str(round(int_device.bat_lev, 1)),
                    Image=Images()[int_device.image_id]
                )
            else:
                device.Touch()

    @classmethod
    def remove(cls: object, unit_id: int) -> None:
        """Retire le device"""
        remove = 0
        for key, value in cls._map_devices.items():
            if value.unit_id == unit_id:
                remove = key
                break
        if remove:
            Domoticz.Status('Removing: {}'.format(
                cls._devices[cls._map_devices[remove]].Name
            ))
            cls._map_devices.pop(remove)
            return
        Domoticz.Error('Device not found! ({})'.format(unit_id))

    @classmethod
    def build_from_hardware(cls: object, hardwares: dict) -> None:
        """[summary]

        Args:

            - hardwares (dict): les devices obtenus de l'api domoticz
        """
        for data in hardwares:
            cls.update(data)
        debug('Detected hardwares', **cls.materials)
        cls._check_devices()

    @classmethod
    def values(cls: object) -> List[_Device]:
        """Liste des devices"""
        return cls._devices.values()

    @classmethod
    def __iter__(cls: object) -> Iterator[_Device]:
        """Wrapper for ... in ..."""
        for device in cls._devices.values():
            yield device
