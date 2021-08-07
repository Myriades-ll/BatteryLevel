#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""Domoticz settings"""

# standard libs
from collections.abc import Sized
from typing import Any, Mapping

__all__ = ['DomSettings', ]


class _Pushover:
    """notification Pushover"""
    _settings = {}
    api = ''
    user = ''
    enabled = ''

    def __new__(cls: object, settings: Mapping[str, str]) -> object:
        """Création de la classe"""
        ndict = {}
        for key, arg in settings.items():
            if 'Pushover' not in key:
                continue
            key = key[8:].lower()
            setattr(cls, key, arg)
            ndict.update({key: arg})
        cls._settings.update(ndict)
        return super(_Pushover, cls).__new__(cls)

    @classmethod
    def __bool__(cls: object) -> bool:
        """Wrapper bool()"""
        return bool(int(cls.enabled))

    @classmethod
    def __int__(cls: object) -> int:
        """Wrapper int()"""
        return int(cls.enabled)

    @classmethod
    def __str__(cls: object) -> str:
        """Wrapper pour str()"""
        print('str')
        return '{}'.format(cls._settings)

    @classmethod
    def __repr__(cls: object) -> str:
        """Wrapper pour repr()"""
        print('repr')
        return str(cls)


class _Notifications(Sized):
    """Liste des notifications"""
    pushover: _Pushover = None

    def __new__(cls: object, settings: dict) -> object:
        """Création de la classe"""
        cls.pushover = _Pushover(settings)
        return super(_Notifications, cls).__new__(cls)

    @classmethod
    def __len__(cls: object) -> int:
        """Wrapper len()

        Renvoie le nombre de notifications actives
        """
        len_ = 0
        len_ += int(cls.pushover)
        return len_


class DomSettings:
    """Paramètres de Domoticz

    Si vous avez besoin des paramètres de Domoticz dans votre plugin.
    Il faut placer la ligne ci-dessous dans l'event OnHeartbeat();
    ceci afin de conserver les paramètres à jour dans la classe.

                DomSettings.heartbeat()

    Si vous ne le faites pas, vous perdrez beaucoup de fonctionnalitées de classe:

    - l'accès direct des paramètres (ex: DomSettings().pushoverenabled)
    - l'accès par chemin (ex: DomSettings.notifications.pushover.enabled)
    - l'accès aux tests booléens (ex: DomSettings.notifications.pushover)

    Il vous restera néanmoins l'accès traditionnel (sensible à la casse):

    - Settings['PushoverEnabled']
    - DomSettings()['PushoverEnabled']

    Mais vous en conviendrez, cette classe perds son sens...
    """
    _init_done = False
    notifications: _Notifications = None
    _settings = {}

    def __new__(cls: object, settings: dict = None) -> object:
        """Initialisation de la classe"""
        print('--new--')
        if isinstance(settings, dict) and not cls._init_done:
            cls._settings = settings
            print('Settings is: {}'.format(cls._settings is settings))
            cls.heartbeat()
            print('Settings is: {}'.format(cls._settings is settings))
            cls._init_done = True
        return super(DomSettings, cls).__new__(cls)

    @classmethod
    def __bool__(cls: object) -> bool:
        """Wrapper bool()"""
        return cls._init_done

    @classmethod
    def __getattr__(cls: object, name: str) -> Any:
        """in case __getattribute__() fails"""
        print('--getattr--')
        name = name.lower()
        if name in cls._settings:
            if 'enabled' in name:
                return bool(int(cls._settings[name]))
            return cls._settings[name]
        raise AttributeError(
            "No attribute '{}' found in Domoticz settings".format(name))

    @classmethod
    def __getitem__(cls: object, name: str) -> Any:
        """Wrapper obj['str']"""
        print('--getitem--')
        name = name.lower()
        if name in cls._settings:
            return cls._settings[name]
        raise KeyError('{} not found'.format(name))

    @classmethod
    def __str__(cls: object) -> str:
        """Wrapper pour str()"""

    @classmethod
    def __repr__(cls: object) -> str:
        """Wrapper pour repr()"""

    @classmethod
    def heartbeat(cls: object) -> None:
        """Mise à jour des paramètres"""
        print('--heartbeat--')
        cls.notifications = _Notifications(cls._settings)
        ndict = {}
        for key, arg in cls._settings.items():
            key = key.lower()
            if 'enabled' in key:
                arg = bool(int(arg))
            ndict.update({key: arg})
        cls._settings.update(ndict)


# for purpose tests
if __name__ == '__main__':
    if DomSettings():
        print('init done')
    else:
        print('init not done')
    DomSettings({
        'DB_Version': '148',
        'Title': 'Domoticz',
        'LightHistoryDays': '7',
        'MeterDividerEnergy': '1000',
        'MeterDividerGas': '100',
        'MeterDividerWater': '100',
        'RandomTimerFrame': '15',
        'ElectricVoltage': '230',
        'CM113DisplayType': '0',
        '5MinuteHistoryDays': '1',
        'SensorTimeout': '60',
        'SensorTimeoutNotification': '0',
        'UseAutoUpdate': '1',
        'UseAutoBackup': '0',
        'CostEnergy': '1353',
        'CostEnergyT2': '1852',
        'CostEnergyR1': '800',
        'CostEnergyR2': '800',
        'CostGas': '6218',
        'CostWater': '16473',
        'UseEmailInNotifications': '1',
        'SendErrorNotifications': '0',
        'EmailPort': '25',
        'EmailAsAttachment': '0',
        'DoorbellCommand': '0',
        'SmartMeterType': '0',
        'EnableTabLights': '1',
        'EnableTabTemp': '1',
        'EnableTabWeather': '1',
        'EnableTabUtility': '1',
        'EnableTabCustom': '1',
        'EnableTabScenes': '1',
        'EnableTabFloorplans': '0',
        'NotificationSensorInterval': '1800',
        'NotificationSwitchInterval': '0',
        'RemoteSharedPort': '6144',
        'Language': 'fr',
        'DashboardType': '0',
        'MobileType': '0',
        'WindUnit': '0',
        'TempUnit': '0',
        'WeightUnit': '0',
        'SecStatus': '0',
        'SecOnDelay': '30',
        'AuthenticationMethod': '0',
        'ReleaseChannel': '0',
        'RaspCamParams': '-w 800 -h 600 -t 1',
        'UVCParams': '-S80 -B128 -C128 -G80 -x800 -y600 -q100',
        'AcceptNewHardware': '1',
        'ZWavePollInterval': '60',
        'ZWaveEnableDebug': '0',
        'ZWaveNetworkKey': '0x01,0x02,0x03,0x04,0x05,0x06,\
            0x07,0x08,0x09,0x0A,0x0B,0x0C,0x0D,0x0E,0x0F,0x10',
        'ZWaveEnableNightlyNetworkHeal': '1',
        'BatteryLowNotification': '15',
        'AllowWidgetOrdering': '1',
        'ActiveTimerPlan': '0',
        'HideDisabledHardwareSensors': '1',
        'EnableEventScriptSystem': '1',
        'EventSystemLogFullURL': '1',
        'DisableDzVentsSystem': '0',
        'DzVentsLogLevel': '3',
        'LogEventScriptTrigger': '1',
        'WebTheme': 'default',
        'FloorplanPopupDelay': '750',
        'FloorplanFullscreenMode': '0',
        'FloorplanAnimateZoom': '1',
        'FloorplanShowSensorValues': '1',
        'FloorplanShowSwitchValues': '0',
        'FloorplanShowSceneNames': '1',
        'FloorplanRoomColour': 'Blue',
        'FloorplanActiveOpacity': '25',
        'FloorplanInactiveOpacity': '5',
        'TempHome': '20',
        'TempAway': '15',
        'TempComfort': '22.0',
        'DegreeDaysBaseTemperature': '18.0',
        'HTTPURL': 'aHR0cHM6Ly93d3cuc29tZWdhdGV3YXkuY29tL3B1c2h1cmwucGhwP3VzZXJ\
            uYW1lPSNGSUVMRDEmcGFzc3dvcmQ9I0ZJRUxEMiZhcGlrZXk9I0ZJRUxEMyZmcm9tP\
                SNGSUVMRDQmdG89I1RPJm1lc3NhZ2U9I01FU1NBR0U=',
        'HTTPPostContentType': 'YXBwbGljYXRpb24vanNvbg==',
        'ShowUpdateEffect': '0',
        'ShortLogInterval': '5',
        'SendErrorsAsNotification': '0',
        'IFTTTEnabled': '0',
        'EmailEnabled': '0',
        'Location': '48.55917;-4.34315',
        'ClickatellEnabled': '0',
        'ClickatellAPI': '0',
        'ClickatellTo': '0',
        'EmailFrom': '0',
        'EmailServer': '0',
        'EmailTo': '0',
        'EmailPassword': '0',
        'EmailUsername': '0',
        'FCMEnabled': '0',
        'HTTPEnabled': '0',
        'HTTPField1': '0',
        'HTTPField2': '0',
        'HTTPField3': '0',
        'HTTPField4': '0',
        'HTTPPostData': '0',
        'HTTPPostHeaders': '0',
        'HTTPTo': '0',
        'KodiIPAddress': '224.0.0.1',
        'KodiEnabled': '0',
        'KodiPort': '9777',
        'KodiTimeToLive': '5',
        'LmsPlayerMac': '0',
        'LmsDuration': '5',
        'LmsEnabled': '0',
        'ProwlAPI': '0',
        'ProwlEnabled': '0',
        'PushALotAPI': '0',
        'PushALotEnabled': '0',
        'PushbulletAPI': '0',
        'PushbulletEnabled': '0',
        'PushoverAPI': 'aa71eqifhiiw6m1acnhvapxuc6bcnr',
        'PushoverUser': 'umjbsyow1nonkg1hv4aystbbrqgpcm',
        'PushoverEnabled': '1',
        'PushsaferAPI': '0',
        'PushsaferImage': '0',
        'PushsaferEnabled': '0',
        'TelegramAPI': '0',
        'TelegramChat': '0',
        'TelegramEnabled': '0',
        'WebLocalNetworks': '192.168.0.2;192.168.0.254;127.0.0.*',
        'WebRemoteProxyIPs': '0',
        'SecPassword': '7365605c495d53cfc5ba1d2ddc7fa1fe',
        'ProtectionPassword': '7365605c495d53cfc5ba1d2ddc7fa1fe',
        'OneWireSensorPollPeriod': '0',
        'OneWireSwitchPollPeriod': '0',
        'IFTTTAPI': '0',
        'WebUserName': 'TXlyaWFkZXM=',
        'WebPassword': '7365605c495d53cfc5ba1d2ddc7fa1fe',
        'ZWaveAeotecBlinkEnabled': '1',
        'MaxElectricPower': '6000',
        'ClickatellFrom': '0'
    })
    if DomSettings():
        print('init done')
    else:
        print('init not done')
    print(DomSettings().PushoverEnabled)
    print(DomSettings().pushoverenabled)
    print(DomSettings().PushoverEnAbled)
    DomSettings.heartbeat()
    print(bool(DomSettings.notifications.pushover))
    print(DomSettings.notifications.pushover)
    print('{}'.format(DomSettings.notifications.pushover))
    print(DomSettings()['PushoverEnabled'])
    print(len(DomSettings.notifications))
