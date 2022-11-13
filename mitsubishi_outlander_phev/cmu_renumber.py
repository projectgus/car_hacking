#!/usr/bin/env python
#
# Copyright 2022 Angus Gratton
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause

import argparse
import serial
import struct
import time

# 2 bits per ID slot in the packet
ID_KEPT = 0b01
ID_NEW = 0b10
ID_MASK = 0b11

# w = bytes([0x00, 0x00, 0x00, 0x00, 0x00])  # first module sets ID1
# w = bytes([0x00, 0x01, 0x00, 0x00, 0x01])  # result of above, sets ID2
# w = bytes([0x00, 0x09, 0x00, 0x00, 0x09])  # result of above, sets ID3, returns 0029000029
# w = bytes([0x00, 0x09, 0x00, 0x00, 0x09]) # sent again, no change, returns 0019000019

# Setting ID "6" yields ID 7
# Read: Timeout
# Write: 0055010056
# Read: 005509005e

# When not changing it:
# Read: Timeout
# Write: 0055010056
# Read: 005505005a

# Setting ID "9" aka CMU10
# Read: Timeout
# Write: 00555500aa
# Read: 00555502ac

# Setting ID "10" aka CMU11
# Read: 00555509b3
# Write: 00555501ab
# Read: Timeout
# Write: 00555501ab
# Read: 00555505af

# Trying to set ID "11" aka CMU12
#Write: 00555505af
#Read: 00555535df
#WARNING: Unexpected sequence for id 11: 0b11
#Write: 00555505af
#Read: 00555535df
#WARNING: Unexpected sequence for id 11: 0b11





def open_port(port):
    return serial.Serial(
        port,
        baudrate=1200,
        parity="E",
        stopbits=1.5,
        timeout=0.5
    )

def renumber_packet_starting_from(first_id=1):
    return renumber_packet_with(tuple(range(1, first_id)))


def renumber_packet_with(ids_in_use=()):
    as_num = 0
    for i in ids_in_use:
        as_num |= ID_KEPT << ((i - 1) * 2)
    assert as_num < 1 << 24  # 3 bytes max
    as_bytes = struct.pack("I", as_num)[:3]
    csum = sum(b for b in as_bytes) & 0xFF
    return b"\x00" + as_bytes + bytes([csum])


def decode_result_packet(pkt):
    # Returns a tuple of ((ids kept), (new ids))
    if len(pkt) != 5:
        raise ValueError(f"Expected 5 bytes not {pkt.hex()}")
    if pkt[0] != 0:
        raise ValueError(
            f"Expected first byte of {pkt.hex()} to be 00. Different algorithm?"
        )
    as_bytes = pkt[1:4]

    calc_csum = sum(b for b in as_bytes) & 0xFF
    if pkt[4] != calc_csum:
        raise ValueError(
            f"Calculated checksum {calc_csum} doesn't match packet {pkt.hex()}"
        )

    as_num = struct.unpack("I", as_bytes + b"\x00")[0]
    new_ids = []
    kept_ids = []
    for i in range(1, 13):
        shift = (i - 1) * 2
        v = (as_num >> shift) & ID_MASK
        if v == ID_KEPT:
            kept_ids.append(i)
        elif v == ID_NEW:
            new_ids.append(i)
        elif v:
            print(f'WARNING: Unexpected sequence for id {i}: {bin(v)}')

    return (tuple(kept_ids), tuple(new_ids))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="/dev/ttyUSB0")
    parser.add_argument("--first-id", default=1, type=int)

    args = parser.parse_args()

    print(f"Opening {args.port}...")
    s = open_port(args.port)

    print(f"Renumbering from {args.first_id}...")
    pkt = renumber_packet_starting_from(args.first_id)
    kept = None
    new = None
    for _tries in range(3):
        print(f"OUT: {pkt.hex()}")
        s.write(pkt)
        r = s.read(5)
        if not r:
            print('Timeout')
        else:
            print(f" IN: {r.hex()}")
            if r:
                try:
                    kept, new = decode_result_packet(r)
                    break
                except ValueError as e:
                    print(f"Failed to decode: {e}")
            print("Will retry...")
            time.sleep(2)


    if kept is None:
        raise SystemExit('Failed to renumber')
    print("Kept existing IDs: {}".format(", ".join(str(k) for k in kept)))
    print("New IDs written: {}".format(", ".join(str(n) for n in new)))


if __name__ == "__main__":
    main()
