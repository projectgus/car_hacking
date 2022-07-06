Some experimental code to communicate with Mitsubishi Outlander PHEV components over python-can.

* outlander_dtc.py is a Python module with some functions to work with the DTCs on various ECUs in the Outlander. See [Outlander PHEV Diagnostic CAN IDs, clearing "crashed mode"](https://forums.aeva.asn.au/viewtopic.php?f=49&t=7198) for some additional explanation.
* outlander_cmu.py is a Python module with a class and a function to parse CAN messages received from Outlander CMUs (battery cell monitor units).
* outlander_cmu_ui.py is a simple GUI program that uses outlander_cmu.py to talk to one or more CMU units on a CAN bus, display current voltages and temps, trigger balancing, etc.

CMU work here is based on reverse engineering and [protocol description](https://github.com/Tom-evnut/OutlanderPHEVBMS/blob/master/Decode%20BMS%20Canbus.pdf) work done by @Tom-evnut aka Simp ECO Engineering (SimpBMS creator), and also [descriptions written by Coulomb and others on DIY Electric Car](https://www.diyelectriccar.com/threads/mitsubishi-miev-can-data-snooping.179577/page-2#post-1066826). However the code here is not derived from any existing code, only the factual protocol descriptions.

### Using this code

As-is, this code isn't suitable for any application in a vehicle. But if you create something based on this, please credit my work (Angus Gratton) and others' as per the BSD License on the source code.

