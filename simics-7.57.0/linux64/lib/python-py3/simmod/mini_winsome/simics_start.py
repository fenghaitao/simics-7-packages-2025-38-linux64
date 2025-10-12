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

import os
import cli
import simics

def win_main_fail():
    try:
        from simmod.mini_winsome.check_wx import have_wx_failure
    except Exception:
        have_wx_failure = lambda: "mini_winsome not loaded"

    print()
    print("Failed to load the wxPython module needed for the GUI to load.")
    print()
    print('Error message: "%s"' % have_wx_failure())
    print()

gui_enabled = not os.getenv("SIMICS_DISABLE_GUI")
if gui_enabled:
    try:
        simics.SIM_load_module("mini_winsome")
        from simmod.mini_winsome.check_wx import have_wx
    except Exception as ex:
        print(ex)
        have_wx = lambda: False
    if not have_wx():
        cli.new_command("win-about", win_main_fail,
                        [],
                        short = "information on GUI load failure",
                        doc = "Shows information about why the GUI "
                        "libraries such as wxPython failed to load. "
                        "This command will replace the real "
                        "<cmd>win-about</cmd> on a failure.")
