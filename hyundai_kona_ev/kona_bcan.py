#!/usr/bin/env python

import can
import itertools
import time
import argparse

# All of these messages seem to be sent at 5Hz
HZ=5


# These are taken from timestamps 370xxxxxx in 221217-2-2021-pcan-bcan-drive-modes.csv
# and have removed known SMK message IDs.
#
# Most don't seem to change a lot, although some change a bit...
#
# grep ',false,1' 221217-2-2021-pcan-bcan-drive-modes.csv| grep '^370' | grep -v '0000011' | \
# grep -v '00000401' | grep -v '00000510' | cut -d, -f2- | sort | sed s/,false,1,8// | sed s/00000/0x/ \
# | uniq
MSGS = dict(((can_id, can.Message(arbitration_id=can_id,
                                  data=bytes.fromhex(data.replace(',', ''))))
             for (can_id, data) in [
                     (0x100, '04,06,00,A0,00,02,80,00'),  # several bytes change
                     (0x101, '00,00,00,00,00,00,00,10'),  # byte 1 changes
                     (0x102, '00,00,A0,00,00,00,00,00'),
                     (0x103, '00,00,00,00,00,00,00,00'),
                     (0x104, '48,4E,C0,02,00,00,02,40'),  # byte 6 changes
                     (0x105, '00,00,00,00,08,00,00,00'),
                     (0x106, '00,00,00,00,00,00,00,00'),
                     (0x107, '00,00,00,00,2C,C1,C0,00'),  # byte 5 changes
                     (0x109, '00,00,00,00,00,00,00,00'),
                     (0x168, '88,00,84,04,C1,B0,40,00'),
                     (0x169, '00,80,00,00,00,00,40,00'),
                     (0x16A, '00,00,00,00,00,00,00,00'),
                     (0x188, '40,50,01,04,00,00,00,00'),  # bytes 1,2 change
                     (0x189, '00,01,00,00,00,00,00,00'),  # byte 1 changes
                     (0x18A, '00,00,00,00,00,00,30,00'),  # byte 6 changes
                     (0x18B, '16,FF,F8,00,00,00,00,00'),
                     (0x18C, '03,00,00,00,00,00,00,00'),  # byte 0 changes
                     (0x18D, '00,00,00,00,00,00,00,00'),
                     (0x18D, '00,00,00,00,00,00,00,0A'),   # byte 7 and bytes 0-5 all change!
                     (0x18E, 'FF,FF,FF,FF,40,40,00,00'),   # bytes 4 & 5 change
                     (0x18F, '00,00,00,00,00,00,00,00'),
                     (0x19B, '00,80,00,00,00,00,00,00'),
                     (0x1F7, '00,00,00,40,00,00,00,00'),  # byte 3 changes 00/40
                     (0x1FA, '00,00,00,00,00,00,00,00'),  # byte 0,1 change sometimes?
                     (0x400, '01,02,00,00,00,00,FF,FF'),
                     (0x416, '1E,02,00,00,00,00,FF,FF'),
                     (0x41E, '00,12,00,00,00,00,FF,FF'),
                     (0x588, '00,00,00,00,00,00,18,00'),  # bytes 0,6 change
                     (0x589, '00,00,00,7F,FF,00,00,00'),
                     (0x59D, '64,60,60,00,00,00,00,00'),
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
