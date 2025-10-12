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


import sys
import os
import time

from simics import *
import conf

from .common import listify
from . import probes
from . import sketch
from .probe_cache import cached_probe_read
from .probe_type_classes import Int128Value

def create_probe_sketches():
    objs = []
    for (cls, obj) in [
        ("probe_simulation_time",     "sim.probes.sim.simulation_time"),
        ("probe_sim_virtual_time",    "sim.probes.sim.virtual_time"),
        ("probe_sim_virtual_time_ps", "sim.probes.sim.virtual_time_ps"),
        ("probe_host_seconds",        "sim.probes.sim.host_time"),
        ("probe_image_mem",           "sim.probes.sim.image_mem"),
        ("probe_wallclock_time",      "sim.probes.sim.host_wallclock"),
        ("probe_module_profile",      "sim.probes.sim.module_profile"),
        ("probe_mm_malloc",           "sim.probes.sim.malloc_debug"),
        ("probe_io_probes",           "sim.probes.sim.io_probes")]:
        objs += sketch.new(cls, obj)
    return objs

class virtual_time:
    cls = confclass("probe_sim_virtual_time", pseudo = True,
                    short_doc = "internal class",
                    doc = "Probe class for virtual time.")

    # Try to find a CPU or clock to read time from
    def get_cpu_or_clock(self):
        if SIM_number_processors():
            return SIM_get_all_processors()[0]
        clks = list(SIM_object_iterator_for_interface(["cycle"]))
        return clks[0] if clks else None

    @cls.finalize
    def finalize_instance(self):
        self.cpu = self.get_cpu_or_clock()

    @cls.iface.probe
    def value(self):
        if not self.cpu:
            self.cpu = self.get_cpu_or_clock()
        if self.cpu:
            return SIM_time(self.cpu)
        return None

    @cls.iface.probe
    def properties(self):
        return listify(
            [(Probe_Key_Kind, "sim.time.virtual"),
             (Probe_Key_Display_Name, "Virtual-Time"),
             (Probe_Key_Unit, "hh:mm:ss.d"),
             (Probe_Key_Time_Format, True),
             (Probe_Key_Description,
              "The virtual time of the simulated system."
              " The time is taken from the first processor or clock in the"
              " system."),
             (Probe_Key_Type, "float"),
             (Probe_Key_Categories, ["time"]),
             (Probe_Key_Width, 11),
             (Probe_Key_Owner_Object, conf.sim)])

class virtual_time_ps:
    cls = confclass("probe_sim_virtual_time_ps", pseudo = True,
                    short_doc = "internal class",
                    doc = "Probe class for virtual time in ps.")

    def get_cycle_iface(self):
        if SIM_number_processors():
            cpu = SIM_get_all_processors()[0]
            if hasattr(cpu.iface, "cycle"):
                return cpu.iface.cycle
        clks = list(SIM_object_iterator_for_interface(["cycle"]))
        clk = clks[0] if clks else None
        if clk:
            return clk.iface.cycle
        return None

    @cls.finalize
    def finalize_instance(self):
        self.cycle_iface = self.get_cycle_iface()

    @cls.iface.probe
    def value(self):
        if not self.cycle_iface:
            self.cycle_iface = self.get_cycle_iface()

        if self.cycle_iface:
            ps = self.cycle_iface.get_time_in_ps().t
            return Int128Value._python_to_int128_attr(ps)
        return None

    @cls.iface.probe
    def properties(self):
        return listify(
            [(Probe_Key_Kind, "sim.time.virtual_ps"),
             (Probe_Key_Display_Name, "Virtual-Time"),
             (Probe_Key_Unit, "ps"),
             (Probe_Key_Description,
              "The virtual time of the simulated system in picoseconds."
              " The time is taken from the first processor or clock in the"
              " system."),
             (Probe_Key_Type, "int128"),
             (Probe_Key_Categories, ["time", "picoseconds"]),
             (Probe_Key_Width, 20),
             (Probe_Key_Owner_Object, conf.sim)])

class ImageMemoryUsage:
    cls = confclass("probe_image_mem", pseudo = True,
                    short_doc = "internal class",
                    doc = "Probe class for image memory.")

    @cls.iface.probe_index
    def num_indices(self):
        return 2


    @cls.iface.probe_index
    def value(self, idx):
        image_mem = SIM_get_class_attribute("image", "memory_usage")
        image_limit = SIM_get_class_attribute("image", "memory_limit")

        if idx == 0:
            return image_mem
        if idx == 1:
            return [image_mem, image_limit]

    @cls.iface.probe_index
    def properties(self, idx):
        if idx == 0:
            return listify(
                [(Probe_Key_Kind, "sim.image.memory_usage"),
                 (Probe_Key_Display_Name, "Image-Memory"),
                 (Probe_Key_Binary_Prefix, "B"),
                 (Probe_Key_Description,
                  "Memory usage of the image class objects"),
                 (Probe_Key_Type, "int"),
                 (Probe_Key_Categories, ["host", "memory"]),
                 (Probe_Key_Width, 11),
                 (Probe_Key_Owner_Object, conf.sim)])
        if idx == 1:
            return listify(
                [(Probe_Key_Kind, "sim.image.memory_limit_percent"),
                 (Probe_Key_Display_Name, "Image-Memory Limit%"),
                 (Probe_Key_Float_Percent, True),
                 (Probe_Key_Float_Decimals, 1),
                 (Probe_Key_Description,
                  "Memory usage of the image class objects, as percent"
                  " to the memory-limit set."),
                 (Probe_Key_Type, "fraction"),
                 (Probe_Key_Categories, ["host", "memory"]),
                 (Probe_Key_Width, 6),
                 (Probe_Key_Owner_Object, conf.sim)])


class WallClockCache:
    @cached_probe_read
    def read(self):
        return time.perf_counter()

# We cache the wallclock time in its own singleton object
# This is needed when we share the cache over multiple different probes
# in different classes
wallclock_cache = WallClockCache()

class simulation_time:
    cls = confclass("probe_simulation_time", pseudo = True,
                    short_doc = "internal class",
                    doc = "Probe class for wall clock time during simulation.")

    @cls.finalize
    def finalize_instance(self):
        self.users = 0
        wallclock = wallclock_cache.read()
        self.pause_start = None if SIM_simics_is_running() else wallclock
        self.base_time = wallclock
        self.pause_total = 0.0

    @cls.iface.probe_subscribe
    def subscribe(self):
        if self.users == 0:
            self.stop_hap_id = SIM_hap_add_callback(
                "Core_Simulation_Stopped", self.simulation_stopped, None)
            self.cont_hap_id = SIM_hap_add_callback(
                "Core_Continuation", self.simulation_continued, None)
        self.users += 1

    @cls.iface.probe_subscribe
    def unsubscribe(self):
        self.users -= 1
        if self.users == 0:
            SIM_hap_delete_callback_id("Core_Simulation_Stopped",
                                       self.stop_hap_id)
            SIM_hap_delete_callback_id("Core_Continuation",
                                       self.cont_hap_id)

    @cls.iface.probe_subscribe
    def num_subscribers(self):
        return self.users

    @cls.iface.probe
    def value(self):
        wallclock = wallclock_cache.read()
        if not SIM_simics_is_running():
            if self.pause_start == None: # Simulation_Stopped not yet triggered
                self.pause_start = wallclock
            # Reading time at the Simics prompt
            self.pause_total += wallclock - self.pause_start
            self.pause_start = wallclock

        return wallclock - self.pause_total - self.base_time

    @cls.iface.probe
    def properties(self):
        return listify(
            [(Probe_Key_Kind, "sim.time.wallclock"),
             (Probe_Key_Display_Name, "Wallclock"),
             (Probe_Key_Unit, "hh:mm:ss.d"),
             (Probe_Key_Time_Format, True),
             (Probe_Key_Description,
              "The host wall-clock time spent during simulation."
              " Idle time elapsed while Simics is not simulating is removed."),
             (Probe_Key_Type, "float"),
             (Probe_Key_Categories, ["host", "time"]),
             (Probe_Key_Width, 11),
             (Probe_Key_Owner_Object, conf.sim)])

    def simulation_continued(self, data, obj):
        self.pause_total += wallclock_cache.read() - self.pause_start
        self.pause_start = None

    def simulation_stopped(self, pm, obj, exc, error):
        self.pause_start = wallclock_cache.read()

class wallclock_time(WallClockCache):
    cls = confclass("probe_wallclock_time", pseudo = True,
                    short_doc = "internal class",
                    doc = "Probe class for wall clock time.")

    @cls.finalize
    def finalize_instance(self):
        self.base_time = wallclock_cache.read() # cache this at start-up instead?

    @cls.iface.probe
    def value(self):
        wallclock = wallclock_cache.read()
        return wallclock - self.base_time

    @cls.iface.probe
    def properties(self):
        return listify(
            [(Probe_Key_Kind, "host.time.wallclock"),
             (Probe_Key_Display_Name, "Host-Wallclock"),
             (Probe_Key_Unit, "hh:mm:ss.d"),
             (Probe_Key_Time_Format, True),
             (Probe_Key_Description,
              "The host wall-clock time."),
             (Probe_Key_Type, "float"),
             (Probe_Key_Categories, ["host", "time"]),
             (Probe_Key_Width, 11),
             (Probe_Key_Owner_Object, conf.host)])

class host_seconds:
    cls = confclass("probe_host_seconds", pseudo = True,
                    short_doc = "internal class",
                    doc = "Probe class for host thread time.")

    @cls.finalize
    def finalize_instance(self):
        self.users = 0
        host_time = self.get_host_time()
        self.pause_start = None if SIM_simics_is_running() else host_time
        self.base_time = host_time
        self.pause_total = 0.0

    @cls.iface.probe_subscribe
    def subscribe(self):
        if self.users == 0:
            self.stop_hap_id = SIM_hap_add_callback(
                "Core_Simulation_Stopped", self.simulation_stopped, None)
            self.cont_hap_id = SIM_hap_add_callback(
                "Core_Continuation", self.simulation_continued, None)
        self.users += 1

    @cls.iface.probe_subscribe
    def unsubscribe(self):
        self.users -= 1
        if self.users == 0:
            SIM_hap_delete_callback_id("Core_Simulation_Stopped",
                                       self.stop_hap_id)
            SIM_hap_delete_callback_id("Core_Continuation",
                                       self.cont_hap_id)

    @cls.iface.probe_subscribe
    def num_subscribers(self):
        return self.users

    @cls.iface.probe
    def value(self):
        host_time = self.get_host_time()
        if not SIM_simics_is_running():
            if self.pause_start == None:  # Simulation_Stopped not yet triggered
                self.pause_start = self.get_host_time()
            # Reading time at the Simics prompt
            self.pause_total += host_time - self.pause_start
            self.pause_start = host_time

        return host_time - self.pause_total - self.base_time

    @cls.iface.probe
    def properties(self):
        return listify(
            [(Probe_Key_Kind, "sim.time.host_threads"),
             (Probe_Key_Display_Name, "Host"),
             (Probe_Key_Unit, "hh:mm:ss.d"),
             (Probe_Key_Time_Format, True),
             (Probe_Key_Description,
              "Time Simics has spent simulating on all threads."
              " Idle time elapsed while Simics is not simulating is removed."),
             (Probe_Key_Type, "float"),
             (Probe_Key_Categories, ["host", "threads", "time"]),
             (Probe_Key_Width, 11),
             (Probe_Key_Owner_Object, conf.sim)])

    def simulation_continued(self, data, obj):
        self.pause_total += self.get_host_time() - self.pause_start
        self.pause_start = None

    def simulation_stopped(self, pm, obj, exc, error):
        self.pause_start = self.get_host_time()

    def get_host_time(self):
        return time.process_time()

class module_profile:
    cls = confclass("probe_module_profile", pseudo = True,
                    short_doc = "internal class",
                    doc = "Probe class for module-profiling.")

    @cls.finalize
    def finalize_instance(self):
        self.users = 0
        self.perfanalyze = None

    @cls.iface.probe_subscribe
    def subscribe(self):
        if self.users == 0 and not self.perfanalyze:
            SIM_get_class("perfanalyze-client")
            self.perfanalyze = conf.classes.perfanalyze_client
            self.perfanalyze.profiling_enabled = True
        self.users += 1

    @cls.iface.probe_subscribe
    def unsubscribe(self):
        self.users -= 1
        if self.users == 0:
            self.perfanalyze.profiling_enabled = False
            self.perfanalyze = None

    @cls.iface.probe_subscribe
    def num_subscribers(self):
        return self.users

    @cls.iface.probe
    def value(self):
        if not self.perfanalyze:
            return []
        # Return the module and the accumulated samples only
        return [[m, sa] for (m, u, s, sa) in self.perfanalyze.profile_data]

    @cls.iface.probe
    def properties(self):
        return listify(
            [(Probe_Key_Kind, "sim.module_profile"),
             (Probe_Key_Display_Name, "Module profile"),
             (Probe_Key_Type, "histogram"),
             (Probe_Key_Description,
              "Histogram of which modules being executed the most."),
             (Probe_Key_Categories, ["performance"]),
             (Probe_Key_Width, 40),
             (Probe_Key_Owner_Object, conf.sim)])


# Helper classes implementing various mm- probes
class mm_probe:
    __slots__ = ('kind', 'display', 'probe_type', 'width', 'fmt', 'desc')

    def __init__(self, kind, display, probe_type, width, fmt, desc):
        self.kind = kind
        self.display = display
        self.probe_type = probe_type
        self.width = width
        self.fmt = fmt
        self.desc = desc

    @staticmethod
    def value(mm_sites):
        assert 0  # Should be overridden

class mm_bytes_total(mm_probe):
    __slots__ = ()
    @staticmethod
    def value(mm_sites):
        # a[0] = number of bytes for this site allocation
        return sum([a[0] for a in mm_sites])

class mm_allocs_total(mm_probe):
    __slots__ = ()
    @staticmethod
    def value(mm_sites):
        # a[2] = total number of allocs for this site allocation
        return sum([a[2] for a in mm_sites])

class MmProbes:
    # We could export histogram probes for most allocs and memory per
    # site and type. But then we would like a beter C interface that
    # gives us this directly. We used to have this in Python but it
    # became too slow in large systems since the DBG_mm_get_sites()
    # returns a too large list to operate on.
    cls = confclass("probe_mm_malloc", pseudo = True,
                    short_doc = "internal class",
                    doc = "Probe class for mm allocation sites.")

    @cached_probe_read
    def cached_dbg_mm_get_sites(self):
        return DBG_mm_get_sites()

    idx2probe = {
        0: mm_bytes_total(
            "sim.process.memory.mm.bytes.total", "MM Bytes", "int", 10,
            (Probe_Key_Binary_Prefix, "B"),
            "The total amount of mm-malloced memory active in Simics."),
        1: mm_allocs_total(
            "sim.process.memory.mm.allocs.total", "MM Allocs", "int", 10,
            None,
            "The total amount of mm-malloced allocations in Simics."),
    }

    @cls.finalize
    def finalize_instance(self):
        self.users = 0

    @cls.iface.probe_subscribe
    def subscribe(self):
        self.users += 1
        if not DBG_mm_get_sites():
            print("Error: All sim.process.memory.mm.* probes requires that the"
                  " SIMICS_MEMORY_TRACKING environment variable is set"
                  " when Simics is started."
                  "\n No values will be returned")

    @cls.iface.probe_subscribe
    def unsubscribe(self):
        self.users -= 1

    @cls.iface.probe_subscribe
    def num_subscribers(self):
        return self.users

    @cls.iface.probe_index
    def num_indices(self):
        return len(self.idx2probe)

    @cls.iface.probe_index
    def value(self, idx):
        mm_sites = self.cached_dbg_mm_get_sites()
        p = self.idx2probe[idx]
        return p.value(mm_sites)

    @cls.iface.probe_index
    def properties(self, idx):
        p = self.idx2probe[idx]
        prop = [
            (Probe_Key_Kind, p.kind),
            (Probe_Key_Display_Name, p.display),
            (Probe_Key_Description, p.desc +
             " This probe requires that SIMICS_MEMORY_TRACKING"
             " is set, Simics is started."),
            (Probe_Key_Type, p.probe_type),
            (Probe_Key_Categories, ["host", "memory"]),
            (Probe_Key_Width, p.width),
            (Probe_Key_Owner_Object, conf.sim)]
        if p.fmt:
            prop.append(p.fmt)
        return listify(prop)

class IoProbes:
    cls = confclass("probe_io_probes", pseudo = True,
                    short_doc = "internal class",
                    doc = "Probe class for io-histogram.")

    @cached_probe_read
    def cached_all_io_accesses(self):
        l = []
        for p in probes.get_probes("dev.io_access_count"):
            v = p.value()
            if v:
                l.append((p.prop.owner_obj, v))
        return l

    class io_probe:
        __slots__ = ('kind', 'display', 'probe_type', 'width', 'fmt', 'desc')

        def __init__(self, kind, display, probe_type, width, desc):
            self.kind = kind
            self.display = display
            self.probe_type = probe_type
            self.width = width
            self.desc = desc

        @staticmethod
        def value(io_access_list):
            assert 0  # Should be overridden

    class io_access_count(io_probe):
        __slots__ = ()
        @staticmethod
        def value(io_access_list):
            return sum([v for _,v in io_access_list])

    class io_access_class_histogram(io_probe):
        __slots__ = ()
        @staticmethod
        def value(io_access_list):
            h = {}
            for (o, v) in io_access_list:
                cls_str = f"<{o.classname}>"
                h.setdefault(cls_str, 0)
                h[cls_str] += v

            return listify(list(h.items()))

    class io_access_object_histogram(io_probe):
        __slots__ = ()
        @staticmethod
        def value(io_access_list):
            return [[o.name, v] for (o, v) in io_access_list]

    idx2probe = {
        0: io_access_count(
            "sim.io_access_count", "IO accesses", "int", 12,
            "Total memory or port accesses towards devices."),

        1: io_access_class_histogram(
            "sim.io_access_class_histogram", "IO Access Class Histogram",
            "histogram", 50,
            "The classes which have most io-accesses from CPUs."),

        2: io_access_object_histogram(
            "sim.io_access_object_histogram", "IO Access Object Histogram",
            "histogram", 60,
            "The objects which have most io-accesses from CPUs."),
    }

    @cls.iface.probe_index
    def num_indices(self):
        return len(self.idx2probe)

    @cls.iface.probe_index
    def value(self, idx):
        io_accesses = self.cached_all_io_accesses()
        p = self.idx2probe[idx]
        return p.value(io_accesses)

    @cls.iface.probe_index
    def properties(self, idx):
        p = self.idx2probe[idx]
        prop = [
            (Probe_Key_Kind, p.kind),
            (Probe_Key_Display_Name, p.display),
            (Probe_Key_Description, p.desc),
            (Probe_Key_Type, p.probe_type),
            (Probe_Key_Categories, ["device", "io"]),
            (Probe_Key_Width, p.width),
            (Probe_Key_Owner_Object, conf.sim)]
        return listify(prop)
