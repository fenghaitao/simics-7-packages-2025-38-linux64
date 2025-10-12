# © 2023 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import os

def init_winsome():
    try:
        from simmod.mini_winsome import check_wx
        have_wx = check_wx.have_wx
        init_gui = check_wx.init_gui
    except ImportError as ex:
        print(f"winsome module failed to load - no builtin GUI available: {ex}")
        init_gui = lambda : None
        have_wx = lambda : False
    init_gui()
    if have_wx():
        from simmod.mini_winsome import win_main
        win_main.win_init()

gui_enabled = not os.getenv("SIMICS_DISABLE_GUI")
if gui_enabled:
    init_winsome()
