#!/usr/bin/env python
#
# Based on work Copyright (c) 2019 Simp ECO Engineering, additions Copyright 2022 Angus Gratton
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause

import can, outlander_cmu
import datetime, sys, struct
from PySide6.QtCore import (
    QTimer,
    Qt,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
    QLineEdit,
)

class CMUPanel(QWidget):
    def __init__(self, cmu_id):
        super().__init__()
        self.cmu = outlander_cmu.CMU(cmu_id)

        cmu_id = QLabel(f"CMU ID: {cmu_id}")
        self.last_update = QLabel("Never updated")
        self.byte1 = QLabel("Byte1: ")
        self.temps = [ QLabel("NaN C") for _ in range(3) ]
        self.voltages = [ QLabel(f"{i}: NaN V") for i in range(8) ]
        self.module_voltage = QLabel("Module: NaN V")

        layout = QVBoxLayout()
        for widget in [ cmu_id, self.last_update, self.byte1, self.module_voltage] + self.temps + self.voltages:
            layout.addWidget(widget)
        self.setLayout(layout)

    def update(self, can_msg):
        self.cmu.update(can_msg)
        self.last_update.setText(self.cmu.last_update.isoformat())
        self.byte1.setText(f"Byte1: {self.cmu.byte1:#x}")
        self.module_voltage.setText(f"Module: {sum(self.cmu.voltages):.3f} V")
        for (w,t) in zip(self.temps, self.cmu.temps):
            w.setText(f"{t:.3f} C")
        for (i,w,v,b) in zip(range(len(self.voltages)), self.voltages, self.cmu.voltages, self.cmu.balancing):
            bmsg = "Balancing" if b else ""
            w.setText(f"{i}: {v:.3f} V {bmsg}")


class MainWindow(QWidget):
    def __init__(self, bus):
        super().__init__(None)

        self.setWindowTitle("CMU Tests")
        self.bus = bus

        self.enable_balance = QCheckBox("Enable Balancing")
        self.force_balance = QCheckBox("Force Balance On")
        self.balance_voltage = QLineEdit("3.600")
        self.balance_voltage.setInputMask("9.900")

        save_voltages = QPushButton("Save Voltages")
        save_voltages.clicked.connect(self.save_voltages)

        controls = QVBoxLayout()
        for w in [self.enable_balance, self.force_balance, self.balance_voltage, save_voltages]:
            controls.addWidget(w)
        controls.addStretch(1)

        top_level_layout = QHBoxLayout()
        top_level_layout.addLayout(controls)
        self.module_layout = QGridLayout()
        top_level_layout.addLayout(self.module_layout)
        self.setLayout(top_level_layout)

        self.panels = {}

        can_timer = QTimer(self)
        can_timer.timeout.connect(self.can_update)
        can_timer.setInterval(50)
        can_timer.start()

        update_balance_timer = QTimer(self)
        update_balance_timer.timeout.connect(self.update_balance)
        update_balance_timer.setInterval(400)
        update_balance_timer.start()


    def can_update(self):
        for _ in range (10):
            msg = self.bus.recv(0)
            if not msg:
                return
            #print(msg)
            if 0x600 <= msg.arbitration_id < 0x700:
                cmu_id = (msg.arbitration_id & 0xf0) >> 4  # indexing from 1, same as Mitsubishi does
                if cmu_id not in self.panels:
                    row = len(self.panels) % 2
                    col = len(self.panels) // 2
                    self.panels[cmu_id] = CMUPanel(cmu_id)
                    self.module_layout.addWidget(self.panels[cmu_id], row, col)
                panel = self.panels[cmu_id]
                panel.update(msg)

    def update_balance(self):
        balance_voltage = float(self.balance_voltage.text())
        balance_level = 0
        if self.force_balance.isChecked():
            balance_level = 2  # https://www.diyelectriccar.com/threads/mitsubishi-miev-can-data-snooping.179577/page-2#post-1066826
        elif self.enable_balance.isChecked():
            balance_level = 1

        txdata = struct.pack(">HBBBxxx", int(balance_voltage * 1000), balance_level, 4, 3)  # 4,3 are magic numbers???
        txmsg = can.Message(arbitration_id=0x3c3, data=txdata, is_extended_id=False)
        #print(txmsg)
        self.bus.send(txmsg)

    def save_voltages(self):
        filename = QFileDialog.getSaveFileName(self, "Save Voltages Summary",
                                               filter="Text Files (*.txt)")
        with open(filename[0], "w") as f:
            for k in sorted(self.panels):
                p = self.panels[k]
                p.cmu.print(f)
                f.write("\n")


if __name__ == "__main__":
    bus = can.Bus(bitrate=500000)  # use default python-can config
    app = QApplication(sys.argv)
    win = MainWindow(bus)
    win.resize(500, 300)
    win.show()
    sys.exit(app.exec())
