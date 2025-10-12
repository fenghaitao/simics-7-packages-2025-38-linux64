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

import cli
import psutil
import conf

from simics import *
from configuration import *

from .common import listify
from . import probes
from . import host_cpu_probes
from . import host_core_probes
from . import sketch

from .probe_cache import cached_probe_read

cached_cpu_count = None
cached_core_count = None
cached_has_frequencies = None

def host_cpu_count():
    global cached_cpu_count
    if cached_cpu_count:
        return cached_cpu_count
    cached_cpu_count = psutil.cpu_count(True)
    return cached_cpu_count

def host_core_count():
    global cached_core_count
    if cached_core_count:
        return cached_core_count
    cached_core_count = psutil.cpu_count(False)
    return cached_core_count

def has_frequencies():
    global cached_has_frequencies
    if cached_has_frequencies != None:
        return cached_has_frequencies
    num_frequencies = len(psutil.cpu_freq(True))
    cached_has_frequencies = (num_frequencies == host_cpu_count())
    return cached_has_frequencies

def create_probe_sketches():
    num_cpus = host_cpu_count()
    num_cores = host_core_count()
    objs = []
    objs += sketch.new("host_system", "host")
    # Generic host probes
    n = "host.probes"
    objs += sketch.new("probe_host_memory", f"{n}.host.memory")
    objs += sketch.new("probe_host_swap", f"{n}.host.swap")
    objs += sketch.new("probe_host_loadavg", f"{n}.host.loadavg")
    objs += sketch.new("probe_process_memory", f"{n}.host.process_memory")

    # Create CPU specific probes
    for i in range(num_cpus):
        objs += host_cpu_probes.create_probe_sketches(i)

    # Core specific probes
    for i in range(num_cores):
        objs += host_core_probes.create_probe_sketches(i)
    return objs


# The singleton Simics 'host' top-level object.
class HostClass:
    __slots__ = ('num_cpus', 'num_cores', 'obj')
    cls = confclass("host_system", pseudo = True,
                    short_doc = "host statistics for probes",
                    doc = ("Singleton object class used to for host"
                           " specific probes."))

    @cls.finalize
    def finalize_instance(self):
        self.num_cpus = host_cpu_count()
        self.num_cores = host_core_count()

    class host_memory:
        cls = confclass("probe_host_memory", pseudo = True,
                        short_doc = "internal class",
                        doc = "Probe class for memory.")

        @cached_probe_read
        def cached_read_virtual_memory(self):
            return psutil.virtual_memory()

        @cls.iface.probe_index
        def num_indices(self):
            return 3

        @cls.iface.probe_index
        def value(self, idx):
            vmem = self.cached_read_virtual_memory()
            used = vmem.total - vmem.available
            if idx == 0:
                return used
            if idx == 1:
                return [used, vmem.total]
            if idx == 2:
                return vmem.total

        @cls.iface.probe_index
        def properties(self, idx):
            if idx == 0:
                return listify(
                    [(Probe_Key_Kind, "host.memory.used"),
                     (Probe_Key_Display_Name, "Host Mem"),
                     (Probe_Key_Binary_Prefix, "B"),
                     (Probe_Key_Description, "Used host memory."),
                     (Probe_Key_Type, "int"),
                     (Probe_Key_Categories, ["host", "memory"]),
                     (Probe_Key_Width, 9),
                     (Probe_Key_Owner_Object, conf.host)])
            elif idx == 1:
                return listify(
                    [(Probe_Key_Kind, "host.memory.used_percent"),
                     (Probe_Key_Display_Name, "Host Mem%"),
                     (Probe_Key_Float_Percent, True),
                     (Probe_Key_Float_Decimals, 1),
                     (Probe_Key_Description, "Used host memory."),
                     (Probe_Key_Type, "fraction"),
                     (Probe_Key_Categories, ["host", "memory"]),
                     (Probe_Key_Width, 6),
                     (Probe_Key_Owner_Object, conf.host)])
            else:
                return listify(
                    [(Probe_Key_Kind, "host.memory.total"),
                     (Probe_Key_Display_Name, "Host Mem Total"),
                     (Probe_Key_Binary_Prefix, "B"),
                     (Probe_Key_Description, "Total host memory."),
                     (Probe_Key_Type, "int"),
                     (Probe_Key_Categories, ["host", "memory"]),
                     (Probe_Key_Width, 9),
                     (Probe_Key_Owner_Object, conf.host)])


    class host_swap:
        cls = confclass("probe_host_swap", pseudo = True,
                        short_doc = "internal class",
                        doc = "Probe class for swap.")

        @cached_probe_read
        def cached_read_swap(self):
            return psutil.swap_memory()

        @cls.iface.probe_index
        def num_indices(self):
            return 3

        @cls.iface.probe_index
        def value(self, idx):
            swap = self.cached_read_swap()
            if idx == 0:
                return swap.used
            if idx == 1:
                return [swap.used, swap.total]
            if idx == 2:
                return swap.total

        @cls.iface.probe_index
        def properties(self, idx):
            if idx == 0:
                return listify(
                    [(Probe_Key_Kind, "host.swap.used"),
                     (Probe_Key_Display_Name, "Host Swap"),
                     (Probe_Key_Binary_Prefix, "B"),
                     (Probe_Key_Description, "Used host swap memory."),
                     (Probe_Key_Type, "int"),
                     (Probe_Key_Categories, ["host", "memory", "swap"]),
                     (Probe_Key_Width, 9),
                     (Probe_Key_Owner_Object, conf.host)])
            elif idx == 1:
                return listify(
                    [(Probe_Key_Kind, "host.swap.used_percent"),
                     (Probe_Key_Display_Name, "Host Swap%"),
                     (Probe_Key_Float_Percent, True),
                     (Probe_Key_Float_Decimals, 1),
                     (Probe_Key_Description, "Used host swap memory."),
                     (Probe_Key_Type, "fraction"),
                     (Probe_Key_Categories, ["host", "memory", "swap"]),
                     (Probe_Key_Width, 6),
                     (Probe_Key_Owner_Object, conf.host)])
            else:
                return listify(
                    [(Probe_Key_Kind, "host.swap.total"),
                     (Probe_Key_Display_Name, "Host Swap Total"),
                     (Probe_Key_Binary_Prefix, "B"),
                     (Probe_Key_Description, "Total swap memory."),
                     (Probe_Key_Type, "int"),
                     (Probe_Key_Categories, ["host", "memory", "swap"]),
                     (Probe_Key_Width, 9),
                     (Probe_Key_Owner_Object, conf.host)])

    class host_loadavg:
        cls = confclass("probe_host_loadavg", pseudo = True,
                        short_doc = "internal class",
                        doc = "Probe class for loadavg.")

        @cached_probe_read
        def cached_read_loadavg(self):
            return psutil.getloadavg()

        @cls.iface.probe_index
        def num_indices(self):
            return 3                # 1, 5 and 15 minutes

        @cls.iface.probe_index
        def value(self, idx):
            return self.cached_read_loadavg()[idx]

        @cls.iface.probe_index
        def properties(self, idx):
            minutes = [1, 5, 15][idx]
            return listify(
                [(Probe_Key_Kind, f"host.load_average_{minutes}m"),
                 (Probe_Key_Display_Name, f"Host Load ({minutes}m)"),
                 (Probe_Key_Description,
                  f"Host load average last {minutes} minutes."),
                 (Probe_Key_Type, "float"),
                 (Probe_Key_Float_Decimals, 1),
                 (Probe_Key_Categories, ["host", "load"]),
                 (Probe_Key_Width, 5),
                 (Probe_Key_Owner_Object, conf.host)])


    class process_memory:
        cls = confclass("probe_process_memory", pseudo = True,
                        short_doc = "internal class",
                        doc = "Probe class for process memory usage.")

        @cached_probe_read
        def cached_read_memory_info(self):
            return psutil.Process().memory_info()

        @cls.iface.probe_index
        def num_indices(self):
            return 2                # rss and vms

        @cls.iface.probe_index
        def value(self, idx):
            info = self.cached_read_memory_info()
            if idx == 0:
                return info.rss
            if idx == 1:
                return info.vms
            assert 0

        @cls.iface.probe_index
        def properties(self, idx):
            if idx == 0:
                return listify(
                    [(Probe_Key_Kind, "sim.process.memory.resident"),
                     (Probe_Key_Display_Name, "Process Mem-Res"),
                     (Probe_Key_Description,
                      "Amount of resident memory this Simics process uses."),
                     (Probe_Key_Binary_Prefix, "B"),
                     (Probe_Key_Float_Decimals, 1),
                     (Probe_Key_Categories, ["process", "memory"]),
                     (Probe_Key_Width, 9),
                     (Probe_Key_Owner_Object, conf.sim)])
            if idx == 1:
                return listify(
                    [(Probe_Key_Kind, "sim.process.memory.virtual"),
                     (Probe_Key_Display_Name, "Process Mem-Virt"),
                     (Probe_Key_Description,
                      "Amount of virtual memory this Simics process uses."),
                     (Probe_Key_Binary_Prefix, "B"),
                     (Probe_Key_Float_Decimals, 1),
                     (Probe_Key_Categories, ["process", "memory"]),
                     (Probe_Key_Width, 9),
                     (Probe_Key_Owner_Object, conf.sim)])
