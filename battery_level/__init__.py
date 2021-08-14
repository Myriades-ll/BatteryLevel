#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""Wrapper pour le plugin"""

__all__ = ['Wrapper']

# standards libs
import json
from time import time
from typing import Iterable, Mapping, Tuple

# Domoticz lib
import Domoticz

# local libs
from battery_level.common import debug
from battery_level.devices import Devices
from battery_level.images import Images
from battery_level.plans import Plans
from battery_level.plugin_config import PluginConfig
from battery_level.requests import Requests


class Wrapper:
    """Wrapper pour le plugin"""
    _bat_lev_conn: Domoticz.Connection = None
    _five_m_datas = (
        "GET",
        "/json.htm?type=devices&used=true"
    )

    def __init__(self: object) -> None:
        """Initialisation de la classe"""
        self._last_value_update = time()

    def on_start(self: object, **_kwargs: dict) -> None:
        """Event démarrage"""
        Domoticz.Debugging(PluginConfig.debug_level)
        debug('{}'.format(PluginConfig()))
        Plans()
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

            - connection (Domoticz.Connection): Domoticz.Connection object
            - status (int): 0 if no error
            - description (str): failure reason
        """
        connection, status, description = args
        if connection.Name == 'bat_lev_conn':
            if status == 0:
                self._bat_lev_conn.Send(Requests.get())
            else:
                Domoticz.Error('Erreur: {} - {}'.format(status, description))

    def on_message(self: object, *args: Tuple[Domoticz.Connection, dict]) -> None:
        """Event message

        [args]:

            - connection (Domoticz.Connection): Domoticz.Connection object
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
                Domoticz.Error('{}'.format(Requests.last_out()))
                Domoticz.Error('Erreur: {}'.format(status))

    def on_heartbeat(self: object) -> None:
        """Event heartbeat"""
        if self._last_value_update <= time():
            self._last_value_update += 60 * 5
            Requests.add(*self._five_m_datas)
            if PluginConfig.create_plan:
                Plans.update()
        if Requests():
            if self._bat_lev_conn.Connected():
                self._bat_lev_conn.Send(Requests.get())
            else:
                self._bat_lev_conn.Connect()

    @staticmethod
    def on_device_modified(unit_id: int) -> None:
        """Event device modified"""
        debug(unit_id)

    def on_device_removed(self: object, unit_id: int) -> None:
        """Event device removed"""
        Devices.remove(unit_id)
        Requests.add(*self._five_m_datas)

    @staticmethod
    def _dispatch_request(datas: dict) -> None:
        """"""
        # FIX: missing result; happens when there's no item
        if 'result' not in datas:
            datas.update({'result': {}})
        debug('API/JSON request: {}'.format(datas['title']))
        # Device
        if datas['title'] == 'Devices':
            Devices.build_from_hardware(datas['result'])
        # Notifications
        elif datas['title'] == 'AddNotification':
            Domoticz.Status('Notification successfully added')
        # Plan of devices
        if PluginConfig.create_plan:
            if datas['title'] == "Plans":
                Plans.check_plans(datas['result'])
            elif datas['title'] == "GetPlanDevices":
                Plans.check_plans_devices(datas['result'])
            elif datas['title'] == 'AddPlanActiveDevice':
                Domoticz.Status('Device successfully added to plan')
            elif datas['title'] == 'AddPlan':
                Requests.add("GET", Plans.urls["plans"])
                Domoticz.Status('Plan successfully added')
