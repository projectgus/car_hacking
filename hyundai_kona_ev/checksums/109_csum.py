#!/usr/bin/env python

MESSAGES = [bytes.fromhex(x) for x in [
    "0001FDFFFFFF0F39",
    "0001FDFFFFFF0F17",
    "000100FFFFFF0F0A",
    "000100FFFFFF0F1B",
    "000100FFFFFF0F2C",
    "000100FFFFFF0F3D",
]]

def nibble_sum(x):
    r = 0
    while x:
        r += x & 0x0f
        x = x >> 4
    return r & 0xF

for m_orig in MESSAGES:
    m = bytearray(m_orig)
    print(m.hex())
    m[7] = m[7] & 0xF0

    res = sum(nibble_sum(n) for n in m)

    print(hex(m_orig[7] & 0x0F), hex(res))
