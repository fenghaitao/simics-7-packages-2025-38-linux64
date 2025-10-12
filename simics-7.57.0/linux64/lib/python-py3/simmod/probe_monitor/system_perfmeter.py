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

from . import monitor

class probe_system_perfmeter(monitor.probe_monitor_base):
    __slots__ = ()

    cls = confclass("probe_system_perfmeter",
                    parent=monitor.probe_monitor_base.cls,
                    pseudo=True,
                    short_doc="probe based system-perfmeter",
                    doc="Probe based system-perfmeter extending on the"
                    " probe-monitor, but adds some performance related"
                    " features")
