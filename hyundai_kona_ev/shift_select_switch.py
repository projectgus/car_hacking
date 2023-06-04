#!/usr/bin/env python
#
# Very simple python-can test script to light up the
# Hyundai Kona Shift Select Switch (SBW)
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileCopyrightText: 2021 Angus Gratton
import can
import time

def main():
    bus = can.Bus(channels=0, baudrate=500_000)
    last_tx = time.time()

    cur_gear = 'P'

    last_counter = 0
    last_rx = None

    while True:
        # flush any received messages to the console
        m = bus.recv(0.010)
        if m:
            # look for a change, excluding the final counter byte
            if m.data[:7] != last_rx:
                last_rx = m.data[:7]
                counter = m.data[7]
                if last_counter == counter:
                    print(f"WARNING: payload changed, counter didn't! {m}")
                last_counter = counter

                # Decode any button that's pressed
                gear_select_momentary = m.data[:3].hex()
                pressed = {
                    "aa0a55": "None",
                    "a90a56": "P",
                    "a60a59": "R",
                    "9a0a65": "N",
                    "6a0a95": "D",
                    }.get(gear_select_momentary,
                          f"UNKNOWN {gear_select_momentary} {m}")
                displayed = m.data[5]
                # Note: different order to the EPCU's order for these
                displayed = {
                    0: 'None',
                    1: 'P',
                    2: 'R',
                    3: 'N',
                    4: 'D'}.get(displayed, displayed)
                print(f'Pressed: {pressed} Displayed: {displayed}')

                # Go direct to the new gear, if there is one
                if pressed in ('P', 'R', 'N', 'D'):
                    cur_gear = pressed

        # Send the status ID 0x200 at approx 100Hz
        if time.time() - last_tx > 0.01:
            current_gear = {
                'P': 0x00,
                'D': 0x05 << 3,
                'N': 0x06 << 3,
                'R': 0x07 << 3,
            }[cur_gear]

            msg = can.Message(arbitration_id=0x200,
                              is_extended_id=False,
                              data=bytes([0x00,
                                          current_gear,
                                          0x00,
                                          0x00,
                                          0x00,
                                          # upper two bits of last byte
                                          # look a lot like a counter field,
                                          # but SBW seems to ignore them! lol
                                          0x00,
                                          ]))
            bus.send(msg)
            last_tx = time.time()


if __name__ == "__main__":
    main()
