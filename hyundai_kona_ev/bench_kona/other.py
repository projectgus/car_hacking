from message import PeriodicMessage, CounterField
import time

# Mystery PCAN messages. Trying to find the ones which are sent by the gateway about the charge port lock.

MSGS = [
    (
        0x5B3,
        "40,10,FE,30,00,00,00,00",
        5,
    ),  # bit 3 goes 30->00 when charging, bits 0-2 seem to change less but may be fault related (maybe...)
    # (  # is sent by one of the bench Kona modules
    #     0x59C,
    #     "00,00,00,00,00,00,00,00",
    #     10,
    # ),  # only on when IG3 is on, seems all zeroes when not charging
    # (0x59c,
    # '00,00,76,10,fa,00,00,00',
    # 10,
    # ),  # value when charging, last byte starts low and climbs up - maybe this is OBC or CCM related actually?
    (
        0x412,
        "00,00,00,00,00,00,00,00",
        5,
    ),
    (
        0x450,  # DBC says this might encode speed & cruise control buttons(?)
        "00,18,04",
        5,
    ),
    (
        0x45c,
        "00,00,00,00,00,00,00,00",
        5,
    ),
    (
        0x45d,
        "ff,ff,ff,ff,ff,ff,ff,0f",
        5,
    ),
    (
        0x45e,
        "ff,ff,ff,ff,ff,00,00,00",
        5,
    ),
    # (  # is sent by one of the bench Kona modules
    #     0x4e4,
    #     "00,00,71,00,00,00,00,00",
    #     10,
    # ),
    (
        0x55c,
        "07,1F,14,FF,01,00,00,00",
        10,
    ),
    # (  # is sent by one of the bench Kona modules
    #     0x570,
    #     "00,00,85,00,00,00,00,00",  # bunch of values change momentarily at some times
    #     10,
    # ),
    (
        0x5F6,
        "00,00,00,00,00,00,00,00", # goes non-zero for a brief period mid-charge session
        10,
    ),
    (
        0x5F7,
        "00,1A,00,00,00,FF,00,00",  # changes a few times during charge session
        10,
    ),
    (
        0x5F8,
        "89,00,10,10,EC,7C,82,8E",  # probably the AC control unit
        10,
    ),
    (
        0x462,
        "FE,3F,FF,0F,F0,1F,00,00",  # one bit changes 2/3 way through charge session
        50,
    ),
    (
        0x4FE,
        "FF,FF,7F,FF,FF,00,FF,FF",  # unchanging in charge session
        5,
    ),
    (
        0x50d,
        "00,00,30,01,00,00,00,00",  # unchanging in charge session
        5,
    ),
    (
        0x520,
        "00,00,00,00,00,00,00,00", # one bit sets a few times brielfy during charging
        10,
        ),
    (
        0x55f,
        "00,00,00,00,00,00,00,00",  # always zero during charge
        10,
    ),
    (
        0x561,
        "00,00,00,00,00,00,00,00",  # always zero during charge
        10,
    ),
    (
        0x578,
        "00,00,00,00,00,00",  # mostly zero during charge, one byte goes to 0F for 36s
        10,
    ),
    (
        0x588,
        "58,1C,00,00,00,00,00,00",  # first two bytes change a couple of times in charging
        10,
    ),
    (
        0x593,
        "01,08,FF,FF,FF,FF",  # first byte has 3 discrete values over charge log
        5,
        ),
    # (  # in the bench logs already
    #     0x59c,
    #     "00,00,76,10,FA,00,00,00",  # some bytes transition counting up a few times during charge log
    #     10,
    #     ),
    (
        0x5ca,
        "00,00,00,FE,FE,10,00,00",  # value transitions once during charge log
        1,
    ),
    (
        0x5cc,
        "00,0C,00,00,00,00,00,F0",  # value changes a few times during charge log
        1,
    ),
    (
        0x5f9,
        "8B,88,FF,FF,00,1A,00,00",  # value changes quite a bit during charge log, but no counter field
        10,
    ),
]


class UNK_164(PeriodicMessage):
    """???"""

    def __init__(self, car):
        super().__init__(car, 0x164, bytes.fromhex("00080000"), 10)  # actually 100!
        # looks like a counter field in byte 3
        self.counter = CounterField(self.data, 2, 0x1F, delta=0x02)

    def update(self):
        self.counter.update()
        # byte 4 is a sum of the previous bytes
        self.data[3] = sum(self.data[:3]) & 0xFF


class UNK_471(PeriodicMessage):
    """???"""
    # The counter byte here follows this weird sequence...?
    SEQ = ( 0xAC, 0xB0, 0xB4, 0xB8, 0xFC, 0x40, 0x44, 0x48,
            0x8C, 0x50, 0x54, 0x58, 0x9C, 0x60, 0x64, 0x68, )

    def __init__(self, car):
        super().__init__(car, 0x471, bytes.fromhex("1554110000AC"), 50)
        self.seq_idx = 0

    def update(self):
        # byte 5 is a weird counter field
        self.seq_idx = (self.seq_idx + 1) % len(self.SEQ)
        self.data[5] = self.SEQ[self.seq_idx]


class UNK_5F5(PeriodicMessage):
    """???"""

    def __init__(self, car):
        super().__init__(car, 0x5f5, bytes.fromhex("041E002900C1FF1F"), 10)
        # 4-bit counter in byte 4
        self.counter = CounterField(self.data, 4, 0x0F)

    def update(self):
        self.counter.update()
        # byte 4 is a sum of the previous bytes
        self.data[3] = sum(self.data[:3]) & 0xFF
        # the last byte looks like a 5-bit CRC or something. currently not implemented :|


def get_messages(car):
    return [
        PeriodicMessage(car, can_id, bytes.fromhex(data.replace(",", "")), hz)
        for (can_id, data, hz) in MSGS
    ] + [
        k(car)
        for k in globals().values()
        if type(k) == type and k != PeriodicMessage and issubclass(k, PeriodicMessage)
    ]
