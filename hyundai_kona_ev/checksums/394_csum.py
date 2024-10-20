#!/usr/bin/env python
import operator
from functools import reduce
#from crccheck.crc import Crc8Autosar as Crc8
import crcmod
lines = open("samples_msg394.csv").read()


hyundai_checksum = crcmod.mkCrcFun(0x11D, initCrc=0xFD, rev=False, xorOut=0xdf)

msgs = []
for l in lines.split("\n"):
    if l:
        msgs.append(bytes.fromhex("".join(l.split(",")[5:])))


def nibble_sum(x):
    r = 0
    while x:
        r += x & 0x0f
        x = x >> 4
    return r & 0xF

def nibble_xor(x):
    r = 0
    while x:
        r ^= x & 0x0f
        x = x >> 4
    return r

def nibble_sub(x):
    r = 0
    while x:
        r -= x & 0x0f
        x = x >> 4
    return r & 0xF

def sum_inverse(x):
    r = 0
    for n in x:
        r += n ^ 0xFF
    return r

last_m = None
r = dict()
for m in msgs:
    m_ = bytearray(m)
    m_[6] = m_[6] & 0xF0

    m_ = m_[:7]

    as_sum = reduce(operator.add, m_, 0)
    as_xor = reduce(operator.xor, m_, 0)
    as_sub = reduce(operator.sub, m_, 0x10000000)

    cs = m[6] & 0x0F
    counter = m[1] >> 4

    if last_m is not None:
        diff = bytes((a^b) for (a,b) in zip(m, last_m))
        res = ~sum(m_) & 0xFFFFFF

        calc_cs = (res & 0xF0) >> 4

        if res & 0x0F >= 0xd:
            calc_cs += (res & 0x0F) - 0xd
        else:
            calc_cs += (res & 0x0F) + 2

        # About 1% of results still don't match, almost all of these are where 'res' ends in 0xc
        # and this method is off by one.
        #
        # Less than 0.001% of other results don't match, maybe due to actual on the wire errors?
        #
        # For some non-matching results, the initial sum value is the same as a
        # different correct packet but the checksum on the wire is different...

        diff_res = (cs - calc_cs)
        if res & 0x0f == 0xc:
            print(hex(cs), m.hex(), hex(res), hex(calc_cs), diff_res, calc_cs & 0xf == cs)

    last_m = m
    continue

    if cs == 0x0:
        print(
            hex(cs),
            "%03x" % as_sum,
            "%03x" % as_xor,
            hex(as_sub),
            hex(nibble_sum(as_sum)),
            hex(nibble_sum(as_xor)),
            hex(nibble_sum(as_sub)),
            hex(nibble_xor(as_sum)),
            hex(nibble_xor(as_xor)),
            hex(nibble_xor(as_sub)),
            hex(nibble_sub(as_sum)),
            hex(nibble_sub(as_xor)),
            hex(nibble_sub(as_sub)),
            )
