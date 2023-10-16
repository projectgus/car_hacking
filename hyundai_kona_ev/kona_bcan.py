#!/usr/bin/env python

import can
import itertools
import time
import argparse

# All of these messages seem to be sent at 5Hz
HZ=5

# Defaults for the constants, can be swapped at runtime(?)
BCAN_CH=0
PCAN_CH=1


class Message(can.Message):
    def __init__(self, arbitration_id, data, channel, hz, update_fn=None):
        super().__init__(arbitration_id, data=data, channel=channel)
        self.hz = hz
        self.delta_t = 1.0 / hz
        self.next_tx = None
        self.update_fn = update_fn

    def check_tx(self, bus):
        now = time.time()
        if self.next_tx is None:
            self.next_tx = now  # First transmit
        if now < self.next_tx:
            return
        if now > self.next_tx + 0.2:
            print(f'WARNING: TX {self.arbitration_id:#x} is {now - self.next_tx}s late')
        bus.send(self)
        if self.update_fn:
            self.update_fn(self)
            self.next_tx += self.delta_t


MSGS = dict(((can_id, Message(can_id,
                              bytes.fromhex(data.replace(',', '')),
                              hz,
                              channel)
            for (can_id, data, hz, channel) in [
                    # BCAN Messages
                    # These are taken from timestamps 370xxxxxx in 221217-2-2021-pcan-bcan-drive-modes.csv
                    # and have removed known SMK message IDs.
                    #
                    # Most don't seem to change a lot, although some change a bit...
                    #
                    # grep ',false,1' 221217-2-2021-pcan-bcan-drive-modes.csv| grep '^370' | grep -v '0000011' | \
                    # grep -v '00000401' | grep -v '00000510' | cut -d, -f2- | sort | sed s/,false,1,8// | sed s/00000/0x/ \
                    # | uniq
                    (0x100, '04,06,00,A0,00,02,80,00', 5, BCAN_CH),  # several bytes change
                    (0x101, '00,00,00,00,00,00,00,10', 5, BCAN_CH),  # byte 1 changes
                    (0x102, '00,00,A0,00,00,00,00,00', 5, BCAN_CH),
                    (0x103, '00,00,00,00,00,00,00,00', 5, BCAN_CH),
                    (0x104, '48,4E,C0,02,00,00,02,40', 5, BCAN_CH),  # byte 6 changes
                    (0x105, '00,00,00,00,08,00,00,00', 5, BCAN_CH),
                    (0x106, '00,00,00,00,00,00,00,00', 5, BCAN_CH),
                    (0x107, '00,00,00,00,2C,C1,C0,00', 5, BCAN_CH),  # byte 5 changes
                    (0x109, '00,00,00,00,00,00,00,00', 5, BCAN_CH),
                    (0x168, '88,00,84,04,C1,B0,40,00', 5, BCAN_CH),
                    (0x169, '00,80,00,00,00,00,40,00', 5, BCAN_CH),
                    (0x16A, '00,00,00,00,00,00,00,00', 5, BCAN_CH),
                    (0x188, '40,50,01,04,00,00,00,00', 5, BCAN_CH),  # bytes 1,2 change
                    (0x189, '00,01,00,00,00,00,00,00', 5, BCAN_CH),  # byte 1 changes
                    (0x18A, '00,00,00,00,00,00,30,00', 5, BCAN_CH),  # byte 6 changes
                    (0x18B, '16,FF,F8,00,00,00,00,00', 5, BCAN_CH),
                    (0x18C, '03,00,00,00,00,00,00,00', 5, BCAN_CH),  # byte 0 changes
                    (0x18D, '00,00,00,00,00,00,00,00', 5, BCAN_CH),
                    (0x18D, '00,00,00,00,00,00,00,0A', 5, BCAN_CH),   # byte 7 and bytes 0-5 all change!
                    (0x18E, 'FF,FF,FF,FF,40,40,00,00', 5, BCAN_CH),   # bytes 4 & 5 change
                    (0x18F, '00,00,00,00,00,00,00,00', 5, BCAN_CH),
                    (0x19B, '00,80,00,00,00,00,00,00', 5, BCAN_CH),
                    (0x1F7, '00,00,00,40,00,00,00,00', 5, BCAN_CH),  # byte 3 changes 00/40
                    (0x1FA, '00,00,00,00,00,00,00,00', 5, BCAN_CH),  # byte 0,1 change sometimes?
                    (0x400, '01,02,00,00,00,00,FF,FF', 5, BCAN_CH),
                    (0x416, '1E,02,00,00,00,00,FF,FF', 5, BCAN_CH),
                    (0x41E, '00,12,00,00,00,00,FF,FF', 5, BCAN_CH),
                    (0x588, '00,00,00,00,00,00,18,00', 5, BCAN_CH),  # bytes 0,6 change
                    (0x589, '00,00,00,7F,FF,00,00,00', 5, BCAN_CH),
                    (0x59D, '64,60,60,00,00,00,00,00', 5, BCAN_CH),

                    # PCAN IEB messages
            ]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bus", type=int, default=0)

    args = parser.parse_args()

    bus = can.Bus(channel=args.bus, bitrate=500_000)

    print('"Emulating" BCAN..')

    tdelta = (1.0 / HZ) / len(MSGS)
    next_send = time.time()
    send_from = itertools.cycle(MSGS.values())
    while True:
        if time.time() >= next_send:
            bus.send(next(send_from))
            next_send += tdelta
            r = bus.recv(max(0.0, next_send - time.time()))
        if r:
            print(r)
            if r.arbitration_id in MSGS:
                print(f'WARNING: {r.arbitration_id:#x} ID received and sent')


if __name__ == "__main__":
    main()
