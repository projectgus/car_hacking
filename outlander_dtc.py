# A Python module to help explore diagnostic interfaces, read and erase DTCs on
# Mitsubishi Outlander
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileCopyrightText: 2021 Angus Gratton
#
# Uses https://github.com/pylessard/python-can-isotp and Python 3.6+
#
# This isn't an executable script, it's designed for interactive use. i.e:
#
# import can, outlander_dtc
# bus = can.Bus()
# bus.scan_ecus(bus)
#
# ABSOLUTELY NO WARRANTY. THIS IS ALL WRITTEN TO MESS AROUND ON ONE WRECKED
# OUTLANDER AND IT'S POSSIBLE RUNNING THIS SCRIPT WILL BREAK YOUR CAR, REQUIRE
# PROFESSIONAL REPAIRS, CAUSE INJURY OR DEATH, PROPERTY DAMAGE, FIRES, ETC.
# ANY USE IS ENTIRELY AT OWN RISK. NO SUPPORT.
#
import asyncio
import can
import isotp
import time
import threading
import logging

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)-15s %(levelname)-8s:%(name)-12s:%(message)s',
                    filename='outlander_dtc.debug.log')

def find_ecu(bus, txid, timeout=0.1):
    """ Send a diagnostic command to 'txid', look for a matching response on any CAN ID """
    # the 'switch back to normal' msg
    scan_msg = can.Message(arbitration_id=txid, data=bytearray([0x02, 0x10, 0x81] + [0]*5),
                           is_extended_id=False)
    #print(scan_msg)
    expect_response = bytearray([0x02, 0x50, 0x81])
    t0 = time.time()
    remaining = timeout
    bus.send(scan_msg)
    while remaining > 0 or r:
        r = bus.recv(max(0,remaining))
        if r and r.data.startswith(expect_response):
            return r.arbitration_id
        remaining = (t0 + timeout) - time.time()
    return None

def scan_ecus(bus):
    """ Search the full 11-bit CAN range for things that respond like diagnostic interfaces """
    ecus = []
    for txid in range(0x00, 0x7FF):
        if (txid % 0x100 == 0):
            print(f"Progress {txid:#x}")
        rxid = find_ecu(bus, txid)
        if rxid:
            print(f'Found ECU TXID {txid:#x} RXID {rxid:#x}')
            ecus.append((txid, rxid))
    return ecus

def read_dtcs(bus, txid, rxid):
    """ Read DTCs from the ECU at txid/rxid CAN ID pair """
    with ThreadedIsoTp(bus, txid, rxid) as iso:
        r = iso.request(b'\x10\x92')
        if r != b'\x50\x92':
            raise RuntimeError(f'Invalid enter diagnostic mode response: {r}')

        r = iso.request(b'\1a\x87')
        if r:
            print(f'ID response: {r.hex()}')

        r = iso.request(b'\x18\x00\xff\x00')  # read codes
        if r[0] != 0x58:
            raise RuntimeError(f'unexpected DTC read response: {r}')
        num_dtcs = r[1]
        print(f'ECU {txid:#x} has {num_dtcs} DTCs:')
        for i in range(num_dtcs):
            offs = 2+i*3
            dtc = r[offs:offs+3]
            letter = {
                0x00: 'P',  # ??
                0x40: 'C',  # ?? <<--- this seems wrong!!!
                0x80: 'B',
                0xc0: 'U'}[dtc[0] & 0xc0]
            dtc[0] &= ~0xc0
            code = f'{letter}{dtc[0]:02X}{dtc[1]:02X}'
            status = {
                0x20 : 'stored',
                0x60 : 'active',
                0xe0 : 'active on dash?'
            }.get(dtc[2], f'status {dtc[2]:#x}')
            print(f'Code {code} ({status})')

        r = iso.request(b'\x10\x81')
        if r != b'\x50\x81':
            raise RuntimeError(f'Invalid exit diagnostic mode response: {r}')

        r = iso.request(b'\x10\x81')
        if r != b'\x50\x81':
            raise RuntimeError(f'Invalid exit diagnostic mode response: {r}')

def erase_dtcs(bus, txid, rxid):
    """ Erase DTCs from the ECU at txid/rxid CAN ID pair """
    print("Before:")
    read_dtcs(bus,txid,rxid)

    with ThreadedIsoTp(bus, txid, rxid) as iso:
        r = iso.request(b'\x10\x92')
        if r != b'\x50\x92':
            raise RuntimeError(f'Invalid enter diagnostic mode response: {r}')

        r = iso.request(b'\x14\xff\x00')
        if r != b'\x54\xff\x00':
            raise RuntimeError(f'Unexpected response to clear codes: {r}')

    print("After:")
    read_dtcs(bus,txid,rxid)

class ThreadedIsoTp:
   def __init__(self, bus, txid, rxid):
      self.exit_requested = False
      self.bus = bus
      self.rxid = rxid
      addr = isotp.Address(isotp.AddressingMode.Normal_11bits, rxid=rxid, txid=txid)
      self.stack = isotp.CanStack(self.bus, address=addr, error_handler=self.my_error_handler,
                                  params=isotp_params)

   def __enter__(self):
       self.old_filters = self.bus.filters
       self.bus.filters = [{"can_id":self.rxid, "can_mask":0xfffffff}]
       self.start()
       return self

   def __exit__(self, type, value, tb):
       self.stop()
       self.bus.filters = self.old_filters

   def start(self):
      self.exit_requested = False
      self.thread = threading.Thread(target = self.thread_task)
      self.thread.start()

   def stop(self):
      self.exit_requested = True
      if self.thread.is_alive():
         self.thread.join()

   def my_error_handler(self, error):
      logging.warning('IsoTp error happened : %s - %s' % (error.__class__.__name__, str(error)))

   def thread_task_disabled(self):
       import cProfile
       cProfile.runctx("self.thread_task_()", globals=globals(), locals=locals(), sort='cumtime')

   def thread_task(self):
      while self.exit_requested == False:
         self.stack.process()                # Non-blocking
         # (sleeping here seems to cause the diagnostic session to time out
         #time.sleep(0.001)
         #time.sleep(self.stack.sleep_time()) # Variable sleep time based on state machine state

   def shutdown(self):
      self.stop()
      self.bus.shutdown()

   def request(self, send_bytes, timeout=1.0):
      self.stack.send(send_bytes)
      t0 = time.time()
      while time.time() - t0 < timeout:
            if self.stack.available():
                return self.stack.recv()
            time.sleep(0.1)
      print(f'Timeout after {time.time() - t0:.1f}s')
      return None


isotp_params = {
    # Will request the sender to wait 32ms between consecutive frame. 0-127ms or 100-900ns with values from 0xF1-0xF9
    'stmin' : 1,
    # Request the sender to send 8 consecutives frames before sending a new flow control message
    'blocksize' : 0,
    # Number of wait frame allowed before triggering an error
    'wftmax' : 0,
    # Link layer (CAN layer) works with 8 byte payload (CAN 2.0)
    'll_data_length' : 8,
    # Will pad all transmitted CAN messages with byte 0x00. None means no padding
    'tx_padding' : 0,
    # Triggers a timeout if a flow control is awaited for more than 1000 milliseconds
    'rx_flowcontrol_timeout' : 500,
    # Triggers a timeout if a consecutive frame is awaited for more than 1000 millisecondsa
    'rx_consecutive_frame_timeout' : 1000,
    # When sending, respect the stmin requirement of the receiver. If set to True, go as fast as possible.
    'squash_stmin_requirement' : False
}
