#!/usr/bin/env python
#
# Copyright 2022 Angus Gratton
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause

import can, bmw_gws
import datetime, sys
from PySide6.QtCore import (
    QTimer,
    Qt,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QWidget):
    def __init__(self, bus):
        super().__init__(None)

        self.setWindowTitle("Bavariatron 5000")
        self.bus = bus

        self.gear = "P"
        self.last_lever_pos = 0x00

        self.park = QPushButton("Park")
        self.reverse = QPushButton("Reverse")
        self.neutral = QPushButton("Neutral")
        self.drive = QPushButton("Drive")

        self.park.pressed.connect(lambda: self.ui_select_gear("P"))
        self.reverse.pressed.connect(lambda: self.ui_select_gear("R"))
        self.neutral.pressed.connect(lambda: self.ui_select_gear("N"))
        self.drive.pressed.connect(lambda: self.ui_select_gear("D"))

        self.park_lock = QCheckBox("Park Lock")
        self.park_lock.setCheckState(Qt.CheckState.Checked)
        self.park_lock.clicked.connect(self.update_enabled)

        self.allow_manual = QCheckBox("Allow Manual")
        self.allow_manual.setCheckState(Qt.CheckState.Checked)

        self.flashing = QCheckBox("Flashing")

        self.cur_gear = QLabel("Gear: ?")
        self.hpos = QLabel("Lever: ???")
        self.vpos = QLabel("M/A: ??? ")
        self.raw_status = QLabel("???")
        self.last_gear_msg = QLabel("(Never)")

        self.brightness = QSlider(orientation=Qt.Horizontal)
        self.brightness.setMinimum(0)
        self.brightness.setMaximum(0xFF)
        self.brightness.valueChanged.connect(self.brightness_update)
        self.brightness_update(0)

        brightness_timer = QTimer(self)
        brightness_timer.timeout.connect(self.brightness_update)
        brightness_timer.setInterval(250)
        brightness_timer.start()

        left_column = QVBoxLayout()
        for w in [self.park, self.reverse, self.neutral, self.drive, self.flashing]:
            left_column.addWidget(w)

        right_column = QVBoxLayout()
        for w in [
            self.park_lock,
            self.allow_manual,
            self.cur_gear,
            self.hpos,
            self.vpos,
        ]:
            right_column.addWidget(w)

        g = QGridLayout(self)
        g.addLayout(left_column, 0, 0)
        g.addLayout(right_column, 0, 1)
        g.addWidget(self.raw_status, 1, 0, 2, 0)
        g.addWidget(self.last_gear_msg, 2, 0, 2, 0)
        g.addWidget(QLabel("Brightness"), 3, 0)
        g.addWidget(self.brightness, 3, 1)

        self.gear_msg_counter = 0
        self.status_msg_counter = None

        can_timer = QTimer(self)
        can_timer.timeout.connect(self.can_update)
        can_timer.setInterval(50)
        can_timer.start()

        self.update_enabled()

    def can_update(self):
        self.process_incoming_can()
        self.send_gear_status_msg()

    def process_incoming_can(self):
        while True:
            m = self.bus.recv(0)
            if not m:
                return
            if m.arbitration_id != 0x197:  # Not a gear status message
                print(m)
            else:
                self.process_incoming_gear_status(m)

    def process_incoming_gear_status(self, m):
        self.raw_status.setText(f"IN 0x197 - {m.data.hex()}")
        need_update = False

        if m.data[1] == self.status_msg_counter:
            print('Repeating counter value!')
            return
        self.status_msg_counter = m.data[1]

        calc_csum = bmw_gws.bmw_197_crc(m.data[1:4])
        if calc_csum != m.data[0]:
            print(f'{m.data} Invalid checksum. Calculated {calc_csum:#2x} provided {m.data[0]:#2x}')
            return

        lever_pos = m.data[2]
        if lever_pos != self.last_lever_pos:
            need_update = True
            if lever_pos in (0x1E, 0x2E):  # Centre Up
                self.hpos.setText("Centre")
                self.vpos.setText("Up" if lever_pos == 0x1E else "Up x2")
                if (
                    lever_pos == 0x1E or self.last_lever_pos != 0x2E
                ):  # only if moving up not down
                    self.gear = {"P": "N", "N": "R", "D": "N"}.get(self.gear, self.gear)
            elif lever_pos in (0x3E, 0x4E):  # Centre Down
                self.hpos.setText("Centre")
                self.vpos.setText("Down" if lever_pos == 0x3E else "Down x2")
                if lever_pos == 0x3E or self.last_lever_pos != 0x4E:
                    self.gear = {"P": "D", "N": "D", "R": "N"}.get(self.gear, self.gear)
            elif lever_pos == 0x0E:  # Centre middle
                self.hpos.setText("Centre")
                self.vpos.setText("Middle")
                if self.gear.startswith("M"):
                    self.gear = "D"
            elif lever_pos == 0x7E:  # Left middle
                self.hpos.setText("Left")
                self.vpos.setText("Middle")
                if self.gear == "D":
                    if self.allow_manual.isChecked():
                        self.gear = "M1"
                elif not self.gear.startswith("M"):
                    print("Error, invalid shifter position")
            elif lever_pos == 0x5E:  # Left Up
                self.hpos.setText("Left")
                self.vpos.setText("Up")
                self.gear = {"M1": "M2", "M2": "M3"}.get(self.gear, self.gear)
            elif lever_pos == 0x6E:  # Left Down
                self.hpos.setText("Left")
                self.vpos.setText("Down")
                self.gear = {"M3": "M2", "M2": "M1"}.get(self.gear, self.gear)
            else:
                self.hpos.setText("Unknown")
                self.vpos.setText("Unknown")

            self.last_lever_pos = lever_pos

        # This byte appears to be 0xC0 normally and 0xD5 when P button is held down
        park_button = m.data[3] == 0xD5
        if park_button and self.gear != "P":
            self.gear = "P"
            need_update = True

        if self.park_lock.isChecked():
            if self.gear != "P":
                need_update = True
                self.gear = "P"
                app.beep()
                print("BEEP!")

        if need_update:
            self.update_enabled()

    def send_gear_status_msg(self):
        # Process outgoing status

        # 0x80 is centre position only
        # 0x81 allows moving to the left "manual" position. 0x82 appears to be the same(?)
        d_value = 0x81 if self.allow_manual.isChecked() else 0x80
        gear_status = {
            "P": 0x20,
            "D": d_value,
            "R": 0x40,
            "N": 0x60,
            "M1": d_value,
            "M2": d_value,
            "M3": d_value,
        }[self.gear]
        if self.flashing.isChecked():
            gear_status |= 0x08

        payload = [self.gear_msg_counter, gear_status, 0x00, 0x00]
        payload.insert(0, bmw_gws.bmw_3fd_crc(payload))
        gear_msg = can.Message(arbitration_id=0x3FD, data=payload, is_extended_id=False)
        self.last_gear_msg.setText(f"OUT 0x3fd {bytes(payload).hex()}")
        self.bus.send(gear_msg)

        self.gear_msg_counter += 1
        if self.gear_msg_counter == 0x0F:
            self.gear_msg_counter = 0  # 0F is not a valid counter value

    def brightness_update(self, value=None):
        if value is None:
            value = self.brightness.value()  # timer callback
        else:
            print(f"Set brightness {value}")
        msg = can.Message(arbitration_id=0x202, data=[value, 0], is_extended_id=False)
        self.bus.send(msg)

    def update_enabled(self):
        park_lock = self.park_lock.isChecked()

        def set_bold(button, bold):
            if bold:
                button.setStyleSheet("font: bold;")
            else:
                button.setStyleSheet("")

        set_bold(self.park, self.gear == "P")
        set_bold(self.drive, self.gear in ["D", "M1", "M2", "M3"])
        self.drive.setEnabled(not park_lock)
        set_bold(self.reverse, self.gear == "R")
        self.reverse.setEnabled(not park_lock)
        set_bold(self.neutral, self.gear == "N")
        self.neutral.setEnabled(not park_lock)
        self.cur_gear.setText(f"Gear: {self.gear}")

    def ui_select_gear(self, gear):
        self.gear = gear
        self.update_enabled()

    def park_lock_checked(self):
        if self.park_lock.isChecked():
            print("Park lock!")
            self.gear = "P"
            self.update_enabled()


if __name__ == "__main__":
    bus = can.Bus(bitrate=500000)  # use default python-can config
    app = QApplication(sys.argv)
    win = MainWindow(bus)
    win.resize(500, 300)
    win.show()
    sys.exit(app.exec())
