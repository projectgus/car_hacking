# A thin client session wrapper around an ISO-TP session using the isotp module.
# Call session.request(bytes) to submit a request and get any response within the specific
# timeout
import isotp

class Session:
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
    'stmin' : 0,
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
