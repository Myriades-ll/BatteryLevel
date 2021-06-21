#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# pylint: disable=no-member
"""Wrapper pour le plugin"""

__all__ = ['Wrapper']

# standards libs
import json
from datetime import datetime, timedelta
from operator import attrgetter, itemgetter
from queue import Queue
from time import time
from typing import Iterable, Mapping, Tuple, Union
from urllib.parse import quote_plus

# Domoticz lib
import Domoticz

# local libs

# Constantes
INIT_PLANS = 0x0
GET_PLANS = 0x1
ADD_PLAN = 0x2
GET_PLAN_DEVICES = 0x4
MOVE_PLAN_DEVICE = 0x8
DZ_FORMAT: str = r'%Y-%m-%d %H:%M:%S'


def last_update_2_datetime(last_update: str) -> datetime:
    """conversion de la valeur last_update de domoticz en datetime"""
    try:  # python > 3.7
        last_update_dt = datetime.strptime(
            last_update,
            DZ_FORMAT
        )
    except TypeError:  # python < 3.8
        last_update_dt = datetime(
            *(time.strptime(
                last_update,
                DZ_FORMAT
            )[0:6])
        )
    return last_update_dt


class _PluginConfig():
    """Configuration du plugin"""
    empty_level = 50
    use_every_devices = False
    notify_all = False
    create_plan = False
    sort_ascending = False
    sort_descending = False
    sort_plan = False
    plan_name = ''
    _init_done = False

    @classmethod
    def __init__(cls: object, parameters: dict = None) -> None:
        """Initialisation de la classe"""
        if not isinstance(parameters, dict) or cls._init_done:
            return
        cls.empty_level = int(parameters['Mode1'])
        # fix: incorrect empty level
        try:
            assert 3 <= cls.empty_level <= 97
        except AssertionError:
            cls.empty_level = 50
        cls.use_every_devices = bool(int(parameters['Mode2']))
        cls.notify_all = bool(int(parameters['Mode3']))
        cls.plan_name = str(parameters['Mode4'])
        cls.create_plan = bool(cls.plan_name)
        mode5 = int(parameters['Mode5'])
        if mode5 == 1:
            cls.sort_ascending = True
        elif mode5 == 0:
            cls.sort_descending = True
        cls.sort_plan = cls.sort_ascending != cls.sort_descending
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


class _OrderedDevices():
    """Collection ordonnée des devices"""
    _ordered_list: Iterable[_OrderedListItem] = []
    _device_dict: Mapping[int, _OrderedListItem] = {}
    _devices: Mapping[str, Domoticz.Device] = None
    _plugin_config: _PluginConfig = None
    is_updated = False

    @classmethod
    def __init__(cls: object, devices: Mapping[str, Domoticz.Device]) -> None:
        """Initialisation de la classe"""
        cls._devices = devices
        cls._plugin_config = _PluginConfig()
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
        if cls._plugin_config.sort_descending:
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
    _last_in_datas: dict = None
    _last_out_datas: dict = None

    @classmethod
    def add(cls: object, verb: str, url: str) -> None:
        """Ajoute un élément à la queue"""
        Domoticz.Log('Ajout: {} - {}'.format(verb, url))
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
        Domoticz.Log('Sortie: {}'.format(cls._last_out_datas))
        return cls._last_out_datas

    @classmethod
    def last_in(cls: object) -> Union[dict, None]:
        """Renvoie le dernier élément inséré"""
        return cls._last_in_datas

    @classmethod
    def last_out(cls: object) -> Union[dict, None]:
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

    @classmethod
    def __str__(cls: object) -> str:
        """Wrapper pour str()"""
        return '{} in requests queue'.format(cls._queue_length)


class _Plans():
    """Gestion des emplacments"""
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
    _plugin_config: _PluginConfig = None

    def __init__(self: object, devices: Mapping[str, Domoticz.Device]) -> None:
        """Initialisation de la classe"""
        self._requests = _Requests()
        self._devices = devices
        self._ordered_devices = _OrderedDevices(devices)
        self._plugin_config = _PluginConfig()
        self._init_plan()

    def _init_plan(self: object) -> None:
        """Initialisation du plan des devices"""
        if 'plan_id' in Domoticz.Configuration():
            self._plan_id = int(Domoticz.Configuration()['plan_id'])
            self._status |= GET_PLANS & ADD_PLAN
            Domoticz.Status('Battery plan id acquired')
        # launch plan creation
        if self._plan_id == 0 and self._status == INIT_PLANS:
            self._status |= GET_PLANS
            self._requests.add("GET", self._urls["plans"])

    def update(self: object) -> None:
        """Appel de mise à jour"""
        if not self._status & GET_PLAN_DEVICES:
            self._status |= GET_PLAN_DEVICES
            self._requests.add(
                'GET', self._urls['getplandevices'].format(self._plan_id)
            )

    def check_plans(self: object, datas: list) -> None:
        """vérifie la liste des plans la liste des plans"""
        # Vérifier l'existence du plan
        for value in datas:
            if value['Name'] == self._plugin_config.plan_name:
                self._status |= ADD_PLAN
                self._plan_id = value['idx']
                Domoticz.Configuration({'plan_id': self._plan_id})
                Domoticz.Status('Battery plan id acquired')
                self.update()
                return
        # Création du 'plan'
        # /json.htm?name=&param=addplan&type=command
        if not self._status & ADD_PLAN:
            self._status |= ADD_PLAN
            self._requests.add(
                'GET',
                self._urls['addplan'].format(self._plugin_config.plan_name)
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
        self._status ^= GET_PLAN_DEVICES
        # si besoin, lancement d'une vérification du plan
        if has_to_be_updated:
            self.update()
        # sinon on commence le tri
        elif self._plugin_config.sort_plan and self._ordered_devices.is_updated:
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
            if not self._status & MOVE_PLAN_DEVICE:
                self._status |= MOVE_PLAN_DEVICE
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
        if self._status & MOVE_PLAN_DEVICE:
            self._status ^= MOVE_PLAN_DEVICE
        Domoticz.Heartbeat(10)
        Domoticz.Status('Tri des widgets terminé')

    def __str__(self: object) -> str:
        """Wrapper pour str()"""

    def __repr__(self: object) -> str:
        """Wrapper pour repr()"""


class _HardWares():
    """Collections des matériels"""
    _materials = {}

    def items(self: object) -> Tuple[str, int, str, datetime]:
        """for...in... extended wrapper"""
        for key, value in self._materials.items():
            yield (key, *value)

    def update(self: object, datas: dict) -> bool:
        """Ajoute ou met à jour un matériel"""
        if datas['BatteryLevel'] < 255:
            brand = datas['HardwareType'].split()[0]
            hw_id = self._build_hw_id(datas)
            # first time hw_id is found
            if hw_id not in self._materials:
                self._materials.update({
                    hw_id: [
                        datas['BatteryLevel'],
                        '{}: {}'.format(brand, datas['Name']),
                        last_update_2_datetime(datas['LastUpdate'])
                    ]
                })
            else:
                prev_last_update = self._materials[hw_id][2]
                new_last_update = last_update_2_datetime(datas['LastUpdate'])
                if new_last_update > prev_last_update:
                    prev_last_update = new_last_update
                self._materials.update({
                    hw_id: [
                        datas['BatteryLevel'],
                        self._refactor_name(hw_id, brand, datas['Name']),
                        prev_last_update
                    ]
                })

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


class _Devices():
    """Classe des devices"""
    _devices: Mapping[str, Domoticz.Device] = {}
    _images: Mapping[str, Domoticz.Image] = {}
    _plugin_config: _PluginConfig = None
    _icons_files = {
        "pyBattLev": "pyBattLev icons.zip",
        "pyBattLev_ok": "pyBattLev_ok icons.zip",
        "pyBattLev_low": "pyBattLev_low icons.zip",
        "pyBattLev_empty": "pyBattLev_empty icons.zip",
        "pyBattLev_ko": "pyBattLev_ko icons.zip"
    }
    _map_devices_hw = {}
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
        self._devices = devices
        self._plugin_config = _PluginConfig()
        self._images = images
        self._init_map()
        self._requests = _Requests()
        self._ordered_devices = _OrderedDevices(self._devices)
        # populate image list
        for key, value in self._icons_files.items():
            if key not in self._images:
                Domoticz.Image(value).Create()

    def _init_map(self: object) -> None:
        """Initialisation du mapping"""
        for device in self._devices.values():
            self._map_devices_hw.update({device.DeviceID: device.Unit})

    def check_devices(self: object, hardwares: _HardWares) -> None:
        """Ajout/mise à jour des devices"""
        # check devices
        for hw_key, hw_batlevel, hw_name, hw_last_update in hardwares.items():
            # Création
            if hw_key not in self._map_devices_hw:
                unit_id = max(self._map_devices_hw.values(), default=0) + 1
                self._map_devices_hw.update({
                    hw_key: unit_id
                })
                Domoticz.Status('Création: {}'.format(hw_name))
                Domoticz.Debug('{}'.format(hw_name))
                params = {
                    'Name': hw_name,
                    'Unit': unit_id,
                    'DeviceID': hw_key,
                    'TypeName': "Custom",
                    'Options': {"Custom": "1;%"}
                }
                if self._plugin_config.use_every_devices:
                    params.update({'Used': 1})
                Domoticz.Device(**params).Create()
                # add notification request
                if self._plugin_config.notify_all:
                    self._requests.add(
                        verb="GET",
                        url=''.join(self._urls["notif"]).format(
                            self._devices[unit_id].ID,
                            quote_plus('Batterie déchargée!'),
                            self._plugin_config.empty_level
                        )
                    )

            # Mise à jour
            device = self._devices[self._map_devices_hw[hw_key]]
            Domoticz.Debug('{} - {} - {}'.format(
                device.Name,
                device.nValue,
                device.sValue
            ))
            # detect hardware down
            max_time = hw_last_update + timedelta(minutes=30)
            if max_time < datetime.now():
                Domoticz.Error('batterie morte: {}'.format(
                    device.Name
                ))
                hw_batlevel = 0
            # batt level change
            if device.nValue != hw_batlevel:
                delta_level = (100 - self._plugin_config.empty_level) / 3
                if hw_batlevel >= (self._plugin_config.empty_level + 2 * delta_level):
                    image_id = "pyBattLev"
                elif hw_batlevel >= (self._plugin_config.empty_level + delta_level):
                    image_id = "pyBattLev_ok"
                elif hw_batlevel >= self._plugin_config.empty_level:
                    image_id = "pyBattLev_low"
                elif hw_batlevel == 0:
                    image_id = "pyBattLev_ko"
                else:
                    image_id = "pyBattLev_empty"
                device.Update(
                    hw_batlevel,
                    str(hw_batlevel),
                    Image=self._images[image_id].ID
                )
                # pour le tri des widgets
                self._ordered_devices.update(
                    device.ID,
                    device.Name,
                    hw_batlevel,
                    True
                )

            else:
                device.Touch()

    def remove(self: object, unit_id: int) -> None:
        """Retire le device"""
        remove = 0
        for key, value in self._map_devices_hw.items():
            if value == unit_id:
                remove = key
                break
        if remove:
            Domoticz.Status('Removing: {}'.format(
                self._devices[self._map_devices_hw[remove]].Name
            ))
            self._map_devices_hw.pop(remove)
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
        Domoticz.Debugging(2)

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
        # Device
        if datas['title'] == 'Devices':
            for data in datas['result']:
                self._hardwares.update(data)
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
