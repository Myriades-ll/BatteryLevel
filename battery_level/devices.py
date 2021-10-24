#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""Domoticz devices"""

# standard libs
from collections import deque, namedtuple
from datetime import datetime, timedelta
from enum import IntFlag, auto
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
    materials: Mapping[str, Tuple[float, str, datetime, int]] = {}

    @classmethod
    def items(cls) -> Tuple[str, float, str, datetime]:
        """for...in... extended wrapper"""
        for key, value in cls.materials.items():
            yield (key, *value)

    @classmethod
    def update(cls, datas: dict) -> bool:
        """Ajoute ou met à jour un matériel"""
        # no battery material
        if datas['HardwareTypeVal'] in (23,):
            return
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
                    last_updated,
                    datas['HardwareTypeVal']
                ]
            })

    @classmethod
    def __repr__(cls) -> str:
        """repr() Wrapper"""
        return str(cls.materials)

    @classmethod
    def __str__(cls) -> str:
        """str() Wrapper"""
        return str(cls.materials)

    @classmethod
    def _build_hw_id(cls, datas: dict) -> str:
        """[DOCSTRING]"""
        return '{}{}{}'.format(
            ('0{}'.format(datas['HardwareTypeVal']))[-2:],
            ('0{}'.format(datas['HardwareID']))[-2:],
            cls._decode_hw_id(datas)
        )

    @classmethod
    def _refactor_name(cls, hw_id: str, brand: str, name: str) -> str:
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


class _BounceModes(IntFlag):
    """Modes de pondération"""
    DISABLED = auto()    # pas de pondération
    SYSTEMATIC = auto()  # mémoire de la valeur la plus basse
    POND_1H = auto()     # pondération sur 1h
    POND_1D = auto()     # opndération sur 1 journée


class _Bounces:
    """Gestion des rebonds des valeurs"""
    _MINMAX = namedtuple('minmax', ['MIN', 'MAX', 'MIN_RESET', 'MAX_RESET'])

    def __init__(
            self,
            mode: _BounceModes,
            mini: Union[str, int, float] = 0,
            maxi: Union[str, int, float] = 100) -> None:
        """Initialisation de la classe"""
        self._bounce_mode = mode
        self._min_max = self._MINMAX(
            mini,
            maxi,
            PluginConfig.empty_level,
            100 - PluginConfig.empty_level
        )
        self.last_value_out = self.last_value_in = 100.0
        self._pond = 1
        if mode & _BounceModes.POND_1H:
            self._pond = 12
        elif mode & _BounceModes.POND_1D:
            self._pond = 288
        self._datas = deque(maxlen=self._pond)

    def _update_bounce(self, new_data: Union[str, int, float]) -> float:
        """Mise à jour des données"""
        try:
            assert type(new_data) in [str, int, float]
        except AssertionError:
            return self.last_value_out
        self.last_value_in = float(new_data)
        # reset system
        if (
                self.last_value_in >= self._min_max.MIN_RESET
                and self.last_value_out <= self._min_max.MIN_RESET
                or self.last_value_out == 0
                and self.last_value_in > 0
        ):
            self._datas.clear()
            self._datas.append(self.last_value_in)
        # no bounce; always remembering the lowest value
        if self._bounce_mode & _BounceModes.SYSTEMATIC:
            if self.last_value_in < self.last_value_out:
                self._datas.append(self.last_value_in)
            else:
                self._datas.append(self.last_value_out)
        else:
            self._datas.append(self.last_value_in)
            if len(self._datas) == 1:
                self._datas *= self._pond
        self.last_value_out = mean(self._datas)
        return self.last_value_out

    def __str__(self) -> str:
        """Wrapper pour str()"""
        return '{} {}'.format(_BounceModes(), self._bounce_mode)

    def __repr__(self) -> str:
        """Wrapper pour repr()"""
        return str(self)

    def __float__(self) -> float:
        """Wrapper pour float()"""
        return self.last_value_out

    def __int__(self) -> int:
        """Wrapper pour int()"""
        return int(self.last_value_out)


class _Device(_Bounces):
    """Elément device

        [kwargs]:

            - unit_id (str,int): Device.Unit
            - name (str): Device.Name
            - last_update (str): Device.LastUpdate
            - bat_lev (str): Device.sValue
            - dz_type (int): Device.Type
    """

    def __init__(self, **kwargs: dict) -> None:
        """Initialisation de la classe"""
        _Bounces.__init__(self, _BounceModes.SYSTEMATIC, 0, 100)
        self.unit_id = int(kwargs.get('unit_id'))
        self.name = ''
        self.last_update: str = None
        self.bat_lev = 0
        self.dz_type: int = kwargs.get('dz_type')
        self.update(
            bat_lev=kwargs['bat_lev'],
            last_update=kwargs['last_update'],
            name=kwargs['name']
        )
        self.image_id = 'pyBattLev'

    def update(self, **kwargs: dict) -> None:
        """Mise à jour

        [kwargs]:

            - bat_lev (int, float): battery level
            - last_update (str, datetime): last time updated
            - name (str): new name
            - dz_type (int): Domoticz device type
        """
        self.bat_lev = self._update_bounce(kwargs.get('bat_lev', self.bat_lev))
        self.last_update = last_update_2_datetime(kwargs.get(
            'last_update',
            self.last_update
        ))
        self.name = kwargs.get('name', self.name)
        self.dz_type = kwargs.get('dz_type', self.dz_type)
        self._detect_device_down()
        self._set_image_id()

    def _detect_device_down(self) -> None:
        """Detect device down"""
        # ignore detection
        if self.dz_type in (1,):
            return
        max_time = self.last_update + timedelta(minutes=30)
        if max_time < datetime.now():
            Domoticz.Error('batterie déchargée: {}'.format(
                self.name
            ))
            self.bat_lev = self._update_bounce(0)

    def _set_image_id(self) -> None:
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

    def __str__(self) -> str:
        """Wrapper pour str()"""
        return '({}[{}]){}: {}% {}% - @{} (values in: {})'.format(
            self.unit_id,
            self.dz_type,
            self.name,
            self.last_value_in,
            self.bat_lev,
            self.last_update,
            len(self._datas)
        )

    def __repr__(self) -> str:
        """Wrapper pour repr()"""
        return self.__str__()


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

    def __new__(cls, devices: Mapping[str, Domoticz.Device] = None) -> object:
        """Initialisation de la classe"""
        if not cls._init_done or isinstance(devices, dict):
            cls._devices = devices
            cls._init_map()
            cls._init_done = True
        return super(Devices, cls).__new__(cls)

    @classmethod
    def _init_map(cls) -> None:
        """Initialisation du mapping"""
        for device in cls._devices.values():
            cls._map_devices.update({
                device.DeviceID: _Device(
                    unit_id=device.Unit,
                    name=device.Name,
                    last_update=device.LastUpdate,
                    bat_lev=device.sValue,
                    dz_type=device.Type
                )
            })

    @classmethod
    def _check_devices(cls) -> None:
        """Ajout/mise à jour des devices"""
        unit_ids_all = set(range(1, 255))
        unit_ids = set(
            sorted({dev.unit_id for dev in cls._map_devices.values()})
        )
        # check devices
        for hw_key, hw_batlevel, hw_name, hw_last_update, dz_type in cls.items():
            # Création
            if hw_key not in cls._map_devices:
                unit_ids_free = unit_ids_all - unit_ids
                if len(unit_ids_free) > 0:
                    unit_id = unit_ids_free.pop()
                    unit_ids.add(unit_id)
                else:
                    Domoticz.Error('Plus de device disponible!')
                    break
                cls._map_devices.update({
                    hw_key: _Device(
                        unit_id=unit_id,
                        name=hw_name,
                        last_update=hw_last_update,
                        bat_lev=hw_batlevel,
                        dz_type=dz_type
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
                last_update=hw_last_update,
                dz_type=dz_type
            )
        # Mise à jour Domoticz
        debug('Internal device view', **cls._map_devices)
        for device in cls._devices.values():
            int_device = cls._map_devices[device.DeviceID]
            if device.DeviceID not in cls.materials:  # device down
                int_device.update(bat_lev=0)
            bat_lev = str(round(int_device.bat_lev, 1))
            if device.sValue != bat_lev:
                device.Update(
                    0,
                    bat_lev,
                    Image=Images()[int_device.image_id]
                )
            else:
                device.Touch()

    @classmethod
    def remove(cls, unit_id: int) -> None:
        """Retire le device
        BUG: entering infinite loop when removing unit, unit is not found in map!
        """
        for key, value in cls._map_devices.items():
            if value.unit_id == unit_id:
                Domoticz.Status('Removing: {}'.format(
                    cls._devices[cls._map_devices[key]].Name
                ))
                cls._map_devices.pop(key)
                return
        Domoticz.Error('Device not found! ({})'.format(unit_id))

    @classmethod
    def build_from_hardware(cls, hardwares: dict) -> None:
        """[summary]

        Args:
            - hardwares (dict): les devices obtenus de l'api domoticz
        """
        for data in hardwares:
            cls.update(data)
        debug('Detected hardwares', **cls.materials)
        cls._check_devices()

    @classmethod
    def values(cls) -> List[_Device]:
        """Liste des devices"""
        return cls._devices.values()

    @classmethod
    def __iter__(cls) -> Iterator[_Device]:
        """Wrapper for ... in ..."""
        for device in cls._devices.values():
            yield device
