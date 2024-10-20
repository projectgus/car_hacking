#!/usr/bin/env python
lines = open("samples_msg394.csv").read()

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
    cs = m[6] & 0x0F  # 4-bit checksum
    m_[6] = m_[6] & 0xF0 # zero out calculated checksum

    m_ = m_[:7]  # last byte does not seem to be covered by checksum

    res = (~sum(nibble_sum(n) for n in m_) + 1) & 0x0F

    diff_res = (cs - res)
    is_good = res == cs

    if is_good:
        good += 1
    else:
        bad += 1

    print(hex(cs), m.hex(), hex(res), diff_res, is_good)


print("Good checksums ", good, " bad checksums ", bad, " overall ratio ", bad/(good+bad))
