#
# Copyright 2008 Free Software Foundation, Inc.
#
# This file is part of GNU Radio
#
# GNU Radio is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# GNU Radio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNU Radio; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
#

##################################################
# Imports
##################################################
from gnuradio.wxgui import common
import numpy
import wx
from gnuradio.wxgui import pubsub
from gnuradio.wxgui.constants import *
from gnuradio import gr #for gr.prefs
from gnuradio.wxgui import forms


import matplotlib
matplotlib.use('WXAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_wxagg import \
    FigureCanvasWxAgg as FigCanvas, \
    NavigationToolbar2WxAgg as NavigationToolbar
import pylab

import time


import serial
from pexpect import fdpexpect

from threading import Thread
from time import sleep


##################################################
# Constants
##################################################
NEG_INF = float('-inf')
SLIDER_STEPS = 100
AVG_ALPHA_MIN_EXP, AVG_ALPHA_MAX_EXP = -3, 0
DEFAULT_NUMBER_RATE = gr.prefs().get_long('wxgui', 'number_rate', 5)
DEFAULT_WIN_SIZE = (500, 400)
DEFAULT_GAUGE_RANGE = 1000
VALUE_REPR_KEY = 'value_repr'
VALUE_REAL_KEY = 'value_real'
SERIAL_PORT_KEY = 'ser_port'
ROTATION_SPEED_KEY='rotationspeed'
WORKING_KEY='working'
#VALUE_IMAG_KEY = 'value_imag'


##################################################
# RADAR window control panel
##################################################
class control_panel(wx.Panel):
    """
    A control panel with wx widgits to control the averaging.
    """




    def __init__(self, parent):
        """
        Create a new control panel.

        Args:
            parent: the wx parent window
        """
        self.parent = parent
        wx.Panel.__init__(self, parent)
        parent[SHOW_CONTROL_PANEL_KEY] = True
        parent.subscribe(SHOW_CONTROL_PANEL_KEY, self.Show)
        control_box = wx.BoxSizer(wx.VERTICAL)
        #checkboxes for average and peak hold
        control_box.AddStretchSpacer()
        options_box = forms.static_box_sizer(
            parent=self, sizer=control_box, label='Options',
            bold=True, orient=wx.VERTICAL,
        )
        forms.check_box(
            sizer=options_box, parent=self, label='Keep values',
            ps=parent, key=PEAK_HOLD_KEY,
        )

        def openserial():
            serport = serial.Serial('/dev/ttyACM0', 115200)
            return serport

        def move_return():
            with openserial() as serport:
                ser = fdpexpect.fdspawn(serport)
                ser.sendline('set speed 960')
                ser.expect('OK')
                ser.sendline('mb 3200')
                ser.expect('OK')
                ser.sendline('wait')
                ser.expect('Waiting')
                print("Moving back to start position")
                ser.expect('OK, done')
                time.sleep(1)



        def start_measure_quick(v):
            if parent[WORKING_KEY]: return
            thread = Thread(target = measure_thread_quick, args = ())
            thread.start()

        def measure_thread_quick():
            try:
                parent[WORKING_KEY] = True
                move_return()
                with openserial() as serport:
                    ser = fdpexpect.fdspawn(serport)
                    print ("Starting measurement")

                    ser.sendline('set speed %s' % parent[ROTATION_SPEED_KEY])
                    parent.calculate_rates()

                    ser.expect('OK')

                    #parent.data = []
                    parent[RUNNING_KEY] = True
                    ser.sendline('mf 3200')
                    ser.expect('OK')
                    ser.sendline('wait')
                    ser.expect('Waiting')
                    print("Running measurement...")
                    choice = ser.expect(['OK, done', 'TIMEOUT', 'antennenlab', 'assertion failed'], timeout=int(parent.revolution_time)+1)
                    if choice == 0:
                        pass # success
                    elif choice == 1:
                        print("TIMEOUT!")
                    else:
                        print("ERROR/RESET in microcontroller")

                    parent[RUNNING_KEY] = False
                    print("Finished.")
            finally:
                parent[WORKING_KEY] = False

        def emerg_stop(v):
            with openserial() as serport:
                ser = fdpexpect.fdspawn(serport)
                ser.sendline('kill')
                parent[WORKING_KEY] = False

        def adj_cw(v):
            with openserial() as serport:
                ser = fdpexpect.fdspawn(serport)
                ser.sendline('mf 16')

        def adj_ccw(v):
            with openserial() as serport:
                ser = fdpexpect.fdspawn(serport)
                ser.sendline('mb 16')

        #run/stop
        control_box.AddStretchSpacer()
        forms.text_box(sizer=control_box, parent=self,
            label='Speed', ps=parent, key=ROTATION_SPEED_KEY)

        btn_start_measure_quick = forms.single_button(
            sizer=control_box, parent=self,
            label='Start measurement',
            callback=start_measure_quick
        )
        btn_adj_cw = forms.single_button(
            sizer=control_box, parent=self,
            label='adj. cw',
            callback=adj_cw
        )
        btn_adj_ccw = forms.single_button(
            sizer=control_box, parent=self,
            label='adj. ccw',
            callback=adj_ccw
        )
        forms.single_button(
            sizer=control_box, parent=self,
            label='STOP',
            callback=emerg_stop
        )

        def on_working_changed(newval):
            btn_start_measure_quick.Enable(not newval)
            btn_adj_cw.Enable(not newval)
            btn_adj_ccw.Enable(not newval)

        parent.subscribe(WORKING_KEY, on_working_changed)


        #set sizer
        self.SetSizerAndFit(control_box)

##################################################
# RADAR window with polar plot
##################################################
class antdiag_window(wx.Panel, pubsub.pubsub):

    def calculate_rates(self):
        speed = int(self[ROTATION_SPEED_KEY]) # pulses/second
        stepping = 1.0/16 # microstepping 1/16 (mode 0x04)
        degrees_per_step = 1.8
        self.revolution_time = 360.0 / (float(speed) * stepping * degrees_per_step)

        self.samples_per_revolution = self.graphing_rate*self.revolution_time
        if self.samples_per_revolution != int(self.samples_per_revolution):
            print("WARNING: samples_per_revolution (graphing_rate * revolution_time) should be integer")
        self.samples_per_revolution = int(self.samples_per_revolution)
        self.angle_per_sample = 2*numpy.pi/self.samples_per_revolution

        self.data = [0] * self.samples_per_revolution
        self.data_ptr = 0

    def __init__(
        self,
        parent,
        controller,
        size,
        minval,
        maxval,
        peak_hold,
        msg_key,
        graphing_rate,
        rotation_speed
    ):
        pubsub.pubsub.__init__(self)
        wx.Panel.__init__(self, parent, style=wx.SUNKEN_BORDER)
        #setup
        self.graphing_rate = graphing_rate
        self[ROTATION_SPEED_KEY] = rotation_speed
        self.calculate_rates()

        self.draw_fps=1 # frames per second
        self.draw_spf=1/self.draw_fps
        self.draw_next=time.time()+self.draw_spf
        

        self.peak_val_real = NEG_INF
        #self.peak_val_imag = NEG_INF
        #self.real = real
        #self.units = units
        #self.decimal_places = decimal_places
        #proxy the keys
        self.proxy(MSG_KEY, controller, msg_key)
        #self.proxy(AVERAGE_KEY, controller, average_key)
        #self.proxy(AVG_ALPHA_KEY, controller, avg_alpha_key)
        #self.proxy(SAMPLE_RATE_KEY, controller, sample_rate_key)
        #initialize values
        self[PEAK_HOLD_KEY] = peak_hold
        self[RUNNING_KEY] = True
        self.draw_pending = True
        self[VALUE_REAL_KEY] = minval
        self[WORKING_KEY] = False
        #setup the box with display and controls
        self.control_panel = control_panel(self)
        main_box = wx.BoxSizer(wx.HORIZONTAL)
        title="Radar"
        sizer = forms.static_box_sizer(
            parent=self, sizer=main_box, label=title,
            bold=True, orient=wx.VERTICAL, proportion=1,
        )
        main_box.Add(self.control_panel, 0, wx.EXPAND)
        forms.static_text(
            parent=self, sizer=sizer,
            ps=self, key=VALUE_REPR_KEY, width=size[0],
            converter=forms.str_converter(),
        )
        self.gauge_real = forms.gauge(
            parent=self, sizer=sizer, style=wx.GA_HORIZONTAL,
            ps=self, key=VALUE_REAL_KEY, length=size[0],
            minimum=minval, maximum=maxval, num_steps=DEFAULT_GAUGE_RANGE,
        )

        self.init_plot(minval, maxval)
        self.canvas = FigCanvas(self, -1, self.fig)
        sizer.Add(self.canvas, 1, flag=wx.LEFT | wx.RIGHT | wx.GROW)  

        #hide/show gauges
        self.show_gauges(True)
        self.SetSizerAndFit(main_box)
        #register events
        self.subscribe(MSG_KEY, self.handle_msg)

    def show_gauges(self, show_gauge):
        """
        Show or hide the gauges.
        If this is real, never show the imaginary gauge.

        Args:
            show_gauge: true to show
        """
        self.gauge_real.ShowItems(show_gauge)

    def handle_msg(self, msg):
        try:
            """
            Handle a message from the message queue.
            Convert the string based message into a float or complex.
            If more than one number was read, only take the last number.
            Perform peak hold operations, set the gauges and display.

            Args:
                event: event.data is the number sample as a character array
            """
            #print time.time()
            format_string = "%.10f"

            sample = numpy.fromstring(msg, numpy.float32)[-1]
            label_text = "%s %s"%(format_string%sample,"")
            self[VALUE_REAL_KEY] = sample

            #set label text
            self[VALUE_REPR_KEY] = label_text


            if self[RUNNING_KEY]:
                self.data[self.data_ptr] = sample
                self.data_ptr += 1
                if self.data_ptr >= self.samples_per_revolution:
                    self.data_ptr = 0
            
            if (self[RUNNING_KEY] or self.draw_pending) \
                     and (self.draw_next <= time.time()):
                self.draw_plot()
                self.draw_next=time.time()+self.draw_spf
                self.draw_pending = self[RUNNING_KEY]
            
        except Exception,e:
            print e



    def init_plot(self, minval, maxval):
        print "init_plot"

        self.dpi = 100
        self.fig = Figure((3.0, 3.0), dpi=self.dpi)

        self.axes = self.fig.add_subplot(111, projection='polar')
        self.axes.set_axis_bgcolor('#444444')
        self.axes.set_title('Radiation pattern', size=10)

        print "init_plot 2"
        
        xmin=0
        xmax=2*numpy.pi
        self.axes.set_xbound(lower=xmin, upper=xmax)
        self.axes.grid(True, color='gray')

        print "init_plot 3"
        
        pylab.setp(self.axes.get_xticklabels(), fontsize=8)
        pylab.setp(self.axes.get_yticklabels(), fontsize=8)
        pylab.setp(self.axes.get_xticklabels(), visible=True)

        # plot the data as a line series, and save the reference 
        # to the plotted line series
        #
        self.plot_data = self.axes.plot(
            self.data, 
            linewidth=1,
            color=(1, 1, 0),
            )[0]

        self.axes.set_ybound(lower=minval, upper=maxval)
        print "setting xmin=%f, xmax=%f"%(minval,maxval)
        print "init_plot DONE"


    def draw_plot(self):
        myxrange=numpy.arange(
                0,
                self.angle_per_sample*len(self.data),
                self.angle_per_sample)
        #print len(myxrange),len(self.data)
        self.plot_data.set_xdata(myxrange)
        self.plot_data.set_ydata(numpy.array(self.data))

        self.canvas.draw()

