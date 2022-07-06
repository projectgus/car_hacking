ESP32 MicroPython code to send ZF 4HP20 compatible automatic transmission display data (current gear selection) to a Peugeot auto dashboard. Will probably work with other vehicles that have 4HP20 transmissions, as well.

The Peugeot uses a single wire for this signal, which is a repeating 10-bit serial protocol at approx 100baud with a fixed delay between each 10-bit word.

For Peugeot 406 series D8.5 the dash signal is wire number 8480 in the loom. Signal is driven by an open drain type output, in this case I used an NPN transistor so the output signal from the micro is inverted in the code.

There is a Citroen Xantia/XM 4HP20 technical document floating around online that contains a full description of this protocol, aside from the baud rate(!)

### Using this code

As-is, this code isn't suitable for any application in a vehicle. But if you create something based on this, please credit my work (Angus Gratton) and others' as per the BSD License on the source code.
