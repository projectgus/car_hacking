## BMW Electronic Gear Selector

Some *experimental* Python code for controlling the gear selector ("GWS") in some recent model BMWs (F series, G? series, etc).

For full story see these blog posts:

* [BMW F Series Gear Selector Part One: Failures](https://www.projectgus.com/2022/06/bmw-f-series-gear-selector-part-one-failures/)
* [BMW F Series Gear Selector Part Two: Breakthrough](https://www.projectgus.com/2022/06/bmw-f-series-gear-selector-part-two-breakthrough/)

The gear lever used here is from a 2014 BMW F20 1 Series (125i) LCI, VIN WBA1S320X05E77714. Marked "GW 9 296 899-01", "100999952-00" (back) and "1009972-00" (side). Code may or may not work with the many similar levers in other models...

[python-can](https://python-can.readthedocs.io/) needs to be installed and configured to use any of these.

### bmw_gws.py

Python module with a bunch of functions to send different status messages to the GWS, and also read back diagnostic trouble codes (DTCs). See the `bmw_gui_ui.py` for a full set of commands to talk to the device.


### bmw_gws_ui.py

1. Set up a [python-can configuration file](https://python-can.readthedocs.io/en/master/configuration.html#configuration-file) with the default CAN bus interface settings and channel (see top-level README in this repo for more).
2. `pip install crccheck`
3. `pip install PySide6`
4. Run `bmw_gws_ui.py` and you should be able to control the gear stick and see any movements.

### Using this code

As-is, this code isn't suitable for any application in a vehicle. But if you create something based on this, please credit my work  (Angus Gratton) as per the BSD License on the source code.
