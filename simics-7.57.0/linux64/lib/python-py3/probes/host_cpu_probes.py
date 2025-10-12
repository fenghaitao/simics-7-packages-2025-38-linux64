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
from .common import listify
from .probe_cache import cached_probe_read

import conf

from . import host_probes
from . import probes
from . import sketch

import psutil
import time

def create_probe_sketches(cpu_num):
    objs = []
    cpu_name = f"host.cpu{cpu_num}"
    a = [["cpu_num", cpu_num]]
    objs += sketch.new("host_processor", cpu_name, a)

    n = f"{cpu_name}.probes"
    if host_probes.has_frequencies():
        # On Windows we sometimes only get one frequency back, if so,
        # ignore these probes
        objs += sketch.new("probe_host_freq", f"{n}.freq", a)
        objs += sketch.new("probe_host_freq_percent", f"{n}.freq_percent", a)
    objs += sketch.new("probe_host_cpu_load", f"{n}.load", a)
    objs += sketch.new("probe_host_work_time", f"{n}.work_time", a)
    objs += sketch.new("probe_host_idle_time", f"{n}.idle_time", a)
    return objs

class CpuFreqCache:
    @cached_probe_read
    def read(self):
        return psutil.cpu_freq(True)

cpu_freq_cache = CpuFreqCache()

# Windows host manages to cause:
#    OSError: [WinError 1359] An internal error occurred
# Unclear why this happens. Also reported on psutil:
#    https://github.com/giampaolo/psutil/issues/2251
# This causes some random test-failures.
# Try to prevent the error by re-trying a number of times to see if
# the error hopefully goes away...
def read_psutil_cpu_times(percpu=False):
    # Gradually increase the sleep times, saturated at 1 second
    nap_times = [1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1] + [1.0] * 9
    while nap_times: # give up after 15 tries ~10 seconds
        try:
            return psutil.cpu_times(percpu=percpu)
        except OSError as msg:
            SIM_log_info(
                1, conf.probes, 0,
                f"psutil.cpu_times() raised OSError({msg}). Retrying..")
            nap = nap_times.pop(0)
            time.sleep(nap)

    assert 0, "Giving up trying to ignore OSError"

class CpuTimesCache:
    @cached_probe_read
    def read(self):
        return read_psutil_cpu_times(percpu=True)

cpu_times_cache = CpuTimesCache()

class HostProcessorClass:
    cls = confclass("host_processor", pseudo = True,
                    short_doc = "host processor statistics for probes",
                    doc = ("Class used for host processor specific probes."
                           " Objects of this class corresponds to a virtual"
                           " processor in the system (SMT). It could be one"
                           "or several of these per core."))

    cls.attr.cpu_num("i", default = None, doc = "The host cpu number")

    # Host processor specific probes

    class host_freq:
        cls = confclass("probe_host_freq", pseudo = True,
                        short_doc = "internal class",
                        doc = "Probe class for host processor frequency.")

        cls.attr.cpu_num("i", default = None, doc = "The host cpu number")

        @cls.iface.probe
        def value(self):
            freqs = cpu_freq_cache.read()
            return freqs[self.cpu_num].current * 1e6

        @cls.iface.probe
        def properties(self):
            # Use host.cpuN object as owner
            host_cpu = SIM_object_parent(SIM_object_parent(self.obj))
            return listify(
                [(Probe_Key_Kind, "host.cpu.freq"),
                 (Probe_Key_Display_Name, "Host CPU Freq"),
                 (Probe_Key_Metric_Prefix, "Hz"),
                 (Probe_Key_Description,
                  "The host CPU frequency."),
                 (Probe_Key_Type, "float"),
                 (Probe_Key_Categories, ["host", "frequency"]),
                 (Probe_Key_Width, 5),
                 (Probe_Key_Owner_Object, host_cpu),
                 (Probe_Key_Aggregates, [
                     [
                         (Probe_Key_Kind, "host.cpu_freq_min"),
                         (Probe_Key_Display_Name, "Min Host Freq"),
                         (Probe_Key_Aggregate_Scope, "global"),
                         (Probe_Key_Owner_Object, conf.host),
                         (Probe_Key_Aggregate_Function, "min"),
                         (Probe_Key_Description,
                          "Lowest frequency of the host processors."),
                     ],
                     [
                         (Probe_Key_Kind, "host.cpu_freq_max"),
                         (Probe_Key_Display_Name, "Max Host Freq"),
                         (Probe_Key_Aggregate_Scope, "global"),
                         (Probe_Key_Owner_Object, conf.host),
                         (Probe_Key_Aggregate_Function, "max"),
                         (Probe_Key_Description,
                          "Highest frequency of the host processors."),
                     ],
                     [
                         (Probe_Key_Kind, "host.cpu_freq_mean"),
                         (Probe_Key_Display_Name, "Mean Host Freq"),
                         (Probe_Key_Aggregate_Scope, "global"),
                         (Probe_Key_Owner_Object, conf.host),
                         (Probe_Key_Aggregate_Function, "arith-mean"),
                         (Probe_Key_Description, ("Arithmetic mean of the host"
                                                  " processors' frequencies.")),
                     ]])
                 ])


    class host_freq_percent:
        cls = confclass("probe_host_freq_percent", pseudo = True,
                        short_doc = "internal class",
                        doc = "Probe class for host frequency percent of max.")

        cls.attr.cpu_num("i", default = None, doc = "The host cpu number")

        @cls.iface.probe
        def value(self):
            freqs = cpu_freq_cache.read()[self.cpu_num]
            return (freqs.current) / (freqs.max)

        @cls.iface.probe
        def properties(self):
            # Use host.coreN object as owner
            host_cpu = SIM_object_parent(SIM_object_parent(self.obj))
            return listify(
                [(Probe_Key_Kind, "host.cpu.freq_percent"),
                 (Probe_Key_Display_Name, "Host Freq%"),
                 (Probe_Key_Float_Decimals, 0),
                 (Probe_Key_Float_Percent, True),
                 (Probe_Key_Description,
                  "The CPU frequency compared to max frequency."),
                 (Probe_Key_Type, "float"),
                 (Probe_Key_Categories, ["host", "frequency"]),
                 (Probe_Key_Width, 5),
                 (Probe_Key_Owner_Object, host_cpu)])


    class host_cpu_load:
        cls = confclass("probe_host_cpu_load", pseudo = True,
                        short_doc = "internal class",
                        doc = "Probe class for host processor load.")

        cls.attr.cpu_num("i", default = None, doc = "The host cpu number")

        def calculate_load(self, scputimes):
            # All fields in scputimes namedtuple, except "idle"
            all = sum([getattr(scputimes, m) for m in self.scputimes_names])
            return [(all - scputimes.idle), all]

        @cls.finalize
        def finalize_instance(self):
            # Get hold of an scputimes namedtuple and extract the
            # member names.
            scputimes = read_psutil_cpu_times()
            self.scputimes_names = set(scputimes._fields)

        @cls.iface.probe
        def value(self):
            cpu_times = cpu_times_cache.read()[self.cpu_num]
            return self.calculate_load(cpu_times)

        @cls.iface.probe
        def properties(self):
            # Use host.cpuN object as owner
            host_cpu = SIM_object_parent(SIM_object_parent(self.obj))
            return listify(
                [(Probe_Key_Kind, "host.cpu.load_percent"),
                 (Probe_Key_Display_Name, "Load%"),
                 (Probe_Key_Float_Decimals, 0),
                 (Probe_Key_Float_Percent, True),
                 (Probe_Key_Description, "The load on a host CPU."),
                 (Probe_Key_Type, "fraction"),
                 (Probe_Key_Categories, ["host", "load"]),
                 (Probe_Key_Width, 5),
                 (Probe_Key_Owner_Object, host_cpu),
                 (Probe_Key_Aggregates, [
                     [
                         (Probe_Key_Kind, "host.load_percent"),
                         (Probe_Key_Display_Name, "Host CPU load%"),
                         (Probe_Key_Aggregate_Scope, "global"),
                         (Probe_Key_Owner_Object, conf.host),
                         (Probe_Key_Aggregate_Function, "weighted-arith-mean"),
                         (Probe_Key_Description,
                          "Total load on all host processors. Maximum is 100%,"
                          " meaning all processors are fully utilized."
                          " On a machine with four processors, 25% equals one"
                          " processor being used and three are being idle."),
                     ]])
                 ])

    class host_cpu_work_time:
        cls = confclass("probe_host_work_time", pseudo = True,
                        short_doc = "internal class",
                        doc = "Probe class for host frequency.")

        cls.attr.cpu_num("i", default = None, doc = "The host cpu number")

        def calculate_time(self, scputimes):
            # All fields in scputimes namedtuple, except "idle"
            all = sum([getattr(scputimes, m) for m in self.scputimes_names])
            return all - scputimes.idle

        @cls.finalize
        def finalize_instance(self):
            # Get hold of an scputimes namedtuple and extract the
            # member names.
            scputimes = read_psutil_cpu_times()
            self.scputimes_names = set(scputimes._fields)

        @cls.iface.probe
        def value(self):
            cpu_times = cpu_times_cache.read()[self.cpu_num]
            return self.calculate_time(cpu_times)

        @cls.iface.probe
        def properties(self):
            # Use host.cpuN object as owner
            host_cpu = SIM_object_parent(SIM_object_parent(self.obj))
            return listify(
                [(Probe_Key_Kind, "host.cpu.time.work"),
                 (Probe_Key_Display_Name, "Host CPU Work"),
                 (Probe_Key_Description, "Scheduled work on a host CPU."),
                 (Probe_Key_Type, "float"),
                 (Probe_Key_Unit, "s"),
                 (Probe_Key_Categories, ["host"]),
                 (Probe_Key_Width, 5),
                 (Probe_Key_Owner_Object, host_cpu),
                 (Probe_Key_Aggregates, [
                     [
                         (Probe_Key_Kind, "host.time.work"),
                         (Probe_Key_Display_Name, "Host Work"),
                         (Probe_Key_Aggregate_Scope, "global"),
                         (Probe_Key_Owner_Object, conf.host),
                         (Probe_Key_Aggregate_Function, "sum"),
                         (Probe_Key_Description,
                          "Total amount of seconds all host processors has been"
                          " scheduled."),
                     ],
                     [
                         (Probe_Key_Kind, "host.time.work_histogram"),
                         (Probe_Key_Display_Name, "Host Work Histogram"),
                         (Probe_Key_Type, "histogram"),
                         (Probe_Key_Aggregate_Scope, "global"),
                         (Probe_Key_Owner_Object, conf.host),
                         (Probe_Key_Width, 30),
                         (Probe_Key_Aggregate_Function, "object-histogram"),
                         (Probe_Key_Description,
                          "Histogram of the host processors' work."),
                     ]]),
                 ])


    class host_cpu_idle_time:
        cls = confclass("probe_host_idle_time", pseudo = True,
                        short_doc = "internal class",
                        doc = "Probe class for host frequency.")

        cls.attr.cpu_num("i", default = None, doc = "The host cpu number")

        @cls.iface.probe
        def value(self):
            cpu_times = cpu_times_cache.read()[self.cpu_num]
            return cpu_times.idle

        @cls.iface.probe
        def properties(self):
            # Use host.cpuN object as owner
            host_cpu = SIM_object_parent(SIM_object_parent(self.obj))
            return listify(
                [(Probe_Key_Kind, "host.cpu.time.idle"),
                 (Probe_Key_Display_Name, "Host CPU Idle"),
                 (Probe_Key_Description, "Scheduled idle on a host CPU."),
                 (Probe_Key_Type, "float"),
                 (Probe_Key_Unit, "s"),
                 (Probe_Key_Categories, ["host"]),
                 (Probe_Key_Width, 5),
                 (Probe_Key_Owner_Object, host_cpu),
                 (Probe_Key_Aggregates, [
                     [
                         (Probe_Key_Kind, "host.time.idle"),
                         (Probe_Key_Display_Name, "Host Idle"),
                         (Probe_Key_Aggregate_Scope, "global"),
                         (Probe_Key_Owner_Object, conf.host),
                         (Probe_Key_Aggregate_Function, "sum"),
                         (Probe_Key_Description,
                          "Total amount of seconds all host processors has been"
                          " idle."),
                     ]])
                 ])
