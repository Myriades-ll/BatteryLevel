#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""JSON/API requests"""

# standard libs
from collections import deque
from collections.abc import Sized
from typing import Optional

# local libs
from battery_level.common import debug


class Requests(Sized):
    """Queue FIFO des requètes JSON API"""
    _queue = deque()
    _last_in_datas = {}
    _last_out_datas = {}

    @classmethod
    def add(cls, verb: str, url: str) -> None:
        """Ajoute un élément à la queue"""
        cls._last_in_datas = {
            "Verb": verb,
            "URL": url
        }
        cls._queue.append(cls._last_in_datas)
        debug('Ajout: {} ({})'.format(
            cls.last_in(),
            cls.__str__()
        ))

    @classmethod
    def get(cls) -> dict:
        """Renvoie le premier élément inséré dans la queue"""
        cls._last_out_datas = cls._queue.popleft()
        debug('Sortie: {} ({})'.format(
            cls.last_out(),
            cls.__str__()
        ))
        return cls._last_out_datas

    @classmethod
    def last_in(cls) -> Optional[dict]:
        """Renvoie le dernier élément inséré"""
        return cls._last_in_datas

    @classmethod
    def last_out(cls) -> Optional[dict]:
        """Renvoie le dernier élément sorti"""
        return cls._last_out_datas

    @classmethod
    def __bool__(cls) -> bool:
        """[return]: False if empty, else True"""
        return cls.__len__() > 0

    @classmethod
    def __len__(cls) -> bool:
        """[return]: size of queue"""
        return len(cls._queue)

    @classmethod
    def __repr__(cls) -> str:
        """Wrapper pour repr()"""
        return cls.__str__()

    @classmethod
    def __str__(cls) -> str:
        """Wrapper pour str()"""
        return '{} requests still in queue'.format(cls.__len__())
