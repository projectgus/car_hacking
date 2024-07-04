#!/usr/bin/env python
#
import asyncio
import can
import sys
import datetime
import signal
from can.notifier import MessageRecipient
from typing import List

from PySide6.QtCore import (Qt, QObject, Signal, Slot, QTimer)
from PySide6.QtWidgets import (QApplication, QCheckBox, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget)
from PySide6.QtAsyncio import QAsyncioEventLoopPolicy

from message import PCAN_CH
import ieb
import srscm


class Car:
    def __init__(self):
        self.braking = True  # start with virtual foot on brake

    def on_message(self, msg: can.Message):
        """ Handle updates, will be called from a non-asyncio non-Qt thread!!  """
        print(msg)

    async def rx_coro(self, bus: can.BusABC):
        """Receive from the CAN bus and log whatever it sends us, plus invoke handler."""
        reader = can.AsyncBufferedReader()
        logger = can.Logger(f"{datetime.datetime.now().isoformat()}-bench_kona.csv")

        listeners: List[MessageRecipient] = [
            reader,  # AsyncBufferedReader() listener
            logger,  # Regular Listener object
        ]

        # Note: the async version of this class doesn't use asyncio event loop
        # unless the bus has a filno() property to use for the listener. It falls
        # back to a thread, meaning the callbacks are called in the thread context
        # still. This is incompoatible with the Python QAsyncioEventLoopPolicy that
        # requires any thread using asyncio to be main thread or a QThread
        self._notifier = can.Notifier(bus, listeners)
        self._notifier.add_listener(self.on_message)


async def main(car):
    """ Set up the asyncio bench_kona "model" """
    messages = []
    for mod in (ieb, srscm):
        messages += mod.get_messages(car)

    if "--virtual" in sys.argv:
        bus = can.interface.Bus("virtual", interface="virtual")
    else:
        bus = can.Bus(channel=(PCAN_CH,))

    # gather creates a task for each coroutine
    await asyncio.gather(car.rx_coro(bus), *(m.coro(bus) for m in messages))


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

    @Slot(bool)
    def on_braking_toggled(self, is_checked):
        print(f"Braking now {is_checked}")
        self.car.braking = is_checked


class AsyncHelper(QObject):

    def __init__(self, worker, entry):
        super().__init__()
        self.entry = entry
        self.worker = worker
        if hasattr(self.worker, "start_signal") and isinstance(self.worker.start_signal, Signal):
            self.worker.start_signal.connect(self.on_worker_started)

    @Slot()
    def on_worker_started(self):
        print('on_worker_started')
        asyncio.ensure_future(self.entry())


if __name__ == "__main__":
    car = Car()

    if "--no-ui" in sys.argv:
        asyncio.run(main(car))
    else:

        # Otherwise, display a UI while running model in background asyncio
        app = QApplication(sys.argv)
        asyncio.set_event_loop_policy(QAsyncioEventLoopPolicy())

        main_window = MainWindow(car)
        main_window.show()

        # Run main() coro on the event loop, once it exists.
        # Seems a bit verbose...?
        timer = QTimer(app)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: asyncio.ensure_future(main(car)))
        timer.start()

        signal.signal(signal.SIGINT, signal.SIG_DFL)

        asyncio.get_event_loop().run_forever()
