#!/usr/bin/env python
#
# Based on work Copyright (c) 2019 Simp ECO Engineering, additions Copyright 2022 Angus Gratton
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause

import can, outlander_cmu, cmu_renumber
import datetime, sys, struct, time
import serial.tools.list_ports
from PySide6.QtCore import (
    QTimer,
    Qt,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
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


class RenumberGroup(QGroupBox):
    def __init__(self):
        super().__init__("Renumber IDs")

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.first_id = QLineEdit("01")
        self.first_id.setInputMask("99") # 2 digits

        self.port_sel = QComboBox()
        for p in serial.tools.list_ports.comports(True):
            self.port_sel.addItem(p.device)

        self.status = QLabel("")
        self.status.setWordWrap(True)

        button = QPushButton("Renumber")
        button.clicked.connect(self.on_renumber)

        for w in [QLabel("First ID"), self.first_id,
                  QLabel("Serial port"), self.port_sel,
                  button,
                  self.status]:
            layout.addWidget(w)

    def on_renumber(self):
        self.status.setText("")
        def msg(text):
            print(text)
            self.status.setText(self.status.text() + "\n" + text)
        port = self.port_sel.currentText()
        first_id = int(self.first_id.text())
        msg("Using port {} first ID {:#x}\n".format(port, first_id))
        try:
            with cmu_renumber.open_port(port) as port:
                pkt = cmu_renumber.renumber_packet_starting_from(first_id)
                msg("Write: {}".format(pkt.hex()))
                port.write(pkt)
                r = port.read(5)
                if r:
                    msg("Read: {}".format(r.hex()))
                    kept, new = cmu_renumber.decode_result_packet(r)
                    def list_ids(ids):
                        return ", ".join(str(x) for x in ids)
                    msg("Kept IDs: {}\nNew IDs: {}".format(list_ids(kept), list_ids(new)))
                else:
                    msg("Timeout, try again?")
        except RuntimeError as e:
            msg(str(e))
            raise


class MainWindow(QWidget):
    def __init__(self, bus):
        super().__init__(None)

        self.setWindowTitle("CMU Tests")
        self.bus = bus

        balance_group = QGroupBox("Balancing")
        balance_layout = QVBoxLayout()
        balance_group.setLayout(balance_layout)

        self.enable_balance = QCheckBox("Enable Balancing")
        self.force_balance = QCheckBox("Force Balance On")
        self.balance_voltage = QLineEdit("3.600")
        self.balance_voltage.setInputMask("9.900")

        for w in [self.enable_balance, self.force_balance, self.balance_voltage]:
            balance_layout.addWidget(w)

        save_voltages = QPushButton("Save Voltages")
        save_voltages.clicked.connect(self.save_voltages)

        renumber_group = RenumberGroup()

        controls = QVBoxLayout()
        for w in [balance_group, save_voltages, renumber_group]:
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

        self.update_tx_timer = QTimer(self)
        self.update_tx_timer.timeout.connect(self.update_tx_cb)
        self.update_tx_timer.setInterval(40)
        self.update_tx_timer.start()

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

    def update_tx_cb(self):
        balance_voltage = float(self.balance_voltage.text())
        txmsg = outlander_cmu.can_balance_msg(balance_voltage,
                                              self.enable_balance.isChecked(),
                                              self.force_balance.isChecked())
        self.bus.send(txmsg)
        #print(txmsg)


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
