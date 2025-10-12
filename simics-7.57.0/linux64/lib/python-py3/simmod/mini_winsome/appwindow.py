# © 2018 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import conf, os, re, sys, wx
import simics
import simmod.mini_winsome.win_main
from .win_utils import *

class appwindow:
    def __init__(self):

        if not self.window_name:
            print("Error: Missing window_name in ", self, file=sys.stderr)
            return

        assert_simics_lock()

        self.Bind(wx.EVT_CLOSE, self.close_window)
        self.Bind(wx.EVT_SHOW, self.show_window)
        self.Bind(wx.EVT_MOVE, self.move_window)
        self.Bind(wx.EVT_SIZE, self.size_window)

    def close_window(self, ev):
        if hasattr(self, 'on_close'):
            self.on_close(ev)
        self.Show(False)

    def show_window(self, ev):
        if hasattr(self, 'on_show'):
            self.on_show(ev)

    def move_window(self, ev):
        if hasattr(self, 'on_move'):
            self.on_move(ev)
        ev.Skip()

    def size_window(self, ev):
        if hasattr(self, 'on_size'):
            self.on_size(ev)
        ev.Skip()
