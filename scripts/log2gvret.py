#!/usr/bin/env python
#
# Copyright (c) 2023 Angus Gratton
# SPDX-License-Identifier: MIT OR Apache-2.0

import csv
import sys
import os
import os.path
import re

# Simple script to convert logs written from standard output of the can.logger
# tool in python-can to the GVRET CSV format as used by SavvyCAN.

def main(from_path, to_path):
    if os.path.realpath(from_path) == os.path.realpath(to_path):
        raise RuntimeError(f"from and to are the same file: {from_path}")
    with open(from_path, "r") as fr:
        with open(to_path, "w", newline="") as to:
            writer = csv.writer(to)
            writer.writerow(
                [
                    "Time Stamp",
                    "ID",
                    "Extended",
                    "Bus",
                    "LEN",
                    "D1",
                    "D2",
                    "D3",
                    "D4",
                    "D5",
                    "D6",
                    "D7",
                    "D8",
                ]
            )
            for line in fr:
                m = re.match(
                    r"Timestamp: *([\d\.]+) *ID: *([\da-f]+) *([S]) ([RT]x)? *DLC?: *(\d+) *([\da-f ]{23}) *Channel: c?a?n?(\d)",
                    line,
                )
                if m:
                    timestamp, canid, idtype, _, dlc, data, channel = m.groups()
                    timestamp = int(float(timestamp) * 1e6)  # to microseconds
                    dbytes = [d for d in data.upper().split(" ") if d]
                    extended = idtype != "S"  # bit hacky
                    canid = int(canid, 16)

                    writer.writerow(
                        [timestamp, f"{canid:08X}", str(extended).lower(), channel, dlc]
                        + dbytes
                    )


if __name__ == "__main__":
    for inpath in sys.argv[1:]:
        outpath = os.path.splitext(sys.argv[1])[0] + ".csv"
        if os.path.exists(outpath):
            raise SystemExit(f"Can't convert {inpath} to {outpath}: Destination exists")
        main(inpath, outpath)
