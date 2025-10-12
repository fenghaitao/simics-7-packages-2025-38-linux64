# © 2010 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

from simics import *
from cli import (
    CliError,
    arg,
    disable_cmd,
    enable_cmd,
    integer_t,
    new_command,
)

mtprof_obj = None

class MTProf:
    def what(self):
        return "Multithreaded simulation profiling"
    def __init__(self, interval=None):
        self.interval = interval
    def is_enabled(self):
        if self.interval is not None:
            # We're setting the interval, so don't consider profiling
            # completely enabled or disabled.
            return None
        return mtprof_obj.active if mtprof_obj else False
    def set_enabled(self, enable):
        global mtprof_obj
        if not enable:
            mtprof_obj.active = False
            return
        if not mtprof_obj:
            mtprof_obj = SIM_create_object("mtprof", "mtprof", [])
        try:
            if self.interval is not None:
                mtprof_obj.interval = self.interval
                self.interval = None
            mtprof_obj.active = True
            self.extra_msg = "Interval: %d ms" % mtprof_obj.interval
        except SimExc_General as msg:
            raise CliError("Error starting profiling: %s" % msg)

new_command("enable-mtprof", enable_cmd(MTProf),
            args = [arg(integer_t, "interval", "?", None)],
            type = ["Profiling", "Performance"],
            short = "enable multithreaded simulation profiling",
            see_also = ["<mtprof>.cellstat", "<mtprof>.modelstat",
                        "<mtprof>.save-data"],
            doc = """
Enable multithreaded simulation profiling. The amount of
host cpu time required to simulate each cell is measured
every <arg>interval</arg> virtual ms.

The collected data is fed into a performance model which
estimates how fast the simulation would run on a system
with enough host cores and Simics Accelerator licenses to
allow each cell to run on a dedicated core. The performance
model also gives some insights into the performance implications
of various min-latency settings (settable though the
<cmd>set-min-latency</cmd> commands).

The <arg>interval</arg> parameter should normally be set to a value
of the same order as the min-latency setting of interest.""")

new_command("disable-mtprof", disable_cmd(MTProf),
            args = [],
            type = ["Profiling", "Performance"],
            short = "disable mtprof data collection",
            doc = """Disable multithreaded simulation profiling.""")
