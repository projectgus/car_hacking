#!/usr/bin/env python
import can
import time
import sys
import struct
import datetime

# Based on work Copyright (c) 2019 Simp ECO Engineering, additions Copyright 2022 Angus Gratton
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause

class CMU(object):
    def __init__(self, cmu_id):
        self.cmu_id = cmu_id
        self.byte1 = -1
        self.balancing = [ False ] * 8
        self.voltages = [ -1 ] * 8
        self.temps = [ -1 ] * 3
        self.last_update = None

    def update(self, msg):
        sub_id = msg.arbitration_id & 0x0f
        data = msg.data
        if sub_id == 1:
            if data[0] != 0:
                print(f"NON-ZERO BALANCE STATUS {data[0]}")
            self.balancing = [ (data[0] & 1 << n) != 0 for n in range(8) ]  # check indexing here! also, seems 0x0d is set on startup?
            self.byte1 = data[1]
            raw_temps = struct.unpack(">HHH", data[2:])
            self.temps = [rt/1000 for rt in raw_temps]
        elif sub_id in (2,3):
            base = 0 if (sub_id == 2) else 4
            raw_voltages = struct.unpack(">HHHH", data)
            self.voltages[base:base+4] = [ rv/1000 for rv in raw_voltages]
        elif sub_id == 4:
            pass  # TODO: possibility CMU has more taps populated
        else:
            raise RuntimeError(f"Invalid arbitration_id {msg.arbitration_id}")
        self.last_update = datetime.datetime.now()

    def print(self, file=sys.stdout):
        print(f'CMU ID {self.cmu_id} - last updated {self.last_update}', file=file)
        print(f'Byte 1 {self.byte1}' ,file=file)
        print(f'Temps {self.temps[0]} {self.temps[1]} {self.temps[2]}', file=file)
        print('Voltages:', file=file)
        for v,b in zip(self.voltages, self.balancing):
            msg = "Balancing" if b else ""
            print(f'{v} {msg}', file=file)
        print(f'Module voltage {sum(self.voltages):.3f}', file=file)


def can_balance_msg(balance_voltage=0.0, enable_balance=False, force_balance=False):
    if force_balance:
        # https://www.diyelectriccar.com/threads/mitsubishi-miev-can-data-snooping.179577/page-2#post-1066826
        balance_level = 2
    elif enable_balance:
        balance_level = 1
    else:
        balance_level = 0
    txdata = struct.pack(">HBBBxxx", int(balance_voltage * 1000) if enable_balance else 0xf3d,
                         balance_level,
                         4, 3)  # last two are magic numbers, some code uses 4,3 here???
    return can.Message(arbitration_id=0x3c3, data=txdata, is_extended_id=False)


def test_cmu(bus, balance_to_min=False):
    txmsg = can.Message(arbitration_id=0x3c3, data=[0,0,0,0,0,0,0,0],
                        is_extended_id=False)
    last_tx = time.time()
    last_print = datetime.datetime.now()
    cmus = {}
    while True:
        if cmus and time.time() - last_tx > 0.040:
            balance_voltage = min(min(cmu.voltages) for cmu in cmus.values())
            txmsg = can_balance_msg(balance_voltage, balance_to_min)
            bus.send(txmsg)
            last_tx = time.time()
        msg = bus.recv(0)
        if msg and 0x600 <= msg.arbitration_id < 0x700:
            cmu_id = (msg.arbitration_id & 0xf0) >> 4  # indexing from 1, same as Mitsubishi does
            if cmu_id not in cmus:
                cmus[cmu_id] = CMU(cmu_id)
            cmus[cmu_id].update(msg)
        elif msg:
            print(msg)
        PRINT_EVERY = datetime.timedelta(seconds=1)
        if datetime.datetime.now() - last_print > PRINT_EVERY:
            for cmu in cmus.values():
                if cmu.last_update > last_print:
                    cmu.print()
            last_print = datetime.datetime.now()



