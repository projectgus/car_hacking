#!/usr/bin/env -S python -u
import can
import cantools
import numpy
import time
import random
import re
import serial
import threading

EXPECTED = {
    # Status message when no lights are on and P button is not being pressed
    0x197: (bytearray([0x03, 0x07, 0x0e, 0xc0, 0x00, 0x00, 0x00, 0x00]),
            ),
    # Heartbeat. Byte 4 is 1 on PTCAN and 2 on PTCAN-2
    0x55e: (bytearray([0x00, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x5e]),
            bytearray([0x00, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x5e]),
            ),
    # Some kind of other message? Comes out randomly
#    0x65e: (bytearray(b'\xf0\x10\x0a\x62\x17\x04\xe0\x94'),  #  <-- this one most common I think
#            bytearray(b'\xf0\x10\x11\x62\x17\x04\xe0\x94'),  # <-- next most common
#            bytearray(b'\xf0\x10\x18\x62\x17\x04\xe0\x94'),
#            ),  # <-- only seen once
}

# Ignore bytes in the sequence before this index (for the status counter bytes)
EXPECT_FROM = { 0x197: 2, 0x55e: 0, 0x65e: 0 }

TIMEOUT = 0.05

def main():
    bus = can.Bus(channel=(0,1))
    #msg = can.Message(arbitration_id=0x1d2, data=bytearray(b'\xE1\x0C\x8F\x7C\xF0\xFF'), is_extended_id=False, channel=1)
    #bus.send(msg)
    #return
    #scan_forever(bus)

    for channel in (1,):
        print(f"Channel {channel}")
        #send_backlight(bus, channel, 0xF0)
        #send_damien(bus, channel)
        scan(bus, channel)
    print("Done")


def send_damien(bus, channel):
    counter = 0
    while True:
        data = bytes([0xe1, 0x0c, 0x8f, 0x0d + (counter << 4), 0xf0])
        counter = (counter + 1) % 0x10
        tx = can.Message(arbitration_id=0x1d2, data=data, is_extended_id=False, channel=channel)
        print(tx)
        bus.send(tx)
        check_unexpected_rx(bus, TIMEOUT, [tx])


def send_backlight(bus, channel, brightness):
    data = bytes([brightness, 0x00])
    tx = can.Message(arbitration_id=0x202, data=data, is_extended_id=False, channel=channel)
    print(tx)
    bus.send(tx)


def send_known(bus, channel):
    db = cantools.database.load_file('bmw_e9x_e8x.dbc')
    #message = db.get_message_by_name('EngineAndBrake')
    #data = message.encode({'BrakePressed':1, 'EngineTorque':50, 'EngineTorqueWoInterv':50, 'Brake_active2':0})

    #message = db.get_message_by_name('TransimissionData2')
    #data = message.encode({'ManualMode':1, 'Counter_418': 1, 'Checksum_418': 0})

    message = db.get_message_by_name('TransmissionDataDisplay')
    data = message.encode({
        'ShiftLeverMode': 1,
        'GearRelated_TBD': 3,
        'Counter_466': 1,
        'ShiftLeverPosition': 1,
        'xFF' : 0xFF,
        'ShiftLeverPositionXOR' : 1 ^ 0xF,
        'SportButtonState': 1})

    tx = can.Message(arbitration_id=message.frame_id, data=data, is_extended_id=False, channel=channel)
    print(message)
    while True:
        bus.send(tx)
        check_unexpected_rx(bus, TIMEOUT, [tx])


def quick_scan(bus, channel):
    for payload in range(0xFF):
        print(f"payload {payload:#x}")
        for test_id in [0x1d2]:
            try_msg = can.Message(arbitration_id=test_id, data=bytearray([payload]*8), is_extended_id=False, channel=channel)
            #print(try_msg)
            bus.send(try_msg)


def scan(bus, channel):
    history = []
    for test_id in range(0x000, 0x4ff):
        if test_id & 0xff == 0:
            print(f"scanning to {test_id:#x}")
        try_msg = can.Message(arbitration_id=test_id, data=bytearray([0xe1, 0x0c, 0x8b, 0x1c, 0xf0]), is_extended_id=False, channel=channel)
        bus.send(try_msg)
        history.append(try_msg)
        history = history[-16:]
        check_unexpected_rx(bus, TIMEOUT, history)


def scan_forever(bus):
    history = []
    while True:
        test_id = random.randint(0x100, 0x1ff)
        test_data = random.randbytes(random.randint(1, 8))
        channel = random.randint(0, 1)
        test_message = can.Message(arbitration_id=test_id, data=test_data, is_extended_id=False, channel=channel)
        history.append(test_message)
        history = history[-16:]
        bus.send(test_message)
        check_unexpected_rx(bus, TIMEOUT, history)


def sequence_onebyte_payloads(length, fill_byte=0xff):
    for seq_idx in range(length):
        for seq in range(0x100):
            yield bytes([fill_byte] * seq_idx + [seq] + [fill_byte] * (length - seq_idx - 1))


def sequence_bits(length):
    for bit in range(length * 8):
        yield bytes([0] * (bit//8) + [1<<(bit % 8)] + [0] * (length - (bit//8) - 1))


def scan_sequences(bus, channel):
    history = []
    for data in sequence_bits(8):
        print(f"scanning data {data.hex()}")
        for test_id in range(0x0, 0x7ff):
            try_msg = can.Message(arbitration_id=test_id, data=data, is_extended_id=False, channel=channel)
            bus.send(try_msg)
            history.append(try_msg)
            history = history[-16:]
            check_unexpected_rx(bus, TIMEOUT, history)


def check_unexpected_rx(bus, timeout, history):
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = bus.recv(timeout)
            # print(r)
            if r and r.arbitration_id in EXPECTED:
                idx = EXPECT_FROM[r.arbitration_id]
                expected = EXPECTED[r.arbitration_id]
                if any(r.data[idx:] == e[idx:] for e in expected):
                    continue  # this was an expected message

            # got an unexpected message
            if not r:
                if time.time() >= deadline:
                    break  # expected timeout
                print(f"unexpected CAN timeout")
            else:
                print(f"unexpected message {r}")
            print(f"--- {len(history)} previous message(s):")
            for m in reversed(history):
                print(f"   {m}")
            history.clear()


def scan_current_blips(bus, channel):
    min_threshold = 99.0
    avg_threshold = 110.3
    max_threshold = 111.0
    history = []
    mon = CurrentMonitor()
    for fill_byte in (0xff, 0x00, 0x55, 0xee):
        print(f"Filling with {fill_byte:#x}")
        data = bytes([fill_byte] * 8)
        for test_id in range(0x000, 0x4ff):
            if test_id == 0x202:
                continue  # we know this one will boost the current
            if test_id & 0x0F == 0:
                print(f"scanning {test_id:#x}")
            try_msg = can.Message(arbitration_id=test_id, data=data)
            bus.send(try_msg)
            mon.start_monitoring()
            for _ in range(60):  # 3 seconds of spamming this message (should be 5-6 samples on the meter)
                bus.send(try_msg)
                time.sleep(0.050)
            min_cur, max_cur, avg_cur = mon.stop_monitoring()
            if avg_cur > avg_threshold or max_cur > max_threshold or min_cur < min_threshold:
                print(f'Message {try_msg} min {min_cur} max {max_cur} avg {avg_cur}')
            time.sleep(1)  # let it 'relax' - would be best to power cycle here


class CurrentMonitor(object):

    def __init__(self):
        self._t = None

    def start_monitoring(self):
        assert self._t is None
        self._samples = []
        self._t = threading.Thread(target=self._thread_main)
        self._t.start()

    def stop_monitoring(self):
        assert self._t
        t = self._t
        self._t = None
        t.join()
        return (min(self._samples), max(self._samples), numpy.mean(self._samples))

    def _thread_main(self):
        with serial.Serial('/dev/ttyUSB0', 19200, bytesize=7, parity="O", stopbits=1, timeout=1.0) as s:
            s.rts = False  # powers up the IR link
            while self._t:
                line = s.readline()
                if not line:
                    print("Timeout!")
                    break
                m = re.match(rb'\d(\d{5})\?\d+:0\r\n', line)
                if m:
                    current = float(m.group(1)) / 100.0
                    #print(m.group(1), current)
                    self._samples.append(current)


if __name__ == "__main__":
    main()
