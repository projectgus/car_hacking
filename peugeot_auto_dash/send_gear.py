# MicroPython code
#
# Copyright 2022 Angus Gratton
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
#
# Send ZF 4HP20 compatible single wire display signals to dash with selected
# gear info.
#
# Based on factual protocol description in Citroen Xantia/XM 4HP20 documentation.
#
# Tested on a Peugeot 406 "D8.5" auto dash, connected to dash wire 8480 via an NPN
# transistor.

import time
import esp32
from machine import Pin

rmt = esp32.RMT(0, pin=Pin(25), clock_div=80)


def send_gear(rmt, gear, snow=False, sport=False, err=False):
    gear_bits = {
        "P": 0b0000,
        "R": 0b0001,
        "N": 0b0010,
        "D": 0b0011,
        "3": 0b0100,
        "2": 0b0101,
        "1": 0b0110,
        "P*": 0b0111,  # * == flashing
        "R*": 0b1000,
        "N*": 0b1001,
        "": 0b1100,  # blank display
        "3*": 0b1101,
        "2*": 0b1110,
        "1*": 0b1111,
    }[gear]

    print("Switching to {}".format(gear))
    bits = [
        False,
        gear_bits & 8,
        gear_bits & 4,
        gear_bits & 2,
        gear_bits & 1,
        not gear_bits & 1,
        snow,
        sport or snow,
        False,
        err,
        not err,
        False,
    ]
    assert len(bits) == 12  # 10 data bits, start, stop
    bits += [
        True
    ] * 10  # gap between packets, in theory 6-15 bit periods but dash fussy about exact gap

    bits = [not x for x in bits]  # invert, NPN transistor driver

    rmt.loop(False)
    bp = 10e-3
    bp = int(rmt.source_freq() / rmt.clock_div() * bp)
    assert 1 < bp < 32768
    rmt.loop(True)
    rmt.write_pulses(bp, bits)


for (snow, sport) in [(False, False), (True, False), (False, True)]:
    for g in ["P", "R", "N", "D", "3", "2", "1", "2", "3", "D", "N", "R", "P"]:
        send_gear(rmt, g, snow=snow, sport=sport)
        time.sleep(1)
