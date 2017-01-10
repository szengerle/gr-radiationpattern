#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 
# Copyright 2017 <+YOU OR YOUR COMPANY+>.
# 
# This is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
# 
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this software; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
# 

import numpy
from gnuradio import gr

import radar_window
from gnuradio.wxgui import common
from gnuradio import gr, filter
from gnuradio import analog
from gnuradio import blocks
from gnuradio.wxgui.pubsub import pubsub
from gnuradio.wxgui.constants import *

class wx_radar_py_f(gr.hier_block2, common.wxgui_hb):
    """
    radar plot sink
    """
    def __init__(self, 
		parent,
		minval=0,
		maxval=1,
		revolution_time=5.0,
		sample_rate=1,
		graphing_rate=1,
		size=radar_window.DEFAULT_WIN_SIZE,
		peak_hold=False,
		**kwargs #catchall for backwards compatibility
		):
        	#init
		self._item_size=gr.sizeof_float
		gr.hier_block2.__init__(
			self,
			"wx_radar_py_f",
			gr.io_signature(1, 1, self._item_size),
			gr.io_signature(0, 0, 0),
		)
		#blocks
		sd = blocks.stream_to_vector_decimator(
			item_size=gr.sizeof_float,
			sample_rate=sample_rate,
			vec_rate=graphing_rate,
			vec_len=1,
		)

		#mult = blocks.multiply_const_ff(factor)
		#add = blocks.add_const_ff(ref_level)
		#avg = filter.single_pole_iir_filter_ff(1.0)

		msgq = gr.msg_queue(2)
		sink = blocks.message_sink(self._item_size, msgq, True)
		#controller
		self.controller = pubsub()
		self.controller.subscribe(SAMPLE_RATE_KEY, sd.set_sample_rate)
		self.controller.publish(SAMPLE_RATE_KEY, sd.sample_rate)
		#self.controller[AVERAGE_KEY] = False
		#self.controller[AVG_ALPHA_KEY] = None
		#def update_avg(*args):
		#	if self.controller[AVERAGE_KEY]: avg.set_taps(self.controller[AVG_ALPHA_KEY])
		#	else: avg.set_taps(1.0)
		#update_avg()
		#self.controller.subscribe(AVERAGE_KEY, update_avg)
		#self.controller.subscribe(AVG_ALPHA_KEY, update_avg)

		#start input watcher
		common.input_watcher(msgq, self.controller, MSG_KEY)
		#create window
		self.win = radar_window.radar_window(
			parent=parent,
			controller=self.controller,
			size=size,
			minval=minval,
			maxval=maxval,
			peak_hold=peak_hold,
			msg_key=MSG_KEY,
			graphing_rate=graphing_rate,
			revolution_time=revolution_time
		)
		common.register_access_methods(self, self.controller)
		#backwards compadibility
		self.set_show_gauge = self.win.show_gauges
		#connect

		#self.wxgui_connect(self, sd, mult, add, avg, sink)
		self.wxgui_connect(self, sd, sink)



# ----------------------------------------------------------------
# Standalone test app
# ----------------------------------------------------------------

import wx
from gnuradio.wxgui import stdgui2

class test_app_flow_graph(stdgui2.std_top_block):
    def __init__(self, frame, panel, vbox, argv):
        stdgui2.std_top_block.__init__(self, frame, panel, vbox, argv)

        # build our flow graph
        input_rate = 10000

        # Generate a real and complex sinusoids
        src1 = analog.sig_source_f(input_rate, analog.GR_SIN_WAVE, 0.1, 1)

        # We add these throttle blocks so that this demo doesn't
        # suck down all the CPU available.  Normally you wouldn't use these.
        thr1 = blocks.throttle(gr.sizeof_float, input_rate)

        sink1 = wx_radar_py_f(panel, 
        	 sample_rate=input_rate,
        	 graphing_rate=10,
        	 revolution_time=4,
        	 minval=-1, maxval=1)
        vbox.Add(sink1.win, 1, wx.EXPAND)


        self.connect(src1, thr1, sink1)

def main ():
    app = stdgui2.stdapp(test_app_flow_graph, "wx_radar_py_f Test App")
    app.MainLoop()

if __name__ == '__main__':
    main()


