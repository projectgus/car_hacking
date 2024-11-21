#!/usr/bin/env python
#
# Very simple CAN logger that writes output to stdout in the GVRET CSV format
# (can be piped to 'tee' or redirected to a file, etc.)
#
# Command line args are the python-can buses to log. python-can config file can be
# used to set baud rate, etc.
#
# Passing a single bus name argument makes a simple CAN logger.
#
# Passing multiple bus name arguments makes a bridged CAN logger. Messages
# received on one bus are forwarded to all other buses. The log indicates which
# bus the message was received on. This can allow splitting a working CAN
# network into multiple parts to identify the source of messages.
#
# Copyright (c) 2024 Angus Gratton
# SPDX-License-Identifier: MIT OR Apache-2.0
import asyncio
import can
import sys
from typing import List

async def main(bus_names: List[str] ):
    buses = [can.Bus(name) for name in bus_names]
    notifiers = [bridge_bus(b, buses) for b in buses]

    print("Time Stamp,ID,Extended,Bus,LEN,D1,D2,D3,D4,D5,D6,D7,D8")

    # run indefinitely processing all the notifiers
    pending = asyncio.all_tasks()
    await asyncio.gather(*pending)

    for n in notifiers:  # probably unreachable
        n.stop()


def print_message(msg: can.Message, index: int):
    ts = int(msg.timestamp * 1e6)
    can_id = format(msg.arbitration_id, "08X")
    extended = "true" if msg.is_extended_id else "false"
    bus = index
    data = ",".join(format(d, "02X") for d in msg.data)
    print(f"{ts},{can_id},{extended},{bus},{msg.dlc},{data}")


def bridge_bus(bus: can.BusABC, buses: List[can.BusABC]):
    index = buses.index(bus)
    other_buses = [b for b in buses if b != bus]

    reader = can.AsyncBufferedReader()
    listeners: List[can.MessageRecipient] = [reader]

    def on_message(msg: can.Message):
        print_message(msg, index)
        for b in other_buses:
            try:
                b.send(msg)
            except can.CanOperationError:
                print(f"Failed to bridge onto bus {b}", file=sys.stderr)

    notifier = can.Notifier(bus, listeners, loop=asyncio.get_running_loop())
    notifier.add_listener(on_message)

    return notifier


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
