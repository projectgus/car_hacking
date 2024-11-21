#!/usr/bin/env python

# All the discrete values of the first 3 bytes in the message
VALUES = [
    bytes([0xA8, 0x0A, 0x57]), # maybe the startup glitch values, maybe not valid
    bytes([0xAA, 0x0A, 0x55]), # no button being pressed
    bytes([0x6A, 0x0A, 0x95]), # pressing D
    bytes([0x9A, 0x0A, 0x65]), # pressing N
    bytes([0xA6, 0x0A, 0x59]), # pressing R
    bytes([0xA9, 0x0A, 0x56]), # pressing P
    ]

for v in VALUES:
    print(v[0], hex(~v[0] & 0xFF), hex(v[2]))
