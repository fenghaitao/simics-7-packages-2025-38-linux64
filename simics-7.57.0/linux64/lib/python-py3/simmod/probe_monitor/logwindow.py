# © 2022 Intel Corporation
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
from cli import get_available_object_name

class LogWindow:
    def __init__(self, monitor_obj):
        name = monitor_obj.name
        clock = monitor_obj.clock
        self.max_table_width = 80
        args = [["window_title", f"{name} Output"],
                ["screen_size", [self.max_table_width, 24]],
                ["visible", True],
                ["convert_crlf", True]]
        obj = SIM_create_object(
            "textcon", f"{name}.log",
            [["recorder", self.get_recorder(clock)],
             ["queue", clock]] + args)
        VT_set_object_checkpointable(obj, False)
        self.win_obj = obj
        self.serial_iface = obj.iface.serial_device

    def get_recorder(self, clock):
        try:
            recorder = list(SIM_object_iterator_for_class('recorder'))[0]
        except (IndexError, LookupError):
            rec_name = get_available_object_name("rec")
            if not clock:
                clock = SIM_create_object("clock", f"clock_{rec_name}", freq_mhz=1)
            recorder = SIM_create_object(
                "recorder", rec_name, [["queue", clock]])
        return recorder

    def log(self, lines):
        max_width = max([len(x) for x in lines.split("\n")])
        if max_width > self.max_table_width:
            self.max_table_width = max_width
            # Adjust the width of the terminal
            (_, h) = self.win_obj.screen_size
            self.win_obj.screen_size = [max_width, h]

        for c in lines:
            for b in c.encode("utf-8"):
                self.serial_iface.write(b)
