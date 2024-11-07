#!/usr/bin/env python
#
# Copyright (c) 2023 Angus Gratton
# SPDX-License-Identifier: MIT OR Apache-2.0
import base64
import sys
import csv
import os
import os.path

# Simple script to convert logs written from the can.io.CSVWriter() log format
# of python-can (non-standard, I think?) into the GVRET CSV format as used by
# SavvyCAN.


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

            reader = csv.reader(fr)
            next(reader)  # ignore header
            for (timestamp, canid, extended, _remote,
                 error, dlc, data) in reader:
                bus = 0  # this CSV format doesn't distinguish
                timestamp = int(float(timestamp) * 1e6)  # to microseconds
                data = ["{:02X}".format(b) for b in base64.b64decode(data)]
                extended = str(extended == "1").lower()
                canid = "{:08X}".format(int(canid, 0))
                writer.writerow([timestamp, canid, extended, bus, dlc] + data)


if __name__ == "__main__":
    inpath = sys.argv[1]
    try:
        outpath = sys.argv[2]
    except IndexError:
        outpath = os.path.splitext(sys.argv[1])[0] + "_savvy.csv"
    main(inpath, outpath)
