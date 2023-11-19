#!/usr/bin/env python
#
import asyncio
import can
import datetime
from can.notifier import MessageRecipient
from typing import List

from message import PCAN_CH, BCAN_CH
import bcan, ieb, srscm

async def rx_coro(bus: can.BusABC):
    """Receive from the CAN bus and log whatever it sends us."""
    reader = can.AsyncBufferedReader()
    logger = can.Logger(f"{datetime.datetime.now().isoformat()}-bench_kona.csv")

    listeners: List[MessageRecipient] = [
        reader,  # AsyncBufferedReader() listener
        logger,  # Regular Listener object
    ]
    notifier = can.Notifier(bus, listeners, loop=asyncio.get_running_loop())

    try:
        while True:
            m = await reader.get_message()
            print(m)
    finally:
        notifier.stop()


async def main():
    messages = []
    for mod in (bcan, ieb, srscm):
        messages += mod.get_messages()

    print(messages)

    bus = can.Bus(channel=(PCAN_CH, BCAN_CH))

    # gather creates a task for each coroutine
    await asyncio.gather(rx_coro(bus), *(m.coro(bus) for m in messages))


if __name__ == "__main__":
    asyncio.run(main())

