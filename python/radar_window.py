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



##################################################
# Constants
##################################################
NEG_INF = float('-inf')
SLIDER_STEPS = 100
AVG_ALPHA_MIN_EXP, AVG_ALPHA_MAX_EXP = -3, 0
DEFAULT_NUMBER_RATE = gr.prefs().get_long('wxgui', 'number_rate', 5)
DEFAULT_WIN_SIZE = (300, 300)
DEFAULT_GAUGE_RANGE = 1000
VALUE_REPR_KEY = 'value_repr'
VALUE_REAL_KEY = 'value_real'
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

        #run/stop
        control_box.AddStretchSpacer()
        forms.toggle_button(
            sizer=control_box, parent=self,
            true_label='Stop', false_label='Run',
            ps=parent, key=RUNNING_KEY,
        )
        #set sizer
        self.SetSizerAndFit(control_box)

##################################################
# RADAR window with polar plot
##################################################
class radar_window(wx.Panel, pubsub.pubsub):
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
        revolution_time
    ):
        pubsub.pubsub.__init__(self)
        wx.Panel.__init__(self, parent, style=wx.SUNKEN_BORDER)
        #setup
        self.graphing_rate = graphing_rate
        self.revolution_time = revolution_time
        self.samples_per_revolution = graphing_rate*revolution_time
        if self.samples_per_revolution != int(self.samples_per_revolution):
            print("WARNING: samples_per_revolution (graphing_rate * revolution_time) should be integer")
        self.samples_per_revolution = int(self.samples_per_revolution)
        self.angle_per_sample = 2*numpy.pi/self.samples_per_revolution

        self.draw_fps=5 # frames per second
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
        self[VALUE_REAL_KEY] = minval
        #setup the box with display and controls
        self.control_panel = control_panel(self)
        main_box = wx.BoxSizer(wx.HORIZONTAL)
        title="Radar"
        sizer = forms.static_box_sizer(
            parent=self, sizer=main_box, label=title,
            bold=True, orient=wx.VERTICAL, proportion=1,
        )
        main_box.Add(self.control_panel, 0, wx.EXPAND)
        sizer.AddStretchSpacer()
        forms.static_text(
            parent=self, sizer=sizer,
            ps=self, key=VALUE_REPR_KEY, width=size[0],
            converter=forms.str_converter(),
        )
        sizer.AddStretchSpacer()
        self.gauge_real = forms.gauge(
            parent=self, sizer=sizer, style=wx.GA_HORIZONTAL,
            ps=self, key=VALUE_REAL_KEY, length=size[0],
            minimum=minval, maximum=maxval, num_steps=DEFAULT_GAUGE_RANGE,
        )
        sizer.AddStretchSpacer()

        self.data = [0]
        self.init_plot()
        self.canvas = FigCanvas(self, -1, self.fig)
        sizer.Add(self.canvas)#, 1, flag=wx.LEFT | wx.TOP | wx.GROW)  

        #hide/show gauges
        self.show_gauges(True)
        self.SetSizerAndFit(main_box)
        #register events
        self.subscribe(MSG_KEY, self.handle_msg)


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
            if not self[RUNNING_KEY]: return
            format_string = "%.10f"

            sample = numpy.fromstring(msg, numpy.float32)[-1]
            label_text = "%s %s"%(format_string%sample,"")
            self[VALUE_REAL_KEY] = sample

            #set label text
            self[VALUE_REPR_KEY] = label_text


            self.data.append(sample)

            if not self[PEAK_HOLD_KEY]:
                # delete data which is from the previous revolution

                if len(self.data) > self.samples_per_revolution:
                    self.data = self.data[-self.samples_per_revolution:]
            
            
            if self.draw_next <= time.time():
                self.draw_plot()
                self.draw_next=time.time()+self.draw_spf
                #print(self.draw_next)
            
        except Exception,e:
            print e



    def init_plot(self):
        self.dpi = 100
        self.fig = Figure((3.0, 3.0), dpi=self.dpi)

        self.axes = self.fig.add_subplot(111, projection='polar')
        self.axes.set_axis_bgcolor('#444444')
        self.axes.set_title('Very important random data', size=12)

        xmin=0
        xmax=2*numpy.pi
        self.axes.set_xbound(lower=xmin, upper=xmax)
        self.axes.grid(True, color='gray')

        pylab.setp(self.axes.get_xticklabels(), fontsize=8)
        pylab.setp(self.axes.get_yticklabels(), fontsize=8)
        pylab.setp(self.axes.get_xticklabels(), 
            visible=True)#self.cb_xlab.IsChecked())

        # plot the data as a line series, and save the reference 
        # to the plotted line series
        #
        self.plot_data = self.axes.plot(
            self.data, 
            linewidth=1,
            color=(1, 1, 0),
            )[0]

    def draw_plot(self):


        # for ymin and ymax, find the minimal and maximal values
        # in the data set and add a mininal margin.
        # 
        # note that it's easy to change this scheme to the 
        # minimal/maximal value in the current display, and not
        # the whole data set.
        # 
        #if self.ymin_control.is_auto():
        #    ymin = round(min(self.data), 0) - 1
        #else:
        #    ymin = int(self.ymin_control.manual_value())

        #if self.ymax_control.is_auto():
        #    ymax = round(max(self.data), 0) + 1
        #else:
        #    ymax = int(self.ymax_control.manual_value())
        ymin = round(min(self.data), 0)
        ymax = round(max(self.data), 0)
        delta = (ymax-ymin)*0.1
        ymin -= delta
        ymax += delta


        self.axes.set_ybound(lower=ymin, upper=ymax)

        # anecdote: axes.grid assumes b=True if any other flag is
        # given even if b is set to False.
        # so just passing the flag into the first statement won't
        # work.
        #
        #if self.cb_grid.IsChecked():
        #else:
        #    self.axes.grid(False)

        # Using setp here is convenient, because get_xticklabels
        # returns a list over which one needs to explicitly 
        # iterate, and setp already handles this.
        #  

        
        self.plot_data.set_xdata(numpy.arange(
                0,
                self.angle_per_sample*len(self.data),
                self.angle_per_sample))
        self.plot_data.set_ydata(numpy.array(self.data))

        self.canvas.draw()

