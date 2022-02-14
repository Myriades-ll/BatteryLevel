# Battery Level

This is a [Domoticz](https://www.domoticz.com/) plugin.

[Still in developpement]

## Features

* create one device for every hardware/devices in use
* define empty level
  * icon change on four ranges (0 <--> 25 <--> 50 <--> 75 <--> 100; % of empty level)
* dynamically adds every devices newly added
* detect device down

## Automation (options)

* marks every device as used at device creation
* add notification at device creation
* create location with sorting system for fast access:
  * by percentage then name
  * 3 sorting way: ascending, none or descending

## Tested over

* RPi4 with RaspiOS (buster) - Domoticz 2021.1/2022.1 - Python 3.7.3

## TIPS

Only devices in use are considered.

Hardwares that holding multiple devices are grouped as they have the same battery; only zwave at the moment, this will be improved.

The plugin tries to make sensed names on hardwares that hold multiples sensors (like zwave one's). Try to name your devices as same as possible. Eg:

* Dad's room - luminosity
* Dad's room - motion

This will result in a single device named:

* Dad's room

Further, you will still able to rename your devices handly.
