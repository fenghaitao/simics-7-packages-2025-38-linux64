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

import conf
import os
import sys
import simics
import atexit

_have_wx = True
_have_wx_failure = "No error"
_init_gui_ok = False

def have_wx():
    return _have_wx

def have_wx_failure():
    return _have_wx_failure

def fail(msg):
    global _have_wx, _have_wx_failure
    _have_wx = False
    _have_wx_failure = msg

def init_gui():
    if conf.sim.batch_mode:
        # Do not load wx in batch-mode where it only makes tests slower
        fail("The GUI is disabled in batch mode")
    else:
        try:
            import wx
            atexit.unregister(wx._core._wxPyCleanup)
            global _have_wx
            _have_wx = True
        except Exception as ex:
            fail("Failed importing the 'wx' module: %s" % ex)

    if (have_wx() and not wx.App.IsDisplayAvailable()):
        fail("No display (DISPLAY environment variable not set?)")

    if have_wx():
        try:
            import simmod.mini_winsome.win_main
            _ = simmod.mini_winsome.win_main
            global _init_gui_ok
            _init_gui_ok = True
        except Exception as ex:
            import traceback
            traceback.print_exc()
            fail("Unexpected GUI error: %s" % ex)
            print(have_wx_failure())

def prepare_for_shutdown():
    # called from Simics core to freeze the gui thread (if it exists)
    if _init_gui_ok:
        import simmod.mini_winsome.win_main
        if (simics.VT_is_oec_thread()
            and not simmod.mini_winsome.win_main.is_in_gui_thread()):
            simmod.mini_winsome.win_main.prepare_for_shutdown()
