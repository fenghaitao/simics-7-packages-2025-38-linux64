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
from configuration import *
import conf

from . import host_probes
from . import probes
from . import sketch
from .common import listify
from .probe_cache import cached_probe_read

import psutil

def create_probe_sketches(core_num):
    core_name = f"host.core{core_num}"
    n = f"{core_name}.probes"
    a = [["core_num", core_num]]
    objs = []
    objs += sketch.new("host_core", core_name, a)
    if hasattr(psutil, "sensors_temperatures"): # Not on windows
        objs += sketch.new("probe_host_core_temps", f"{n}.core_temps", a)
    return objs

class HostCoreTemperatureCache:
    @cached_probe_read
    def read(self):
        # This reads out temperatures on all cores!
        # Note, this is very slow!! So only do it once per sample
        return psutil.sensors_temperatures()

hostcore_temperature_cache = HostCoreTemperatureCache()

class HostCoreClass:
    cls = confclass("host_core", pseudo = True,
                    short_doc = "host core statistics for probes",
                    doc = ("Class used for host core specific probes."
                           " Objects of this class corresponds"
                           " to a physical processor core, with one or more"
                           " hardware threads (SMT)."))

    cls.attr.core_num("i", default = None, doc = "The host core number")

    class host_core_temps:
        cls = confclass("probe_host_core_temps", pseudo = True,
                        short_doc = "internal class",
                        doc = "Probe class for temperature a host core.")

        cls.attr.core_num("i", default = None, doc = "The host cpu number")

        @cls.iface.probe
        def value(self):
            temps = hostcore_temperature_cache.read()['coretemp']
            for t in temps:
                if t.label == f'Core {self.core_num}':
                    return t.current
            return -273.15          # quantum computer!

        @cls.iface.probe
        def properties(self):
            # Use host.coreN as owner
            host_core = SIM_object_parent(SIM_object_parent(self.obj))
            return listify(
                [(Probe_Key_Kind, "host.core.temp"),
                 (Probe_Key_Display_Name, "Host Temp"),
                 (Probe_Key_Metric_Prefix, "C"),
                 (Probe_Key_Float_Decimals, 0),
                 (Probe_Key_Description,
                  "The host core temperature."),
                 (Probe_Key_Type, "float"),
                 (Probe_Key_Cause_Slowdown, True),
                 (Probe_Key_Categories, ["host", "temperature"]),
                 (Probe_Key_Width, 6),
                 (Probe_Key_Owner_Object, host_core),
                 (Probe_Key_Aggregates, [
                     [
                         (Probe_Key_Kind, "host.core_temp_min"),
                         (Probe_Key_Display_Name, "Min Host Temp"),
                         (Probe_Key_Aggregate_Scope, "global"),
                         (Probe_Key_Owner_Object, conf.host),
                         (Probe_Key_Aggregate_Function, "min"),
                         (Probe_Key_Description,
                          "Lowest temperature on the host cores."),
                     ],
                     [
                         (Probe_Key_Kind, "host.core_temp_max"),
                         (Probe_Key_Display_Name, "Max Host Temp"),
                         (Probe_Key_Aggregate_Scope, "global"),
                         (Probe_Key_Owner_Object, conf.host),
                         (Probe_Key_Aggregate_Function, "max"),
                         (Probe_Key_Description,
                          "Highest temperature of the host cores."),
                     ],
                     [
                         (Probe_Key_Kind, "host.core_temp_mean"),
                         (Probe_Key_Display_Name, "Mean Host Temp"),
                         (Probe_Key_Aggregate_Scope, "global"),
                         (Probe_Key_Owner_Object, conf.host),
                         (Probe_Key_Aggregate_Function, "arith-mean"),
                         (Probe_Key_Description,
                          "Arithmetic mean of the cores' temperatures."),
                     ]])
                 ])
