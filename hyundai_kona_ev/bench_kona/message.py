from asyncio import sleep
import can
import time
from can.typechecking import CanData, Channel
from typing import Optional

PCAN_CH = "can0"

DEFAULT_CHANNEL = PCAN_CH


class PeriodicMessage(can.Message):
    """Periodic transmitted CAN message.

    Constructor takes same arguments as can.Message plus a frequency in Hz"""

    def __init__(
        self,
        car,
        arbitration_id: int,
        data: CanData,
        frequency: int,
        channel: Optional[Channel] = None,
    ):
        super().__init__(
            arbitration_id=arbitration_id,
            data=data,
            is_extended_id=False,
            is_rx=False,
            channel=channel,
        )
        if channel is None:
            self.channel = DEFAULT_CHANNEL
        self.frequency = frequency
        self.delta = 1.0 / frequency  # seconds
        self.car = car
        self.enabled = True

    def __repr__(self):
        return (
            f"PeriodicMessage(arbitration_id={self.arbitration_id:#x}, "
            f"dlen={len(self.data)}, data={self.data.hex()}, "
            f"frequency={self.frequency}, "
            f"channel={self.channel})"
        )

    def update(self):
        """If message needs any fields in self.data (or other content) updated
        each time it sends, then override this function in a subclass.
        """
        pass

    def set_enabled(self, value):
        self.enabled = value
        print(f"Message {hex(self.arbitration_id)} enabled = {value}")

    async def coro(self, bus: can.BusABC, can_logfile):
        await sleep(self.delta)  # staggered start to avoid overloading the bus
        next_tx = time.time()
        while True:
            if self.enabled:
                self.update()
                print(self, file=can_logfile)
                try:
                    bus.send(self, timeout=0.025)
                except can.CanError as e:
                    print(f"ID {self.arbitration_id:#x} ({self.frequency}Hz) failed to send: {e}")
                next_tx += self.delta
            await sleep(max(0, next_tx - time.time()))


def ffs(x):
    """Returns the index, counting from 0, of the
    least significant set bit in `x`.

    Cribbed from https://stackoverflow.com/a/36059264/1006619
    """
    return (x & -x).bit_length() - 1


class CounterField:
    """Little convenience class to wrap a counter field in a bytearray."""

    def __init__(
        self,
        target: bytearray,
        byte_idx: int,
        bitmask: int,
        delta: int = -1,
        skip: Optional[int] = None,
    ):
        self.target = target
        self.idx = byte_idx
        self.bitmask = bitmask
        self.shift = ffs(bitmask)
        self.delta = delta
        self.skip = skip

    def get(self):
        return (self.target[self.idx] & self.bitmask) >> self.shift

    def set(self, new):
        v = self.target[self.idx] & ~self.bitmask
        self.target[self.idx] = v | ((new << self.shift) & self.bitmask)

    def update(self):
        c = self.get()
        c = (c + self.delta) & (self.bitmask >> self.shift)
        if c == self.skip:
            # repeat the counter step if we hit the 'skip' value
            c = (c + self.delta) & (self.bitmask >> self.shift)
        self.set(c)
