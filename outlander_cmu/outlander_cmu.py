#!/usr/bin/env python
import can
import time
import struct
import datetime

# Based on work Copyright (c) 2019 Simp ECO Engineering, additions Copyright 2022 Angus Gratton
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause

class CMU(object):
    def __init__(self, cmu_id):
        self.cmu_id = cmu_id
        self.byte1 = None  # what is this?
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

    def print(self):
        print(f'CMU ID {self.cmu_id} - last updated {self.last_update}')
        print(f'Byte 1 {self.byte1}')
        print(f'Temps {self.temps[0]} {self.temps[1]} {self.temps[2]}')
        print('Voltages:')
        for v,b in zip(self.voltages, self.balancing):
            msg = "Balancing" if b else ""
            print(f'{v} {msg}')
        print(f'Module voltage {sum(self.voltages):.3f}')

def test_cmu(bus):
    txmsg = can.Message(arbitration_id=0x3c3, data=[0,0,0,0,0,0,0,0],
                        is_extended_id=False)
    last_tx = time.time()
    last_print = 0.0
    cmus = {}
    while True:
        if cmus and time.time() - last_tx > 1.0:
            balance_voltage = min(min(cmu.voltages) for cmu in cmus.values())
            if balance_voltage > 0:
                balance_voltage = 3.6
                txmsg.data = struct.pack(">HBBBxxx", int(balance_voltage * 1000), 0, 4, 3)  # 4,3 are magic numbers?
                print(f"Balance to {balance_voltage}    {txmsg}")
            else:
                txmsg.data = [ 0 ] * 8
            assert len(txmsg.data) == 8
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
        if time.time() - last_print > 2.0:
            for cmu in cmus.values():
                cmu.print()
            last_print = time.time()



