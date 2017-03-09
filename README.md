gr-radiationpattern
===================

This GNUradio module provides a block to measure and display antenna radiation pattern diagrams.


Neccessary hardware
===================

- measurement transmitter
  - HackRF (or any other radio transmitter)
  - antenna
- receiver
  - HackRF or RTL-SDR
  - stepper motor
  - mounting bracket to mount antenna on stepper motor
  - motor controller:
     - developer board NUCLEO-F103R with BX_NUCLEO_IHM01A1 shield
     - https://developer.mbed.org/users/maxweller/code/motorControlShell/


License
=======

This software was developed at SEEMOO Secure Mobile Networking Lab, TU Darmstadt
https://www.seemoo.tu-darmstadt.de/

Copyright (c) 2017 Max Weller

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.


Instructions
============

1. Install dependencies:
	On Ubuntu:
  		sudo apt-get install gnuradio gr-osmosdr python python-serial cmake build-essential python-matplotlib python-numpy python-pexpect

  	On Arch:
  		sudo pacman -S gnuradio gr-osmosdr python2 python2-serial cmake build-essential python2-matplotlib python2-numpy python2-pexpect


2. Compile and install the module gr-radiationpattern:

	mkdir build
	cd build
	cmake .. && make && sudo make install && sudo ldconfig


3. Run:
	- connect the motor control board and the hackrf to the USB
	- make sure your user account has permission on the USB serial port, e.g. sudo chmod 0666 /dev/ttyACM0
	- open examples/receive.grc with gnuradio companion, run it
	- on an other computer, run examples/transmit.grc
	- click on "Start measurement"
	- ???
	- PROFIT


The interesting python code for the radiation pattern is python/antenna_diagram.py and python/antdiag_window.py. These files are modified versions of wxgui/numbersink2.py and wxgui/number_window.py from the GNUradio distribution.

There is a slightly different version of the antenna_diagram block called wx_radar_py_f which displays an endless updated radar-screen-like polar plot.


