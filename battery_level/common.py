#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""Utilitaires"""

# standards libs
from datetime import datetime
from time import strptime


# Domoticz lib
import Domoticz


def debug(*args: tuple, **kwargs: dict) -> None:
    """Extended debug"""
    for arg in args:
        Domoticz.Debug('{}'.format(arg))
    for key, arg in kwargs.items():
        Domoticz.Debug('{}: {}'.format(key, arg))


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
