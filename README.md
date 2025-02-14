Some random pieces of code for car hacking purposes.

Not finished, possibly non-functional, but maybe useful for some things.

See READMEs or code comments in sub-directories.

### Configuring python-can

Most of the Python code in this repo uses the [python-can](https://python-can.readthedocs.io/en/stable/) library to talk with a CAN bus.

Where possible the code uses the "default" python-can Bus, meaning that the system will choose the CAN interface based on a [configuration file](https://python-can.readthedocs.io/en/stable/configuration.html#configuration-file). This allows different systems to use different interfaces without changing the code (although none of these projects are very polished, so you'll possibly have to tweak the code for some of them!)

Here is a minimal sample config file for [Linux socketcan](https://python-can.readthedocs.io/en/stable/interfaces/socketcan.html):

```
[default]
interface = socketcan
channel = can0
bitrate = 500000
```

Here's one for the [Canalyst-II interface](https://python-can.readthedocs.io/en/stable/interfaces/canalystii.html) (which I don't recommend using if you have a busy CAN bus, it drops frames easily.)

```
[default]
interface = canalystii
channel = 0
bitrate = 500000
```

... consult the quite comprehensive python-can docs for more details.

### Using this code

As-is, none of this code is suitable for any application in a vehicle. But if you create something based on this, please credit my work (Angus Gratton) as per the BSD License.
