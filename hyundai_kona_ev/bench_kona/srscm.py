from message import PeriodicMessage, PCAN_CH


class ACU_5A0(PeriodicMessage):
    """ Low duty cycle airbag/SRS status message.
    """
    def __init__(self):
        super().__init__(0x5a0,
                         bytearray.fromhex('000000C025029101'),
                         1,
                         PCAN_CH)


def get_messages():
    for k in globals().values():
        if type(k) == type and issubclass(k, PeriodicMessage):
            print(k)

    return [k() for k in globals().values()
            if type(k) == type
            and k != PeriodicMessage
            and issubclass(k, PeriodicMessage)]
