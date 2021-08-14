#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# pylint:disable=line-too-long
"""Domoticz Python plugin for monitoring and logging for every device that provide battery level

Idea inspired from: https://github.com/999LV/BatteryLevel

Icons are from wpclipart.com. many thanks to them for these public domain graphics:

Versions:
    1.0: first release

<plugin key="pyBattLev" name="Battery monitoring for all devices" author="Myriades" version="1.0">
    <description>
        <h2>Battery Level python plugin</h2>
        <h3>Options</h3>
        <h4>Empty level:</h4>
        <p>The value from which you consider a battery empty. This value is also used for treshold notification and bounce system reset.</p><br/>
        <h4>Use every devices:</h4>
        <p>Automatically marks every device created by the plugin as used.</p><br/>
        <h4>Add notification:</h4>
        <p>Automatically add notification for every created device.</p><br/>
        <h4>View name:</h4>
        <p>Automatically add a plan view and add every used device in it.</p><br/>
        <h4>Sort devices:</h4>
        <p>Devices can be sorted in plan view.<br/>
        None makes no sort.<br/>
        Other ways, devices are first sort by percentage, then name; either ascending or descending.</p>
    </description>
    <params>
        <param field="Mode1" label="Empty level (%)" width="40px" required="true" default="25" />
        <param field="Mode2" label="Use every device">
            <options>
                <option label="Yes" value="1" default="true" />
                <option label="No" value="0" />
            </options>
        </param>
        <param field="Mode3" label="Add notification">
            <options>
                <option label="Yes" value="1" default="true" />
                <option label="No" value="0" />
            </options>
        </param>
        <param field="Mode4" label="View name" width="100px" default="Batteries" />
        <param field="Mode5" label="Sort devices">
            <options>
                <option label="Ascending" value="1" default="true" />
                <option label="None" value="-1" />
                <option label="Descending" value="0" />
            </options>
        </param>
        <param field="Mode6" label="Debugging">
            <options>
                <option label="Nothing" value="0" default="true"/>
                <option label="All" value="1" />
                <option label="Plugin" value="2" />
            </options>
        </param>
    </params>
</plugin>
"""
# pylint:enable=line-too-long


# local lib
import battery_level
from pluginhelper.settings.system.interface import Interface

WRAPPER = battery_level.Wrapper()


def onStart() -> None:  # pylint: disable=invalid-name
    """Démarrage du plugin"""
    # pylint: disable=undefined-variable
    battery_level.PluginConfig(Parameters)
    battery_level.Images(Images)
    battery_level.Devices(Devices)
    Interface(Settings)
    WRAPPER.on_start()
    # pylint: enable=undefined-variable


def onStop() -> None:  # pylint: disable=invalid-name
    """onStop"""
    WRAPPER.on_stop()


def onConnect(*args) -> None:  # pylint: disable=invalid-name
    """onConnect"""
    WRAPPER.on_connect(*args)


def onMessage(*args) -> None:  # pylint: disable=invalid-name
    """onMessage"""
    WRAPPER.on_message(*args)


def onCommand(*_args) -> None:  # pylint: disable=invalid-name
    """onCommand"""


def onNotification(*_args) -> None:  # pylint: disable=invalid-name
    """onNotification"""


def onDisconnect(*_args) -> None:  # pylint: disable=invalid-name
    """onDisconnect"""


def onHeartbeat() -> None:  # pylint: disable=invalid-name
    """onHeartbeat"""
    WRAPPER.on_heartbeat()


def onDeviceModified(*args) -> None:  # pylint: disable=invalid-name
    """onDeviceModified"""
    WRAPPER.on_device_modified(*args)


def onDeviceRemoved(*args) -> None:  # pylint: disable=invalid-name
    """onDeviceModified"""
    WRAPPER.on_device_removed(*args)
