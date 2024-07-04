from message import PeriodicMessage


class ACU_5A0(PeriodicMessage):
    """ Low duty cycle airbag/SRS status message.
    """
    def __init__(self, car):
        super().__init__(car,
                         0x5a0,
                         bytearray.fromhex('000000C025029101'),
                         1)


def get_messages(car):
    return [k(car) for k in globals().values()
            if type(k) == type
            and k != PeriodicMessage
            and issubclass(k, PeriodicMessage)]
