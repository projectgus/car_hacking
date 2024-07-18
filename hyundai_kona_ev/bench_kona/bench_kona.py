#!/usr/bin/env python
#
import asyncio
import can
import math
import sys
import datetime
import signal
from can.notifier import MessageRecipient
from typing import List

from PySide6.QtCore import Qt, QObject, Signal, Slot, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PySide6 import QtAsyncio

from message import PCAN_CH
import ieb
import igpm
import other
import srscm

can_log_name = f"{datetime.datetime.now().isoformat()}-bench_kona.log"
can_log = open(can_log_name, "w")
print(f"Writing CAN messages to {can_log_name}")


class Car:
    def __init__(self):
        self.braking = True  # start with virtual foot on brake
        self.charge_port_locked = False
        self.bus = None

        # Set up all the messages we'll be sending
        self.tx_messages = {}
        for mod in (ieb, igpm, srscm, other):
            for m in mod.get_messages(self):
                assert (
                    m.arbitration_id not in self.tx_messages
                )  # check for accidental dupes
                self.tx_messages[m.arbitration_id] = m

    def on_message(self, msg: can.Message):
        """Handle updates, will be called from a non-asyncio non-Qt thread!!"""
        print(msg, file=can_log)
        if msg.arbitration_id in self.tx_messages:
            print(f"WARNING: {msg.arbitration_id:#x} appears in both TX and RX")

    async def rx_coro(self, bus: can.BusABC):
        """Receive from the CAN bus and log whatever it sends us, plus invoke handler."""
        reader = can.AsyncBufferedReader()

        listeners: List[MessageRecipient] = [
            reader,  # AsyncBufferedReader() listener
        ]

        # Note: the async version of this class doesn't use asyncio event loop
        # unless the bus has a filno() property to use for the listener. It falls
        # back to a thread, meaning the callbacks are called in the thread context
        # still. This is incompoatible with the Python QAsyncioEventLoopPolicy that
        # requires any thread using asyncio to be main thread or a QThread
        self._notifier = can.Notifier(bus, listeners)
        self._notifier.add_listener(self.on_message)

    async def start(self):
        """Set up the asyncio bench_kona "model" """
        if "--virtual" in sys.argv:
            self.bus = can.interface.Bus("virtual", interface="virtual")
        else:
            self.bus = can.Bus(channel=PCAN_CH)

        # gather creates a task for each coroutine
        await asyncio.gather(
            self.rx_coro(self.bus),
            *(m.coro(self.bus, can_log) for m in self.tx_messages.values()),
        )

    async def send_ac_current(self, value):
        """ Send a short burst of CAN messages to update OBC state
        """
        print("Starting AC charge current change...")
        msg = can.Message(arbitration_id=0x562,
                          data=[0x00, value, 0x03, 0x00, 0xFF, 0xFF, 0x00, 0x00])
        print(msg)
        for _ in range(3):
            self.bus.send(msg, timeout=0.05)
            await asyncio.sleep(0.040)

        msg.data[1] = 0x00
        print(msg)

        for _ in range(3):
            self.bus.send(msg, timeout=0.05)
            await asyncio.sleep(0.040)

        print("Finished AC charge current change")

    async def send_ac_charge_limit(self, percent):
        """ Send a short burst of CAN messages to update charge termination
        """
        print(f"Starting AC charge to {percent}% change...")
        level = int(percent * 2)
        msg = can.Message(arbitration_id=0x562,
                          data=[0x00, 0x1C, 0x03, 0x00, level, 0xFF, 0x00, 0x00])
        print(msg)
        for _ in range(3):
            self.bus.send(msg, timeout=0.05)
            await asyncio.sleep(0.040)

        print(f"Finished AC charge to {percent}% change")


class MainWindow(QMainWindow):
    def __init__(self, car):
        super().__init__()
        self.car = car

        widget = QWidget()
        self.setCentralWidget(widget)

        layout = QVBoxLayout(widget)

        self.cb_braking = QCheckBox("Braking")
        self.cb_braking.setChecked(True)
        self.cb_braking.toggled.connect(self.on_braking_toggled)

        layout.addWidget(self.cb_braking)

        self.cb_locked = QCheckBox("Charge Port Locked")
        self.cb_locked.toggled.connect(self.on_charge_port_lock_toggled)

        layout.addWidget(self.cb_locked)

        # AC Charge Current buttons
        def make_send_ac_charge_current_fn(value):
            # bind pct to unique value in the lambda
            return lambda checked: asyncio.create_task(
                self.car.send_ac_current(value))

        for label, value in (("Maximum", 0x08),
                             ("Reduced", 0x0C),
                             ("Minimum", 0x04)):
            button = QPushButton(f"AC Charge {label}")
            button.clicked.connect(make_send_ac_charge_current_fn(value))
            layout.addWidget(button)

        def make_send_ac_charge_limit_fn(pct):
            # bind pct to unique value in the lambda
            return lambda checked: asyncio.create_task(
                self.car.send_ac_charge_limit(pct))

        # AC charge termination %
        for pct in (50, 70, 100):
            button = QPushButton(f"AC Charge Limit {pct}%")
            button.clicked.connect(make_send_ac_charge_limit_fn(pct))
            layout.addWidget(button)

        txGroup = QGroupBox("Enabled TX Messages")
        txLayout = QGridLayout()
        COLS = 3
        num_msgs = len(car.tx_messages)
        msgs_per_col = math.ceil(num_msgs / COLS)
        txGroup.setLayout(txLayout)
        for i, m in enumerate(
            sorted(car.tx_messages.values(), key=lambda m: m.arbitration_id)
        ):
            summary = m.__doc__
            if "\n" in summary:
                summary = summary[: summary.index("\n")]
            cb = QCheckBox(hex(m.arbitration_id) + " - " + summary)
            cb.setChecked(m.enabled)
            cb.toggled.connect(m.set_enabled)
            txLayout.addWidget(cb, i % msgs_per_col, i // msgs_per_col)
        layout.addWidget(txGroup)

    @Slot(bool)
    def on_braking_toggled(self, is_checked):
        print(f"Braking now {is_checked}")
        self.car.braking = is_checked

    @Slot(bool)
    def on_charge_port_lock_toggled(self, is_checked):
        print(f"Charge port lock now {is_checked}")
        self.car.charge_port_locked = is_checked


class AsyncHelper(QObject):

    def __init__(self, worker, entry):
        super().__init__()
        self.entry = entry
        self.worker = worker
        if hasattr(self.worker, "start_signal") and isinstance(
            self.worker.start_signal, Signal
        ):
            self.worker.start_signal.connect(self.on_worker_started)

    @Slot()
    def on_worker_started(self):
        print("on_worker_started")
        asyncio.ensure_future(self.entry())


if __name__ == "__main__":
    car = Car()

    if "--no-ui" in sys.argv:
        asyncio.run(car.start())
    else:

        # Otherwise, display a UI while running model in background asyncio
        app = QApplication(sys.argv)
        asyncio.set_event_loop_policy(QtAsyncio.QAsyncioEventLoopPolicy())

        main_window = MainWindow(car)
        main_window.show()

        # Run car.start() coro on the event loop, once it exists.
        # Seems a bit verbose...?
        timer = QTimer(app)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: asyncio.ensure_future(car.start()))
        timer.start()

        signal.signal(signal.SIGINT, signal.SIG_DFL)

        asyncio.get_event_loop().run_forever()
