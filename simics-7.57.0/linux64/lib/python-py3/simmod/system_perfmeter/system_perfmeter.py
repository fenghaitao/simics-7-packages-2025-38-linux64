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

#
#  system_perfmeter.py - performance monitor tool for Simics
#

# The actual command which starts the performance measurements is located in
# simics_start.py

import simics
from simics import (
    CORE_host_hypervisor_info,
    SIM_cancel_realtime_event,
    SIM_class_has_attribute,
    SIM_create_object,
    SIM_delete_object,
    SIM_event_cancel_time,
    SIM_event_post_time,
    SIM_flush_all_caches,
    SIM_object_iterator,
    SIM_get_all_processors,
    SIM_get_class,
    SIM_get_class_attribute,
    SIM_get_processor_number,
    SIM_hap_add_callback,
    SIM_hap_delete_callback_id,
    SIM_number_processors,
    SIM_object_iterator_for_class,
    SIM_object_iterator_for_interface,
    SIM_realtime_event,
    SIM_register_event,
    SIM_run_alone,
    SIM_simics_is_running,
    SIM_step_count,
    SIM_time,
    VT_object_cell,
    VT_set_object_checkpointable,
)
from functools import cmp_to_key
from cli import conf
from cli import get_available_object_name
from cli import current_cycle_queue
import os
import timeit
import sys
import math
from functools import reduce

# The cpu/clock object used by system-perfmeter to measure time or use
# as cycle queue.
def sysperf_clock():
    return current_cycle_queue()

COUNTER_CAUSE_NORMAL = 0
COUNTER_CAUSE_INIT   = 1
COUNTER_CAUSE_UPDATE = 2
num_top_modules = 10

# A counter is an integer or floating point counter which is
# incremented during simulation. (Never decremented, reset etc).
# All counters starts with the 'value' zero when measurement starts.
# The 'value' retrieved from the counter is always a diff from
# the initial value set when initiating the counter.
# It is also possible to get the delta_value from the counter
# which then represent how much a counter has been incremented
# between two samples.
class counter:
    def __init__(self, desc):
        self.value = 0
        self.delta_value = 0
        self.start_value = 0
        self.delta_diff  = 0
        self.description = desc

    def update(self, new_val, cause):
        if cause == COUNTER_CAUSE_NORMAL:
            # Normal sample elapsed
            old = self.value
            self.value = new_val - self.start_value
            self.delta_value = (self.value - old) + self.delta_diff
            self.delta_diff = 0
        elif cause == COUNTER_CAUSE_INIT:
            # Initiate start value
            self.start_value = new_val
            self.value = 0
            self.delta_value = 0
            self.delta_diff = 0
        elif cause == COUNTER_CAUSE_UPDATE:
            # update inbetween samples
            old = self.value
            self.value = new_val - self.start_value
            self.delta_diff += (self.value - old)
            self.delta_value = None
        else:
            raise

# The perfanalyze client class supports getting module profile.
# This is a class and not an object, so we shouldn't be using
# its profile_data_clear or profile_data_accum_clear attributes
# since it disturbs collection for multiple users.
# Instead, we remember profile data we had when we started
# and the data in the last sample.
class module_profile:
    def __init__(self):
        # raises SimExc_General if the class is not available
        SIM_get_class("perfanalyze-client")

        self.perfanalyze = conf.classes.perfanalyze_client
        self.perfanalyze.profiling_enabled = True
        self.start_profile = {}
        self.last_profile = {}
        for (m, u, t, at) in self.perfanalyze.profile_data:
            self.start_profile[m] = (u, t, at)
            self.last_profile[m] = (u, t, at)

    def get_profile(self):
        new = []
        for (m, u, t, at) in self.perfanalyze.profile_data:
            if m in self.start_profile:
                delta_acc_ticks = at - self.start_profile[m][2]
            else:
                delta_acc_ticks = at

            if m in self.last_profile:
                delta_ticks = t - self.last_profile[m][1]
            else:
                delta_ticks = t

            self.last_profile[m] = (u, t, at)
            new.append([m, u, delta_ticks, delta_acc_ticks])
        return new

# Shared class between system-perfmeter and winsome plot code.
# Any state accessed through these generic functions must
# be visible in this class, not the system_perfmeter class.
class stats_collector:
    def __init__(self, cpu, sim_start = None, sim_stop = None):

        self.time_queue = cpu
        self.sim_start = sim_start
        self.sim_stop = sim_stop
        self.queue_objects = []
        self.measure_cell = None
        self.include_stop_time = False

        # Global Counters
        self.ctr = {}
        self.ctr["sim_time"] = counter("Virtual time")
        self.ctr["host_utime"] = counter("Host user time")
        self.ctr["host_stime"] = counter("Host system time")
        self.ctr["host_rtime"] = counter("Host real time")
        self.ctr["total_steps"] = counter("Simulator steps (all CPUs)")
        self.ctr["total_idle_steps"] = counter("Idle steps (all CPUs)")
        self.ctr["total_ma_steps"] = counter(
            "multicore accelerator steps (all CPUs)")
        self.ctr["total_host_ticks"] = counter("Total host ticks measured)")
        self.ctr["missed_host_ticks"] = counter("Host ticks not in CPU)")
        self.ctr["total_turbo_steps"] = counter("Steps with turbo (all CPUs)")
        self.ctr["total_vmp_steps"] = counter("Steps with VMP (all CPUs)")
        self.ctr["total_io"] = counter("I/O accesses (all CPUs)")
        self.ctr["total_imem_limit_hits"] = counter("Image memory limit hits")
        self.ctr["total_imem_limit_time"] = counter("Image memory limit time")
        self.ctr["total_imem_limit_bytes"] = counter("Image memory limit bytes")

        # Total ticks in cells (outside cells not added)
        self.ctr["cell_total_host_ticks"] = counter("Total cell ticks measured)")

        self.get_queue_objects()  # Cache queue objects (has "step" iface)
        self.get_device_objects() # Cache all device objects
        self.get_cell_objects()   # Cache cell objects

        # Per CPU Counters
        self.ctr["steps"] = {}
        self.ctr["idle_steps"] = {}
        self.ctr["ma_steps"] = {}
        self.ctr["jit_steps"] = {}
        self.ctr["vmp_steps"] = {}
        self.ctr["host_ticks"] = {}
        for id in range(len(self.queue_objects)):
            cpu = self.queue_objects[id]
            self.ctr["steps"][cpu] = counter("steps on cpu%d" % id)
            self.ctr["idle_steps"][cpu] = counter("idle steps on cpu%d" % id)
            self.ctr["ma_steps"][cpu] = counter(
                "multicore accelerator steps on cpu%d" % id)
            self.ctr["jit_steps"][cpu] = counter("JIT steps on cpu%d" % id)
            self.ctr["vmp_steps"][cpu] = counter("VMP steps on cpu%d" % id)
            self.ctr["host_ticks"][cpu] = counter("host ticks taken for cpu%d"
                                                  % id)
        # Per cell counters
        self.ctr["cell_host_ticks"] = {}
        for cell in self.cell_objects:
            self.ctr["cell_host_ticks"][cell] = counter(
                "host ticks for %s" % (cell.name))

        # Outside cell counter
        self.ctr["cell_host_ticks"][None] = counter("host ticks outside cells")

        # Non-counters (do not increase)
        self.disabled_cpus = 0

        # Keep track on how much time is spent in Simics command line
        # so we can distract this from the measurement
        self.last_prompt_rtime = 0.0
        self.last_prompt_utime = 0.0
        self.last_prompt_stime = 0.0
        self.stopped_rt_timestamp = 0.0
        self.stopped_ut_timestamp = 0.0
        self.stopped_st_timestamp = 0.0
        self.total_prompt_rtime = 0.0
        self.total_prompt_utime = 0.0
        self.total_prompt_stime = 0.0

        # Haps
        self.continuation_hap_id = 0
        self.sim_started_hap_id = 0
        self.objects_created_hap_id = 0
        self.objects_deleted_hap_id = 0
        self.at_exit_hap_id = 0

    def in_measure_cell(self, o):
        return (self.measure_cell == None or
                self.measure_cell == VT_object_cell(o))

    def get_queue_objects(self):
        self.queue_objects = sorted(
            o for o in SIM_object_iterator_for_interface(["step"])
            if self.in_measure_cell(o))

    def get_device_objects(self):
        self.device_objects = sorted(o for o in SIM_object_iterator(None)
                                     if (hasattr(o, 'access_count')
                                         and self.in_measure_cell(o)))

    def get_cell_objects(self):
        self.cell_objects = sorted(o for o in SIM_object_iterator_for_class("cell"))
        self.cell_object_short_name = {}
        for (i, cell) in enumerate(self.cell_objects):
            self.cell_object_short_name[cell] = "c%d" % (i)
        self.cell_object_short_name[None] = "oc"

    def update_queue_objects_and_counter(self):
        old_queue_objects = self.queue_objects[:]
        self.get_queue_objects()
        if old_queue_objects != self.queue_objects:
            # queue_objects list has changed, update cpu counter for new
            # queue_objects.
            # Remove the counter if its cpu object is gone
            # in the new queue_objects
            for cpu in old_queue_objects:
                if cpu not in self.queue_objects:
                    del self.ctr["steps"][cpu]
                    del self.ctr["idle_steps"][cpu]
                    del self.ctr["ma_steps"][cpu]
                    del self.ctr["jit_steps"][cpu]
                    del self.ctr["vmp_steps"][cpu]
                    del self.ctr["host_ticks"][cpu]

            # Add counter for the newly added cpu objects
            for id, cpu in enumerate(self.queue_objects):
                if cpu not in old_queue_objects:
                    self.ctr["steps"][cpu] = counter("steps on cpu%d" % id)
                    self.ctr["idle_steps"][cpu] = counter(
                        "idle steps on cpu%d" % id)
                    self.ctr["ma_steps"][cpu] = counter(
                        "multicore accelerator steps on cpu%d" % id)
                    self.ctr["jit_steps"][cpu] = counter(
                        "JIT steps on cpu%d" % id)
                    self.ctr["vmp_steps"][cpu] = counter(
                        "VMP steps on cpu%d" % id)
                    self.ctr["host_ticks"][cpu] = counter(
                        "host ticks taken for cpu%d" % id)

        old_cell_objects = self.cell_objects[:]
        self.get_cell_objects()
        if old_cell_objects != self.cell_objects:
            # Cell list different from before. Fix counters
            for cell in old_cell_objects:
                if cell not in self.cell_objects:
                    del self.ctr["cell_host_ticks"][cell]

            for cell in self.cell_objects:
                if cell not in old_cell_objects:
                    self.ctr["cell_host_ticks"][cell] = counter(
                        "host ticks for %s" % (cell.name))

            print(("systemperf: Cell-list has changed, -cpu-host-ticks will"
                   + " not be correct. You must restart system-perfmeter."))

        self.get_device_objects()


    # Command backend for the system-perfmeter command
    def stats_activate(self, register_haps=True):

        # Keep track on when Simics starts and stops
        if register_haps:
            if not self.continuation_hap_id:
                self.continuation_hap_id = SIM_hap_add_callback(
                    "Core_Continuation", self.stats_simulation_started, None)
            if not self.sim_started_hap_id:
                self.sim_started_hap_id = SIM_hap_add_callback(
                    "Core_Simulation_Stopped", self.stats_simulation_stopped,
                    True)
            if not self.objects_created_hap_id:
                self.objects_created_hap_id = SIM_hap_add_callback(
                    "Core_Conf_Objects_Created", self.objects_changed, None)
            if not self.objects_deleted_hap_id:
                self.objects_deleted_hap_id = SIM_hap_add_callback(
                    "Core_Conf_Objects_Deleted", self.objects_changed, None)
            if not self.at_exit_hap_id:
                self.at_exit_hap_id = SIM_hap_add_callback(
                    "Core_Clean_At_Exit", self.stats_at_exit, None)

        # Initiate the counters
        self.stats_update_counters(COUNTER_CAUSE_INIT)
        self.stopped_rt_timestamp = self.ctr["host_rtime"].value
        self.stopped_ut_timestamp = self.ctr["host_utime"].value
        self.stopped_st_timestamp = self.ctr["host_stime"].value
        self.total_prompt_rtime = 0.0
        self.total_prompt_utime = 0.0
        self.total_prompt_stime = 0.0

    def module_profile_activate(self):
        try:
            self.module_profile = module_profile()
        except simics.SimExc_General:
            print ("Failed to enable profiling."
                   " Class perfanalyze-client missing.")
            self.module_profile_enabled = False
            return
        self.module_profile_enabled = True

    def stats_deactivate(self):

        # Remove haps
        if self.continuation_hap_id:
            SIM_hap_delete_callback_id("Core_Continuation",
                                       self.continuation_hap_id)
            self.continuation_hap_id = 0
        if self.sim_started_hap_id:
            SIM_hap_delete_callback_id("Core_Simulation_Stopped",
                                       self.sim_started_hap_id)
            self.sim_started_hap_id = 0
        if self.objects_created_hap_id:
            SIM_hap_delete_callback_id("Core_Conf_Objects_Created",
                                       self.objects_created_hap_id)
            self.objects_created_hap_id = 0
        if self.objects_deleted_hap_id:
            SIM_hap_delete_callback_id("Core_Conf_Objects_Deleted",
                                       self.objects_deleted_hap_id)
            self.objects_deleted_hap_id = 0
        if self.at_exit_hap_id:
            SIM_hap_delete_callback_id("Core_Clean_At_Exit",
                                       self.at_exit_hap_id)
            self.at_exit_hap_id = 0

    # Called when Simics starts to execute
    # read real-time clock so we can discard time at Simics prompt when
    # calculating simulation time.
    def stats_simulation_started(self, cb_data, obj):
        self.update_queue_objects_and_counter()
        # Update counters so we know when we started for prompt time
        self.stats_update_counters(COUNTER_CAUSE_UPDATE)
        # Time spent at prompt this time
        self.last_prompt_rtime = (self.ctr["host_rtime"].value
                                  - self.stopped_rt_timestamp)
        self.last_prompt_utime = (self.ctr["host_utime"].value
                                  - self.stopped_ut_timestamp)
        self.last_prompt_stime = (self.ctr["host_stime"].value
                                  - self.stopped_st_timestamp)
        # Total time at prompt
        self.total_prompt_rtime += self.last_prompt_rtime
        self.total_prompt_utime += self.last_prompt_utime
        self.total_prompt_stime += self.last_prompt_stime

        if self.sim_start:
            self.sim_start()

    # Called when Simics stops and gives user a prompt.
    # Remember when this happen so we can remove this idle time in measurement.
    def stats_simulation_stopped(self, update_stop_time, obj, exc, reason_str):
        # Update counters, but not deltas, since this is not a sample.
        self.stats_update_counters(COUNTER_CAUSE_UPDATE)

        if update_stop_time:
            self.stopped_rt_timestamp = self.ctr["host_rtime"].value
            self.stopped_ut_timestamp = self.ctr["host_utime"].value
            self.stopped_st_timestamp = self.ctr["host_stime"].value

        if self.sim_stop:
            self.sim_stop()

    def stats_at_exit(self, cb_data, obj):
        # Be careful with that we do in the at exit hap. Printing a summary
        # should be fine.
        if self.include_stop_time or SIM_simics_is_running():
            self.stats_simulation_stopped(SIM_simics_is_running(),
                                          None, None, None)
        elif self.sim_stop:
            self.sim_stop()

    def objects_changed(self, cb_data, obj):
        # Update counters, but not deltas, since this is not a sample.
        self.update_queue_objects_and_counter()

    # Extract needed counters, each counter is accessible via:
    # self.ctr["name"].value & delta_value
    #
    # If cause is set to 1, the counters are initiated.
    # Thus, any value they have being initiated will
    # be subtracted from the current value to provide the delta
    # since performance measurement started.
    # If cause is set to 2, counters are updated but not the delta.
    def stats_update_counters(self, cause = COUNTER_CAUSE_NORMAL):

        # Global counters
        if sys.platform == 'win32':
            # Windows implementation has swapped first two values.
            # Ref. Python-2.4.2/Modules/posixmodule.c
            (stime, utime, _, _, _) = os.times()
        else:
            (utime, stime, child_utime, child_stime, _) = os.times()
        # timeit.default_timer() measures the wall clock. Depending on
        # the platform, it chooses between time.time() and
        # time.clock(), whichever is more accurate.
        rtime = timeit.default_timer()
        self.ctr["host_utime"].update(utime, cause)
        self.ctr["host_stime"].update(stime, cause)
        self.ctr["host_rtime"].update(rtime, cause)
        self.ctr["sim_time"].update(SIM_time(self.time_queue), cause)

        host_tick_list = conf.sim.cpu_tick
        missed_host_ticks = conf.sim.missed_cpu_ticks
        total_ticks = missed_host_ticks
        if len(host_tick_list):
            for t in range(len(host_tick_list)):
                total_ticks += host_tick_list[t]
        self.ctr["total_host_ticks"].update(total_ticks, cause)
        self.ctr["missed_host_ticks"].update(missed_host_ticks, cause)

        # CPU specific counters or counters derived from all CPUs
        total_steps = 0
        total_idle_steps = 0
        total_ma_steps = 0
        self.disabled_cpus = 0

        turbo_steps = 0
        vmp_steps = 0

        # Iterate over the processors and accumulate various data
        for id in range(len(self.queue_objects)):
            cpu = self.queue_objects[id]

            # Steps
            steps = SIM_step_count(cpu)
            total_steps += steps
            self.ctr["steps"][cpu].update(steps, cause)

            # Idle steps (halt and ffwd)
            idle_steps = 0

            # multicore accelerator steps
            ma_steps = 0

            if hasattr(cpu.iface, "step_info"):
                # HLT, MTMSR etc.
                idle_steps += cpu.iface.step_info.get_halt_steps()
                # Other kind of fast-forwarding, such as idle-loop optimizers
                idle_steps += cpu.iface.step_info.get_ffwd_steps()
                # multicore accelerator
                if cpu.iface.step_info.get_ma_steps != None:
                    # get_ma_steps was introduced in Simics 5 so has
                    # to be guarded/optional
                    ma_steps += cpu.iface.step_info.get_ma_steps()

            total_idle_steps += idle_steps
            self.ctr["idle_steps"][cpu].update(idle_steps, cause)

            # multicore accelerator steps
            total_ma_steps += ma_steps
            self.ctr["ma_steps"][cpu].update(ma_steps, cause)

            # Disabled
            if hasattr(cpu.iface, "processor_info"):
                self.disabled_cpus += not cpu.iface.processor_info.get_enabled()

            # Host ticks
            if len(host_tick_list):
                if (hasattr(cpu, "processor_number")
                    and len(host_tick_list) > cpu.processor_number):
                    cpu_ticks = host_tick_list[cpu.processor_number]
                else:
                    cpu_ticks = 0
                self.ctr["host_ticks"][cpu].update(cpu_ticks, cause)


            cpu_turbo_steps = 0
            cpu_vmp_steps = 0
            if SIM_class_has_attribute(cpu.class_data, "turbo_stat"):
                cpu_turbo_steps = cpu.turbo_stat['dynamic_instructions']
                turbo_steps += cpu_turbo_steps
                try:
                    cpu_vmp_steps = cpu.turbo_stat['vmp_run_steps']
                    vmp_steps += cpu_vmp_steps
                except simics.SimExc_Attribute:
                    pass

            self.ctr["jit_steps"][cpu].update(cpu_turbo_steps, cause)
            self.ctr["vmp_steps"][cpu].update(cpu_vmp_steps, cause)

        # Cell specific counters
        total_cell_ticks = 0
        cell_ticks_list = list(conf.sim.cell_ticks)
        cell_ticks = dict(cell_ticks_list) if len(cell_ticks_list) > 0 else {}
        for cell in self.cell_objects:
            if not cell in cell_ticks:
                # More cells now than when cell-ticks was started,
                # ignore this fault.
                continue

            ticks = cell_ticks[cell]
            total_cell_ticks += ticks
            self.ctr["cell_host_ticks"][cell].update(ticks, cause)

        self.ctr["cell_total_host_ticks"].update(total_cell_ticks, cause)

        # Outside cell counter
        if None in cell_ticks:
            ticks = cell_ticks[None]
            self.ctr["cell_host_ticks"][None].update(ticks, cause)

        # Total counters (derived accumulated CPU counters)
        self.ctr["total_steps"].update(total_steps, cause)
        self.ctr["total_idle_steps"].update(total_idle_steps, cause)
        self.ctr["total_ma_steps"].update(total_ma_steps, cause)
        self.ctr["total_turbo_steps"].update(turbo_steps, cause)
        self.ctr["total_vmp_steps"].update(vmp_steps, cause)

        io_sum = reduce(lambda x,y : x+y, [x.access_count
                                           for x in self.device_objects], 0)
        self.ctr["total_io"].update(io_sum, cause)

        (nswaps, swap_time, swap_bytes) = conf.classes.image.swap_stats
        self.ctr["total_imem_limit_hits"].update(nswaps, cause)
        self.ctr["total_imem_limit_time"].update(swap_time, cause)
        self.ctr["total_imem_limit_bytes"].update(swap_bytes, cause)

    def stats_generic_measure(self):

        self.stats_update_counters()

        # Elapsed real time
        delta_rtime = self.ctr["host_rtime"].delta_value
        delta_utime = self.ctr["host_utime"].delta_value
        delta_stime = self.ctr["host_stime"].delta_value
        if not self.include_stop_time:
            # Remove real-time we have stopped when we now continue
            delta_rtime -= self.last_prompt_rtime
            delta_utime -= self.last_prompt_utime
            delta_stime -= self.last_prompt_stime
        self.last_prompt_rtime = 0
        self.last_prompt_utime = 0
        self.last_prompt_stime = 0

        total_real_time = self.ctr["host_rtime"].value
        total_user_time = self.ctr["host_utime"].value
        total_system_time = self.ctr["host_stime"].value
        if not self.include_stop_time:
            # Remove real-time we have stopped in total
            total_real_time -= self.total_prompt_rtime
            total_user_time -= self.total_prompt_utime
            total_system_time -= self.total_prompt_stime

        try:
            total_host_cpu_percent = (
                100.0 * (total_user_time + total_system_time) / total_real_time)
        except ZeroDivisionError:
            total_host_cpu_percent = 0.0

        if delta_rtime != 0.0:
            delta_host_cpu_percent = (
                100.0 * (delta_utime + delta_stime) / delta_rtime)
        else:
            # Too short interval for accurate measurement
            delta_host_cpu_percent = 100.0

        # Elapsed virtual time
        total_steps = self.ctr["total_steps"].value
        delta_steps = self.ctr["total_steps"].delta_value
        total_virtual_time = self.ctr["sim_time"].value
        delta_vtime = self.ctr["sim_time"].delta_value

        # Calculate overall idle percentage
        total_idle = self.ctr["total_idle_steps"].value
        delta_idle = self.ctr["total_idle_steps"].delta_value
        if delta_steps:
            idle_percent = 100.0 * delta_idle / delta_steps
        else:
            idle_percent = 0.0

        total_ma_steps = self.ctr["total_ma_steps"].value
        delta_ma_steps = self.ctr["total_ma_steps"].delta_value

        total_turbo_steps = self.ctr["total_turbo_steps"].value
        delta_turbo_steps = self.ctr["total_turbo_steps"].delta_value

        total_vmp_steps = self.ctr["total_vmp_steps"].value
        delta_vmp_steps = self.ctr["total_vmp_steps"].delta_value

        total_io = self.ctr["total_io"].value
        delta_io = self.ctr["total_io"].delta_value

        if delta_vtime != 0:
            delta_slowdown = 1.0 * delta_rtime / delta_vtime
        else:
            delta_slowdown = "NaN"

        if total_virtual_time != 0:
            total_slowdown = 1.0 * total_real_time / total_virtual_time
        else:
            total_slowdown = "NaN"

        # MIPS including doze and idle opt instructions (not disabled)
        if delta_rtime != 0.0:
            delta_ipsi = delta_steps / delta_rtime
            # Really executed MIPS on all processors
            delta_ipse = (delta_steps - delta_idle) / delta_rtime
        else:
            delta_ipsi = "NaN"
            delta_ipse = "NaN"

        if total_real_time != 0.0:
            total_ipsi = total_steps / total_real_time
            total_ipse = (total_steps - total_idle) / total_real_time
        else:
            total_ipsi = "NaN"
            total_ipse = "NaN"

        # Image Memory usage
        image_limit = SIM_get_class_attribute("image", "memory_limit")
        image_mem = SIM_get_class_attribute("image", "memory_usage")
        if image_limit:
            mem_percent = (100 * image_mem)/image_limit
        else:
            mem_percent = 0

        # Page sharing
        page_sharing_savings = conf.sim.page_sharing_savings

        # Calculate disabled percent (for whole system)
        if len(self.queue_objects):
            disabled_percent = 100.0 * self.disabled_cpus / len(
                self.queue_objects)
        else:
            disabled_percent = 100.0
        # module profile
        if self.module_profile_enabled:
            profile_data = self.module_profile.get_profile()
        else:
            profile_data = None

        # If used not from CLI command, return sample numbers in a dictionary
        ret = {"tot_rt":       total_real_time,
               "del_rt":       delta_rtime,
               "tot_ut":       total_user_time,
               "del_ut":       delta_utime,
               "tot_st":       total_system_time,
               "del_st":       delta_stime,
               "tot_host_cpu": total_host_cpu_percent,
               "del_host_cpu": delta_host_cpu_percent,
               "tot_vt":       total_virtual_time,
               "del_vt":       delta_vtime,
               "tot_steps":    total_steps,
               "del_steps":    delta_steps,
               "tot_idle":     total_idle,
               "del_idle":     delta_idle,
               "tot_ma":       total_ma_steps,
               "del_ma":       delta_ma_steps,
               "tot_sd":       total_slowdown,
               "del_sd":       delta_slowdown,
               "tot_ipsi":     total_ipsi,
               "del_ipsi":     delta_ipsi,
               "tot_ipse":     total_ipse,
               "del_ipse":     delta_ipse,
               "idle":         idle_percent,
               "disabled":     disabled_percent,
               "image_mem":    mem_percent,
               "image_mem_usage": image_mem,
               "image_mem_limit": image_limit,
               "tot_turbo_steps": total_turbo_steps,
               "del_turbo_steps": delta_turbo_steps,
               "tot_vmp_steps": total_vmp_steps,
               "del_vmp_steps": delta_vmp_steps,
               "module_profile": profile_data,
               "page_sharing_savings" : page_sharing_savings,
               "tot_io" : total_io,
               "del_io" : delta_io}
        return ret

#
# System Selfprof standalone
#

measure_event = None
def measure_sample_alone(data):
    (obj, param) = data
    param.measure_sample(obj, None)

def measure_sample_cb(obj, param):
    # If multi-threaded execution, do the measurement when
    # all execution threads have stopped
    SIM_run_alone(measure_sample_alone, (obj, param))

def profile_compare_accum(a, b):
    if a[3] < b[3]:
        return 1
    elif a[3] > b[3]:
        return -1
    else:
        return 0

def profile_compare(a, b):
    if a[2] < b[2]:
        return 1
    elif a[2] > b[2]:
        return -1
    else:
        return profile_compare_accum(a, b)

# Format Instruction per seconds value to appropriate unit (KIPS, MIPS, GIPS)
# as a string
def ips_to_string(ips):
    if ips < 1e3:
        return "%.1f " % (ips, )
    if ips < 1e6:
        return "%.1fk" % (ips / 1e3, )
    elif ips < 1e9:
        return "%.1fM" % (ips / 1e6, )
    else:
        return "%.1fG" % (ips / 1e9, )

# Format Instruction per seconds value to appropriate unit (KIPS, MIPS, GIPS)
# as a string to be used in the summary
def ips_to_string_summary(ips):
    if ips < 1e3:
        return "%.2f " % (ips, )
    if ips < 1e6:
        return "%.2fk" % (ips / 1e3, )
    elif ips < 1e9:
        return "%.2fM" % (ips / 1e6, )
    else:
        return "%.2fG" % (ips / 1e9, )

prefixes = ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi", "Yi"]

# Create a human-readable formatting of `x` using binary SI prefixes
# to reduce the magnitude. If `unit` is the empty string, a prefix is
# still used but not followed by a unit.
def format_bin_prefix(x, unit):
    power = math.log(max(abs(x), 1), 2)
    idx = max(min(int(power / 10), len(prefixes) - 1), 0)
    pref = prefixes[idx]
    xp = x / 1024.0 ** idx
    return "%.1f%s%s%s" % (xp, " " if pref or unit else "", pref, unit)

assert format_bin_prefix(0, "") == "0.0"
assert format_bin_prefix(-1000.5, "bit") == "-1000.5 bit"
assert format_bin_prefix(262144, "") == "256.0 Ki"
assert format_bin_prefix(262144, "B") == "256.0 KiB"

# Returns a string with host specific information. (Simics
# version, host CPUs etc.)
def get_host_info():
    sim = conf.sim
    s = "Simics build-id %d %s" % (sim.version, sim.host_type)
    s += " on %d CPUs with %d MiB RAM" % (sim.host_num_cpus,
                                          sim.host_phys_mem // 1024 // 1024)
    return s

# Returns a string with target information. Number of processors, cells etc.
def get_target_info():
    sim = conf.sim
    cpus = 0
    l = []
    cells = len(sim.cell_list)
    # Count how many CPUs there are in each cell, and how may CPUs in total.
    for i in range(cells):
        cell = sim.cell_list[i]
        cpus += len(cell.schedule_list)
        l.append(len(cell.schedule_list))

    s = " %d CPUs" % (cpus,)
    s += " in %d cells" % (cells,)
    # list amount of scheduled processors in each cell
    s += " ["
    for (i,c) in enumerate(l):
        s += "%d" % (c)
        if i != len(l) - 1:
            s += ","
    s += "]"
    return s

# Return a string with information on number of threads used.
def get_thread_info():
    return ("%d execution threads, %d compilation threads"
            % (conf.sim.num_threads_used,
               conf.sim.actual_worker_threads if conf.sim.use_jit_threads
               else 0))

import simmod.hypersim_pattern_matcher.simics_start as hypersim

# Return an array of strings, where each string identifies a Simics setting
# making the simulation speed degrade.
def get_slow_settings(sys_perfm):
    sim = conf.sim
    l = []
    if not hypersim.hypersim_enabled:
        l.append("Hypersim disabled")

    if not sim.data_stc_enabled:
        l.append("DSTC disabled")
    if not sim.instruction_stc_enabled:
        l.append("ISTC disabled")
    if not sim.multithreading:
        l.append("Multimachine Accelerator disabled")

    realtime_objs = list(SIM_object_iterator_for_class("realtime"))
    if realtime_objs:
        realtime_enabled = False
        for o in realtime_objs:
            if o.enabled:
                realtime_enabled = True
        if realtime_enabled:
            l.append("Real-time mode active")

    vmp_enabled = True
    for c in SIM_get_all_processors():
        if hasattr(c, "init_vm_monitor") and not c.init_vm_monitor:
            vmp_enabled = False

    if not vmp_enabled:
        l.append("VMP disabled")

    hv_info = CORE_host_hypervisor_info()
    if hv_info.is_hv_detected:
        l.append("Running inside hypervisor (hypervisor: {0})".format(
            "unknown" if hv_info.vendor is None else hv_info.vendor))
    nswaps = sys_perfm.ctr["total_imem_limit_hits"].value
    if nswaps:
        swap_time = sys_perfm.ctr["total_imem_limit_time"].value
        swap_bytes = sys_perfm.ctr["total_imem_limit_bytes"].value
        l.append("Image memory limit hits: %d, took: %.1f s, written: %s"
                 % (nswaps, swap_time * 1e-3, format_bin_prefix(swap_bytes, "B")))

    return l

class system_perfmeter(stats_collector):
    def __init__(self):

        stats_collector.__init__(self,
                                 sysperf_clock(),
                                 None,
                                 self.simulation_stopped)

        self.output_win_obj = None
        self.top_win_obj = None
        self.mips_win_obj = None

        self.print_heading = False
        self.print_summary = False
        self.print_summary_always = False
        self.realtime_active = 0
        self.realtime_event_id = None
        self.samples = False

        # User parameters
        self.print_io = False
        self.print_idle_per_cpu = 0
        self.print_jit_vmp_per_cpu = 0
        self.print_ma = 0
        self.print_execution_mode = 0
        self.print_host_ticks_per_cpu = 0
        self.print_cell_host_ticks = 0
        self.host_ticks_raw = False
        self.print_mips = 0
        self.print_emips = 0
        self.sample_time = 0.0
        self.print_imem = 0
        self.print_page_sharing = 0

        self.output_file = ""
        self.textcon_class = SIM_get_class("textcon")

        # Register our event which we use to measure performance
        global measure_event
        if not measure_event:
            measure_event = SIM_register_event(
                "system-perfmeter::measure-sample",
                self.time_queue.classname,
                simics.Sim_EC_Notsaved,
                measure_sample_cb, # Callback
                None, # Destroy
                None, # Get
                None, # Set
                None) # Describe

    # Command backend for the system-perfmeter command
    def activate(self, sample_time,
                 real_time = False,
                 cpu_idle = False,
                 cpu_host_ticks = False,
                 host_ticks_raw = False,
                 cell_host_ticks = False,
                 cell_host_ticks_raw = False,
                 print_summary = False,
                 print_summary_always = False,
                 window = False,
                 top = False,
                 print_disabled = False,
                 print_mips = False,
                 print_emips = False,
                 print_ma = False,
                 print_imem = False,
                 mips_window = False,
                 no_logging = False,
                 print_execution_mode = False,
                 print_module_profile = False,
                 file_name = False,
                 print_page_sharing = False,
                 print_io = False,
                 only_current_cell = False,
                 include_stop_time = False):

        update_execution_mode = (
            self.print_execution_mode != print_execution_mode)

        # Deactivate existing. Must be done before parameters are changed.
        self.deactivate()

        if only_current_cell:
            self.measure_cell = VT_object_cell(self.time_queue)
        else:
            self.measure_cell = None

        # CPU objects may change, e.g., new ones may be added or
        # existing cpu objects may be deleted. Check if queue_objects
        # list has been changed.
        self.update_queue_objects_and_counter()

        # Set user parameters
        self.sample_time = sample_time
        self.print_io = print_io
        self.print_idle_per_cpu = cpu_idle
        self.print_jit_vmp_per_cpu = print_execution_mode
        self.print_host_ticks_per_cpu = (cpu_host_ticks or host_ticks_raw)
        self.host_ticks_raw = host_ticks_raw
        self.print_cell_host_ticks = (cell_host_ticks or cell_host_ticks_raw)
        self.cell_host_ticks_raw = cell_host_ticks_raw
        self.print_mips = print_mips
        self.print_emips = print_emips
        self.print_ma = print_ma
        self.print_disabled = print_disabled
        self.print_summary = print_summary or print_summary_always
        self.print_summary_always = print_summary_always
        self.print_imem = print_imem
        self.mips_window = mips_window
        self.logging = not no_logging
        self.print_execution_mode = print_execution_mode
        self.file_name = file_name
        self.module_profile_enabled = False
        self.print_page_sharing = print_page_sharing
        self.include_stop_time = include_stop_time

        if print_module_profile:
            self.module_profile_activate()
        self.print_module_profile = self.module_profile_enabled

        # Clear host ticks per CPU, if used
        if self.print_host_ticks_per_cpu:
            conf.sim.cpu_tick = [0] * SIM_number_processors()

        if self.print_cell_host_ticks:
            if sys.platform == 'win32':
                print ("Sorry -cell-host-ticks does not work on windows yet,"
                       " ignored")
                self.print_cell_host_ticks = False
            else:
                conf.sim.cell_tick_enable = True

        # If we should present jit stats we need to change debug-level
        if update_execution_mode:
            if print_execution_mode:
                print(("NOTE: Displaying execution modes"
                       +" slightly reduces performance."))

            for cpu in SIM_get_all_processors():
                if hasattr(cpu, 'turbo_count_steps'):
                    cpu.turbo_count_steps = print_execution_mode
                elif hasattr(cpu, 'turbo_debug_level'):
                    cpu.turbo_debug_level = print_execution_mode
            print("Flushing all internal caches")
            SIM_flush_all_caches()

        self.stats_activate()

        # Reset values
        self.print_heading = 0

        if window:
            # Calculate width for the log window based on what will be printed
            width = len(
                "Total-vt Total-rt Sample-vt Sample-rt Slowdown  CPU Idle")
            if self.print_disabled:
                width += len(" Disabled")
            if self.print_execution_mode:
                width += len("  JIT VMP")
            if self.print_mips:
                width += len("     IPS")
            if self.print_emips:
                width += len("    eIPS")
            if self.print_imem:
                width += len(" Mem")
            if self.print_page_sharing:
                width += len("   Shared")
            if self.print_io:
                width += len(" inv I/O")
            if self.print_idle_per_cpu:
                width += len(self.queue_objects) * 8 + 4
            if self.print_jit_vmp_per_cpu:
                width += len(self.queue_objects) * 4 * 2 + 4
            if self.print_host_ticks_per_cpu:
                width += len(self.queue_objects) + 1 * 4 + 4
            if self.print_cell_host_ticks:
                width += (len(self.cell_objects) + 1) * 4 + 4

            width += 1
            if not self.output_win_obj:
                self.create_log_window(width)
            else:
                window.screen_size = [width, window.screen_size[1]]
        else:
            if self.output_win_obj:
                SIM_delete_object(self.output_win_obj)
                self.output_win_obj = None

        if top:
            if not self.top_win_obj:
                self.create_top_window()
        else:
            if self.top_win_obj:
                SIM_delete_object(self.top_win_obj)
                self.top_win_obj = None

        if mips_window:
            if not self.mips_win_obj:
                self.create_mips_window()
        else:
            if self.mips_win_obj:
                SIM_delete_object(self.mips_win_obj)
                self.mips_win_obj = None

        # Set output to go either to stdout or to a specified file
        if file_name:
            try:
                self.output_file = open(file_name, "w")
            except Exception as ex:
                print("Failed opening log file '%s'. " % file_name, end=' ')
                print("Using stdout instead. Error: %s" % ex)
                self.output_file = sys.stdout
        else:
            self.output_file = sys.stdout

        # Present what the processor numbers mean if a feature
        # is used which presents CPU specific data
        self.print_title_cpu_specific_data()

        # Dito for cell columns
        self.print_title_cell_specific_data()

        # Clear host ticks per CPU, if used
        if self.print_host_ticks_per_cpu:
            conf.sim.cpu_tick = [0] * len(self.queue_objects)

        if not real_time:
            self.realtime_active = 0
            print(("Using virtual time sample slice"
                                       " of %fs" % (self.sample_time,)), file=self.output_file)
            SIM_event_post_time(self.time_queue,
                                measure_event,
                                self.time_queue,
                                self.sample_time,
                                self)
        elif not self.realtime_active:
            milli_sec = int(self.sample_time * 1000.0)
            if milli_sec == 0 or milli_sec > 0xffff:
                print(("real-time time slice must be at"
                                           " least 1 ms and less than 65535 ms"), file=self.output_file)
                return
            self.realtime_active = 1
            print(("Using real time sample slice of %fs"
                                       % (milli_sec / 1000.0,)), file=self.output_file)
            self.realtime_event_id = SIM_realtime_event(
                milli_sec, self.measure_realtime_sample, 0, 0,
                "system perfmeter")

    def print_title_cpu_specific_data(self):
        if self.print_idle_per_cpu or self.print_host_ticks_per_cpu:
            print((
                "CPU specific details will be presented. " +
                "The processors to be monitored are:"), file=self.output_file)
            num = 0
            for obj in self.queue_objects:
                print("%2d - %-25s %-15s %6.2f MHz %s" % (
                    num, obj.name, obj.classname, obj.freq_mhz,
                    VT_object_cell(obj).name), file=self.output_file)
                num += 1
            if self.print_host_ticks_per_cpu:
                print("op - Outside processors, cpu-host-ticks on non-processor"
                      " scheduled objects",
                      file=self.output_file)

            print("\nCPU specific detail order: ", end=' ', file=self.output_file)
            if self.print_idle_per_cpu:
                print("Idle ", end=' ', file=self.output_file)
            if self.print_jit_vmp_per_cpu:
                print("JIT VMP ", end=' ', file=self.output_file)
            if self.print_host_ticks_per_cpu:
                print("Ticks ", end=' ', file=self.output_file)
            print(file=self.output_file)

    def print_title_cell_specific_data(self):
        if self.print_cell_host_ticks:
            print((
                "Abbreviated names for cell columns presented:"), file=self.output_file)
            for c in self.cell_objects:
                print((
                    " %s - %s" % (self.cell_object_short_name[c],
                                  c.name)), file=self.output_file)
            print(" %s - Outside cells" % (
                self.cell_object_short_name[None]), file=self.output_file)

    def deactivate(self):
        # Remove any old event, if started again, we will post a new one
        self.remove_event()

        self.realtime_active = 0
        if self.include_stop_time or SIM_simics_is_running():
            self.stats_simulation_stopped(SIM_simics_is_running(),
                                          None, None, None)
        else:
            self.simulation_stopped()
        self.print_summary = 0
        if self.print_host_ticks_per_cpu:
            conf.sim.cpu_tick = []

        if self.print_cell_host_ticks:
            conf.sim.cell_tick_enable = False

        # Remove windows
        if self.output_win_obj:
            SIM_delete_object(self.output_win_obj)
            self.output_win_obj = None
        if self.mips_win_obj:
            SIM_delete_object(self.mips_win_obj)
            self.mips_win_obj = None
        if self.top_win_obj:
            SIM_delete_object(self.top_win_obj)
            self.top_win_obj = None
            conf.sim.cpu_tick = []

        self.stats_deactivate()

    def remove_event(self):
        SIM_event_cancel_time(self.time_queue,
                              measure_event,
                              self.time_queue,
                              None,
                              None)
        if self.realtime_event_id:
            SIM_cancel_realtime_event(self.realtime_event_id)
            self.realtime_event_id = None

    def get_recorder(self):
        try:
            recorder = list(SIM_object_iterator_for_class('recorder'))[0]
        except (IndexError, LookupError):
            recorder = SIM_create_object(
                "recorder",
                get_available_object_name("rec"),
                [["queue", sysperf_clock()]])
        return recorder

    def create_mips_window(self):
        args = [["window_title", "System Perfmeter MIPS"],
                ["screen_size", [42, 1]],
                ["visible", True]]
        obj = SIM_create_object(self.textcon_class, "systemperf_mips_win",
                                [["recorder", self.get_recorder()],
                                 ["queue", sysperf_clock()]] + args)
        VT_set_object_checkpointable(obj, False)
        con_iface = obj.iface.serial_device
        self.mips_win_obj = obj
        self.mips_win_iface = con_iface


    def create_log_window(self, width):
        args = [["window_title", "System Perfmeter Output"],
                ["screen_size", [width, 24]],
                ["visible", True]]
        obj = SIM_create_object(self.textcon_class, "systemperf_win",
                                [["recorder", self.get_recorder()],
                                 ["queue", sysperf_clock()]] + args)
        VT_set_object_checkpointable(obj, False)
        con_iface = obj.iface.serial_device
        self.output_win_obj = obj
        self.output_win_iface = con_iface

    def create_top_window(self):
        height = len(self.queue_objects) + 6
        if self.print_module_profile:
            height += num_top_modules + 2
        if self.print_execution_mode:
            height += 2 + len(self.queue_objects)

        args = [["window_title", "System Perfmeter - Top"],
                ["screen_size", [92, height]],
                ["visible", True]]
        obj = SIM_create_object(self.textcon_class, "systemperf_top_win",
                                [["recorder", self.get_recorder()],
                                 ["queue", sysperf_clock()]] + args)
        VT_set_object_checkpointable(obj, False)
        con_iface = obj.iface.serial_device
        self.top_win_obj = obj
        self.top_win_iface = con_iface
        # Activate host tick measurement even if user didn't
        conf.sim.cpu_tick = [0] * len(self.queue_objects)
        print(f"clearing cpu_ticks {len(conf.sim.cpu_tick)} elements")

    # Called from system-perfmeter-summary command
    def async_print_summary(self):
        if self.include_stop_time or SIM_simics_is_running():
            # update counters if we are running
            self.stats_update_counters(COUNTER_CAUSE_UPDATE)
        self.do_print_summary()

    def do_print_summary(self):
        tot_vtime = self.ctr["sim_time"].value
        tot_rtime = self.ctr["host_rtime"].value
        tot_utime = self.ctr["host_utime"].value
        tot_stime = self.ctr["host_stime"].value

        if not self.include_stop_time:
            tot_rtime -= self.total_prompt_rtime
            tot_utime -= self.total_prompt_utime
            tot_stime -= self.total_prompt_stime

        tot_steps = self.ctr["total_steps"].value
        tot_idle_steps = self.ctr["total_idle_steps"].value

        if not (tot_vtime > 0 and tot_rtime > 0):
            return

        out = self.output_file
        print("SystemPerf: Performance summary:", file=out)
        print("--------------------------------", file=out)

        # Host/target/features for this run
        print("SystemPerf: Target: %s" % get_target_info(), file=out)
        print("SystemPerf: Running on: %s" % get_host_info(), file=out)
        print("SystemPerf: Threads: %s" % get_thread_info(), file=out)
        for l in get_slow_settings(self):
            print("SystemPerf: Degrades performance: %s" % l, file=out)

        slowdown = tot_rtime / tot_vtime
        host_cpu = 100.0 * (tot_utime + tot_stime) / tot_rtime

        print(("SystemPerf: Virtual (target) time"
                       " elapsed: %9.2f" % tot_vtime), file=out)
        print(("SystemPerf: Real (host) time elapsed:"
                       "      %9.2f" % tot_rtime), file=out)
        print(("SystemPerf: Slowdown:"
                        "                      %9.2f"
                        % slowdown), file=out)

        if self.print_execution_mode and tot_steps > 0:
            idle_percent = 100.0 * tot_idle_steps / tot_steps
            tot_turbo_steps = self.ctr["total_turbo_steps"].value
            turbo_percent = 100.0 * tot_turbo_steps / tot_steps
            tot_vmp_steps = self.ctr["total_vmp_steps"].value
            vmp_percent = 100.0 * tot_vmp_steps / tot_steps
            int_percent = (100.0
                           * (tot_steps - (tot_idle_steps + tot_turbo_steps
                                           + tot_vmp_steps))
                           / tot_steps)
            print(("SystemPerf: System execution idle:"
                          "         %9.2f%%" % idle_percent), file=out)
            print(("SystemPerf: System execution JIT:"
                          "          %9.2f%%" % turbo_percent), file=out)
            print(("SystemPerf: System execution VMP:"
                          "          %9.2f%%" % vmp_percent), file=out)
            print(("SystemPerf: System execution interpreter:"
                          "  %9.2f%%" % int_percent), file=out)

        if self.print_ma and tot_steps > 0:
            tot_ma_steps = self.ctr["total_ma_steps"].value
            ma_percent = 100.0 * tot_ma_steps / tot_steps
            print(("SystemPerf: System multicore accelerator:"
                          "  %9.2f%%" % ma_percent), file=out)

        print(("SystemPerf: Host CPU utilization:"
                      "          %9.2f%%" % host_cpu), file=out)
        if self.print_mips:
            ipsi = tot_steps / tot_rtime
            total_ipsi = ips_to_string_summary(ipsi)
            print(("SystemPerf: IPS (including idle"
                           " instr.):    %9s" % total_ipsi), file=out)
        if self.print_emips:
            ipse = (tot_steps - tot_idle_steps) / tot_rtime
            total_ipse = ips_to_string_summary(ipse)
            print(("SystemPerf: IPSe (without idle"
                           " instr.):     %9s" % total_ipse), file=out)

        if self.print_io:
            tot_io = self.ctr["total_io"].value
            if tot_io:
                inv_io = tot_steps / tot_io
                inv_io_str = ips_to_string_summary(inv_io)
            else:
                inv_io_str = "NaN"
            print(("SystemPerf: Steps per I/O: %26s" % inv_io_str), file=out)

        if self.print_imem:
            nswaps = self.ctr["total_imem_limit_hits"].value
            print(("SystemPerf: Image memory limit hit (times):"
                          " %8d" % (nswaps,)), file=out)
            if nswaps:
                swap_time = self.ctr["total_imem_limit_time"].value
                swap_bytes = self.ctr["total_imem_limit_bytes"].value
                print(("SystemPerf:   Time spent swapping (s):"
                              " %13.3f (avg %.1f ms)" %
                              (swap_time * 1e-3, float(swap_time) / nswaps)), file=out)
                print(("SystemPerf:   Data written:"
                              " %24s (avg %s)" %
                              (format_bin_prefix(swap_bytes, "B"),
                               format_bin_prefix(swap_bytes // nswaps, "B"))), file=out)

        if (self.print_host_ticks_per_cpu or self.print_idle_per_cpu
            or self.print_jit_vmp_per_cpu):
            total_ticks = self.ctr["total_host_ticks"].value
            for id in range(len(self.queue_objects)):
                cpu = self.queue_objects[id]
                print((
                    "SystemPerf:%2d - %-25s (%6.2f MHz)"
                    % (id, cpu.name, cpu.freq_mhz)), end=' ', file=out)

                if self.print_idle_per_cpu:
                    steps = self.ctr["steps"][cpu].value
                    idle  = self.ctr["idle_steps"][cpu].value
                    try:
                        idle_percent = 100.0 * idle / steps
                    except ZeroDivisionError:
                        idle_percent = 0.0

                    print((
                        "Idle: %3.0f%%" % (idle_percent,)), end=' ', file=out)

                if self.print_jit_vmp_per_cpu:
                    steps = self.ctr["steps"][cpu].value
                    jit = self.ctr["jit_steps"][cpu].value
                    try:
                        jit_percent = 100.0 * jit / steps
                    except ZeroDivisionError:
                        jit_percent = 0.0
                    vmp = self.ctr["vmp_steps"][cpu].value
                    try:
                        vmp_percent = 100.0 * vmp / steps
                    except ZeroDivisionError:
                        vmp_percent = 0.0
                    print("JIT: %3.0f%%" % (jit_percent,), end=' ', file=out)
                    print("VMP: %3.0f%%" % (vmp_percent,), end=' ', file=out)

                if self.print_host_ticks_per_cpu:
                    ticks = self.ctr["host_ticks"][cpu].value
                    try:
                        host_percent = 100.0 * ticks / total_ticks
                    except ZeroDivisionError:
                        host_percent = 0.0
                    print(("Host ticks: %9d (%5.1f%%)"
                                   % (ticks, host_percent,)), end=' ', file=out)

                print(file=out)

            if self.print_host_ticks_per_cpu:
                missed_ticks = self.ctr["missed_host_ticks"].value
                missed_percent = 100.0 * missed_ticks / total_ticks if total_ticks else 0.0
                print("SystemPerf:op - %-38s Host ticks: %9d (%5.1f%%)" % (
                    "Outside processors", missed_ticks, missed_percent), file=out)

        if self.print_cell_host_ticks:
            total_ticks = self.ctr["cell_total_host_ticks"].value
            for cell in self.cell_objects + [None]:
                ticks = self.ctr["cell_host_ticks"][cell].value
                cellname = "Outside cells" if not cell else cell.name
                percent = 0 if not total_ticks else 100.0 * ticks / total_ticks
                print((
                    "SystemPerf:%3s - %-25s Host ticks: %9d (%5.1f%%)" % (
                        self.cell_object_short_name[cell],
                        cellname, ticks, percent)), file=out)

        if self.print_module_profile:
            profile_data = self.module_profile.get_profile()
            profile_data.sort(key = cmp_to_key(profile_compare_accum))
            total_samples_accum = 0
            for (name, turbo, samples, accum) in profile_data:
                total_samples_accum += accum
            if not total_samples_accum:
                print((
                    "SystemPerf: No Module CPU usage available (no ticks)"), file=out)
            else:
                print((
                    "SystemPerf: Module CPU usage (%d entries):"
                    % len(profile_data)), file=out)
                for id in range(len(profile_data)):
                    name = profile_data[id][0]
                    print((
                        "SystemPerf: %-40s  %6s%%"
                        % (name,
                           ("%2.2f" % (profile_data[id][3] * 100.0
                                       / total_samples_accum)))), file=out)
        # mark the end of summary (bug 21532)
        if self.file_name:
            print("SystemPerf: End of summary", file=out)

    def simulation_stopped(self):
        if self.print_summary and (self.samples or self.print_summary_always):
            self.do_print_summary()
        self.samples = False
        # Do not mess up the output file when there are multiple writers to it.
        if self.output_file:
            self.output_file.flush()

    # Generic output routine, prints the line either in Simics terminal
    # or the dedicated output window.
    def output(self, output_str):
        if self.output_win_obj:
            iface = self.output_win_iface
            for c in output_str:
                iface.write(ord(c))
            iface.write(ord('\r'))
            iface.write(ord('\n'))
            if self.file_name:
                print("SystemPerf:", end=' ', file=self.output_file)
                print(output_str, file=self.output_file)
        else:
            print("SystemPerf:", end=' ', file=self.output_file)
            print(output_str, file=self.output_file)

    def top_output(self, top_str_list):
        win = self.top_win_obj
        iface = self.top_win_iface
        fmt = "\033[H"                  # Cursor position to 0,0
        fmt += "\033[2J"                # Clear entire screen
        for c in fmt:
            iface.write(ord(c))
        width = win.screen_size[0]
        for line in top_str_list:
            pad = " " * (width - len(line))
            for c in line + pad:
                iface.write(ord(c))
            iface.write(ord('\r'))
            iface.write(ord('\n'))

    def mips_win_output(self, line):
        iface = self.mips_win_iface
        fmt = "\033[H"                  # Cursor position to 0,0
        fmt += "\033[2J"                # Clear entire screen
        for c in fmt:
            iface.write(ord(c))
        iface.write(ord('\r'))
        iface.write(ord('\n'))
        for c in line:
            iface.write(ord(c))


    def generic_measure(self):
        self.samples = True
        vals = self.stats_generic_measure()

        if vals["tot_sd"] == "NaN":
            total_slowdown_str = vals["tot_sd"]
        else:
            total_slowdown_str = "%4.2f" % vals["tot_sd"]

        if vals["del_sd"] == "NaN":
            delta_slowdown_str = vals["del_sd"]
        else:
            delta_slowdown_str = "%4.2f" % vals["del_sd"]

        number_processors = len(self.queue_objects)
        if self.top_win_obj:
            lines = number_processors + 5
            if self.print_module_profile:
                lines += num_top_modules + 2
            if self.print_execution_mode:
                lines += 2 + number_processors
                mode_offset = 3
            else:
                mode_offset = 0
            top_list = [""] * lines
            top_list[0] = ("Total time,  Virtual:%6.1fs "
                           "Real:%6.1fs (slowdown %s) "
                           "User:%6.1fs "
                           "[CPU:%5.1f%%]"
                           % (vals["tot_vt"],
                              vals["tot_rt"],
                              total_slowdown_str,
                              vals["tot_ut"],
                              vals["tot_host_cpu"]))
            top_list[1] = ("Sample time, Virtual:%6.1fs "
                           "Real:%6.1fs (slowdown %s) "
                           "User:%6.1fs "
                           "[CPU:%5.1f%%]"
                           % (vals["del_vt"],
                              vals["del_rt"],
                              delta_slowdown_str,
                              vals["del_ut"],
                              vals["del_host_cpu"]))

            top_list[3] = "CPU    MHz       Idle%           Host%      Name"

            host_ticks_total = self.ctr["total_host_ticks"].value
            host_ticks_sample = self.ctr["total_host_ticks"].delta_value

            for cpu in self.queue_objects:
                if not hasattr(cpu.iface, 'processor_info'):
                    continue
                id = SIM_get_processor_number(cpu)
                other_total_count = 0
                other_sample_count = 0
                idle_total_count = self.ctr["idle_steps"][cpu].value
                other_total_count += idle_total_count
                steps_total_count = self.ctr["steps"][cpu].value
                steps_sample_count = self.ctr["steps"][cpu].delta_value
                try:
                    idle_total = 100.0 * idle_total_count / steps_total_count
                except ZeroDivisionError:
                    idle_total = 0.0

                idle_sample_count = self.ctr["idle_steps"][cpu].delta_value
                other_sample_count += idle_sample_count
                try:
                    idle_sample = 100.0 * idle_sample_count / steps_sample_count
                except ZeroDivisionError:
                    idle_sample = 0.0

                jit_total_count = self.ctr["jit_steps"][cpu].value
                other_total_count += jit_total_count
                try:
                    jit_total = 100.0 * jit_total_count / steps_total_count
                except ZeroDivisionError:
                    jit_total = 0.0

                jit_sample_count = self.ctr["jit_steps"][cpu].delta_value
                other_sample_count += jit_sample_count
                try:
                    jit_sample = 100.0 * jit_sample_count / steps_sample_count
                except ZeroDivisionError:
                    jit_sample = 0.0

                vmp_total_count = self.ctr["vmp_steps"][cpu].value
                other_total_count += vmp_total_count
                try:
                    vmp_total = 100.0 * vmp_total_count / steps_total_count
                except ZeroDivisionError:
                    vmp_total = 0.0

                vmp_sample_count = self.ctr["vmp_steps"][cpu].delta_value
                other_sample_count += vmp_sample_count
                try:
                    vmp_sample = 100.0 * vmp_sample_count / steps_sample_count
                except ZeroDivisionError:
                    vmp_sample = 0.0

                interpreter_total_count = steps_total_count - other_total_count
                interpreter_sample_count = (steps_sample_count
                                            - other_sample_count)
                try:
                    interpreter_total = (
                        100.0 * interpreter_total_count / steps_total_count)
                except ZeroDivisionError:
                    interpreter_total = 0.0

                try:
                    interpreter_sample = (
                        100.0 * interpreter_sample_count / steps_sample_count)
                except ZeroDivisionError:
                    interpreter_sample = 0.0

                try:
                    ticks_total = (100.0 * self.ctr["host_ticks"][cpu].value
                                   / host_ticks_total)
                except ZeroDivisionError:
                    ticks_total = 0

                try:
                    ticks_sample = (100.0
                                    * self.ctr["host_ticks"][cpu].delta_value
                                    / host_ticks_sample)
                except ZeroDivisionError:
                    ticks_sample = 0

                top_list[4 + id] = (
                    "%3d %7.1f %5.1f%% (%5.1f%%) %5.1f%% (%5.1f%%) %s"
                    % (id, cpu.freq_mhz, idle_sample, idle_total, ticks_sample,
                       ticks_total, cpu.name))
                if self.print_execution_mode:
                    top_list[4 + number_processors + 3 + id] = (
                      "  CPU%3d       %5.1f%% (%5.1f%%) %5.1f%% (%5.1f%%)"
                      " %5.1f%% (%5.1f%%) %5.1f%% (%5.1f%%)"
                      % (id, idle_sample, idle_total, jit_sample, jit_total,
                         vmp_sample, vmp_total,
                         interpreter_sample, interpreter_total))

            if self.print_execution_mode:
                try:
                    idle_sample = (100.0 * vals["del_idle"] / vals["del_steps"])
                except ZeroDivisionError:
                    idle_sample = 0.0

                try:
                    idle_total = (100.0 * vals["tot_idle"] / vals["tot_steps"])
                except ZeroDivisionError:
                    idle_total = 0.0

                try:
                    jit_sample = (100.0 * vals["del_turbo_steps"]
                                  / vals["del_steps"])
                except ZeroDivisionError:
                    jit_sample = 0.0

                try:
                    jit_total = (100.0 * vals["tot_turbo_steps"]
                                 / vals["tot_steps"])
                except ZeroDivisionError:
                    jit_total = 0.0

                try:
                    vmp_sample = (100.0 * vals["del_vmp_steps"]
                                  / vals["del_steps"])
                except ZeroDivisionError:
                    vmp_sample = 0.0

                try:
                    vmp_total = (100.0 * vals["tot_vmp_steps"]
                                 / vals["tot_steps"])
                except ZeroDivisionError:
                    vmp_total = 0.0

                other_sample = (vals["del_idle"] + vals["del_turbo_steps"]
                                + vals["del_vmp_steps"])
                try:
                    interpreter_sample = (
                      100.0 * (vals["del_steps"] - other_sample)
                      / vals["del_steps"])
                except ZeroDivisionError:
                    interpreter_sample = 0.0

                other_total = (vals["tot_idle"] + vals["tot_turbo_steps"]
                               + vals["tot_vmp_steps"])
                try:
                    interpreter_total = (100.0
                                         * (vals["tot_steps"] - other_total)
                                         / vals["tot_steps"])
                except ZeroDivisionError:
                    interpreter_total = 0.0

                top_list[4 + number_processors + 1] = (
                    "Execution mode      Idle%           JIT%            VMP%"
                    "         Interpreter%")
                top_list[4 + number_processors + 2] = (
                    "  Overall      %5.1f%% (%5.1f%%) %5.1f%% (%5.1f%%) %5.1f%%"
                    " (%5.1f%%) %5.1f%% (%5.1f%%)"
                    % (idle_sample, idle_total, jit_sample, jit_total,
                       vmp_sample, vmp_total,
                       interpreter_sample, interpreter_total))

            if self.print_module_profile:
                top_list[4 + mode_offset + number_processors + 1] = (
                    "%-40s   CPU%%  Accum-CPU%%" % "Module")
                profile_data = list(vals["module_profile"])
                profile_data.sort(key = cmp_to_key(profile_compare))
                total_samples = 0
                total_samples_accum = 0
                for (name, turbo, samples, accum) in profile_data:
                    total_samples += samples
                    total_samples_accum += accum
                for id in range(num_top_modules):
                    if len(profile_data) > id:
                        name = profile_data[id][0]
                        if total_samples > 0:
                            sample_percent = ("%2.2f"
                                              % (profile_data[id][2] * 100.0
                                                 / total_samples))
                        else:
                            sample_percent = "0"
                        if total_samples_accum > 0:
                            total_percent = ("%2.2f"
                                             % (profile_data[id][3] * 100.0
                                                / total_samples_accum))
                        else:
                            total_percent = "0"
                        top_list[6 + mode_offset + number_processors + id] = (
                            "%-40s %6s      %6s"
                            % (name, sample_percent, total_percent))
            self.top_output(top_list)

        if vals["del_ipsi"] == "NaN":
            delta_ipsi_str = vals["del_ipsi"]
        else:
            delta_ipsi_str =  ips_to_string(vals["del_ipsi"])

        if vals["del_ipse"] == "NaN":
            delta_ipse_str = vals["del_ipse"]
        else:
            delta_ipse_str = ips_to_string(vals["del_ipse"])

        if vals["del_steps"] > 0:
            delta_ma = vals["del_ma"] * 100.0 / vals["del_steps"]
        else:
            delta_ma = 0

        if vals["tot_ipsi"] == "NaN":
            total_ipsi_str = vals["tot_ipsi"]
        else:
            total_ipsi_str = ips_to_string(vals["tot_ipsi"])

        if vals["del_sd"] == "NaN":
            delta_slowdown_str = vals["del_sd"]
        else:
            delta_slowdown_str = "%7.2f" % vals["del_sd"]

        if self.mips_win_obj:
            mips_line = "IPS: %7s (%7s average, %3.0f%% idle)" % (
                delta_ipsi_str, total_ipsi_str, vals["idle"])
            self.mips_win_output(mips_line)

        if self.logging:
            # Format result
            head = ""
            line = ""
            res = ""

            head += "Total-vt Total-rt "
            line += "-------- -------- "
            res  += "%7.1fs %7.1fs " % (vals["tot_vt"], vals["tot_rt"])

            head += "Sample-vt Sample-rt Slowdown  CPU Idle"
            line += "--------- --------- -------- ---- ----"

            res += "%8.2fs %8.2fs %8s %4s %3.0f%%" % (
                vals["del_vt"], vals["del_rt"], delta_slowdown_str,
                int(vals["del_host_cpu"]),
                vals["idle"])

            if self.print_disabled:
                head += " Disabled"
                line += " --------"
                res  += " %2d (%2.0f%%)" % (self.disabled_cpus,
                                            vals["disabled"])
            if self.print_execution_mode:
                head += "  JIT  VMP"
                line += " ---- ----"
                del_steps = vals["del_steps"]
                if del_steps > 0:
                    del_turbo = vals["del_turbo_steps"] * 100.0 / del_steps
                    del_vmp = vals["del_vmp_steps"] * 100.0 / del_steps
                else:
                    del_turbo = 0
                    del_vmp = 0
                res  += " %3.0f%% %3.0f%%" % (del_turbo, del_vmp)
            if self.print_mips:
                head += "     IPS"
                line += "   -----"
                res += " %7s" % delta_ipsi_str
            if self.print_emips:
                head += "    eIPS"
                line += "   -----"
                res += " %7s" % delta_ipse_str
            if self.print_ma:
                head += "   MA"
                line += " ----"
                res += " %3.0f%%" % delta_ma
            if self.print_imem:
                head += " Mem"
                line += " ---"
                res  += " %2d%%" % (vals["image_mem"])
            if self.print_page_sharing:
                save = vals["page_sharing_savings"]
                # use replace to save space and fit into 8 symbols
                save_str = format_bin_prefix(save, "").replace(" ", "")
                head += "   Shared"
                line += " --------"
                res += " %8s" % save_str

            del_steps = 0
            for cpu in self.queue_objects:
                if (hasattr(cpu.iface, 'processor_info')
                    and not cpu.iface.processor_info.get_enabled()):
                    continue
                cpu_steps = self.ctr["steps"][cpu].delta_value
                del_steps += cpu_steps
            vals["del_steps"] = del_steps

            if self.print_io:
                head += "   i I/O"
                line += "   -----"
                del_io = vals["del_io"]
                if del_io:
                    delta_io = ips_to_string(del_steps * 1.0 / del_io)
                else:
                    delta_io = "NaN"
                res += " %7s" % delta_io

            if self.print_idle_per_cpu:
                head += " ["
                line += "  "
                for i in range(number_processors):
                    head += "%4d" % i
                    line += " ---"
                line += "  "
                head += " ]"
                res += " [ "
                for cpu in self.queue_objects:
                    cpu_del_steps = self.ctr["steps"][cpu].delta_value
                    if cpu_del_steps == 0:
                        res += "DIS "
                        continue
                    delta_idle_steps = self.ctr["idle_steps"][cpu].delta_value
                    if cpu_del_steps:
                        vals["idle"] = 100.0 * delta_idle_steps / cpu_del_steps
                    else:
                        vals["idle"] = 0.0
                    res += "%3.0f " % (vals["idle"])
                res += "]"

            if self.print_jit_vmp_per_cpu:
                for kind in ("jit", "vmp"):
                    head += " ["
                    line += "  "
                    for i in range(number_processors):
                        head += "%4d" % i
                        line += " ---"
                    line += "  "
                    head += " ]"

                    res += " [ "
                    for cpu in self.queue_objects:
                        if (hasattr(cpu.iface, 'processor_info')
                            and not cpu.iface.processor_info.get_enabled()):
                            res += "DIS "
                            continue
                        delta_steps = (
                            self.ctr["%s_steps" % kind][cpu].delta_value)
                        cpu_del_steps = self.ctr["steps"][cpu].delta_value
                        if cpu_del_steps:
                            vals[kind] = 100.0 * delta_steps / cpu_del_steps
                        else:
                            vals[kind] = 0.0
                        res += "%3.0f " % (vals[kind])
                    res += "]"

            if self.print_host_ticks_per_cpu:
                head += " ["
                line += "  "
                for i in range(number_processors):
                    head += "%4d" % i
                    line += " ---"
                head += "  op ]"
                line += " --- "
                res += " [ "
                delta_total_ticks = self.ctr["total_host_ticks"].delta_value
                for cpu in self.queue_objects:
                    delta_host_ticks = self.ctr["host_ticks"][cpu].delta_value
                    if delta_total_ticks != 0:
                        load_percent = (100.0 * delta_host_ticks
                                        / delta_total_ticks)
                    else:
                        load_percent = 0
                    if self.host_ticks_raw:
                        res += "%d " % delta_host_ticks
                    else:
                        res += "%3.0f " % (load_percent)

                delta_missed_host_ticks = self.ctr["missed_host_ticks"].delta_value
                if delta_total_ticks != 0:
                    miss_percent = (100.0 * delta_missed_host_ticks
                                    / delta_total_ticks)
                else:
                    miss_percent = 0
                if self.host_ticks_raw:
                    res += "%d " % delta_missed_host_ticks
                else:
                    res += "%3.0f " % (miss_percent)

                res += "]"

            if self.print_cell_host_ticks:
                head += " ["
                line += "  "
                for cell in self.cell_objects + [None]:
                    head += "%4s" % self.cell_object_short_name[cell]
                    line += " ---"
                head += " ]"
                res += " [ "
                for cell in self.cell_objects + [None]:
                    delta_cell = self.ctr["cell_host_ticks"][cell].delta_value
                    delta_total = self.ctr["cell_total_host_ticks"].delta_value
                    if delta_total != 0:
                        load_percent = (100.0 * delta_cell / delta_total)
                    else:
                        load_percent = 0.0
                    if self.cell_host_ticks_raw:
                        res += "%3d " % delta_cell
                    else:
                        res += "%3.0f " % (load_percent)
                res += "]"

            # Present the result
            if (self.print_heading % 20 == 0):
                self.output(head)
                self.output(line)
            self.output(res)
            self.print_heading = ((self.print_heading + 1) % 20)

    # Called by an event when a sample cycle has expired
    # Gather all information and present the current performance
    def measure_sample(self, cpu, param):
        self.generic_measure()
        # Repost ourselves
        SIM_event_post_time(self.time_queue,
                            measure_event,
                            self.time_queue,
                            self.sample_time,
                            self)

    # Called by realtime events
    def measure_realtime_sample(self, data):
        if not self.realtime_active:
            return
        if self.include_stop_time or SIM_simics_is_running():
            self.generic_measure()
        # Repost
        milli_sec = int(self.sample_time * 1000.0)
        self.realtime_event_id = SIM_realtime_event(
            milli_sec, self.measure_realtime_sample, 0, 0, "system perfmeter")
