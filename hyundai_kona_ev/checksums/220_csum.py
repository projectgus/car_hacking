#!/usr/bin/env python
import operator
from functools import reduce
#from crccheck.crc import Crc8Autosar as Crc8
import crcmod
lines = open("temp_msg220.csv").read()


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

good = 0
bad = 0

for m in msgs:
    m_ = bytearray(m)
    cs = m[7] & 0x0F  # 4-bit checksum
    m_[7] = m_[7] & 0xF0 # zero out calculated checksum

    #res = (sum(nibble_sum(n) for n in m_) + 1)
    res = sum(m_) & 0x0F ^ 0x9

    diff_res = (cs - res)
    is_good = res == cs

    if is_good:
        good += 1
    else:
        bad += 1

    print(hex(cs), m_.hex(), m.hex(), hex(res), diff_res, is_good)


print("Good checksums ", good, " bad checksums ", bad, " overall ratio ", bad/(good+bad))
