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


from abc import ABC, abstractmethod
import collections
import timeit

import probes
import conf
from simics import *

from . import common
from . import sprobes

REALTIME_SYNC_MODE = "realtime-sync"
REALTIME_MODE = "realtime"
VIRTUAL_MODE = "virtual"
NOTIFIER_MODE = "notifier"
TIMESTAMP_MODE = "time-stamp"

class probe_sampler(ABC):
    __slots__ = ("obj", "mode", "interval", "clock",
                 "notifier_type", "notifier_obj",
                 "timestamp_file_name", "sprobes",
                 "presentation", "sampling",
                 "start_sampling_time", "acc_sampling_time",
                 "start_collecting_time", "acc_collecting_time",
                 "stop_hap_id", "probe_sampler_cache_iface")

    cls = confclass()

    cls.attr.mode(
        "s",
        doc="Sampling mode used.")
    cls.attr.interval(
        "f",
        default=1.0,
        doc="Sampling interval.")
    cls.attr.clock(
        "o|n",
        default=None,
        doc="Master clock.")
    cls.attr.notifier_type(
        "s|n",
        default=None,
        doc="Notifier type.")
    cls.attr.notifier_obj(
        "o|n",
        default=None,
        doc="Object where the notifier is installed.")
    cls.attr.timestamp_file_name(
        "s|n",
        default=None,
        doc="Sampler timestamp file to read/write.")

    @cls.class_constructor
    def class_init(confcls):
        # Create an event for the virtual time sampler
        probe_sampler.VirtualTimeSampling.eventclass = SIM_register_event(
            "probe_sampler:virtual-sampler", confcls, 0,
            probe_sampler.VirtualTimeSampling.class_event,
            None, None, None, None)

        # Create an event for the real time sampler
        probe_sampler.SyncedRealTimeSampling.eventclass = SIM_register_event(
            "probe_sampler:realtime-sync", confcls, 0,
            probe_sampler.SyncedRealTimeSampling.class_sync_event,
            None, None, None, None)

        # Create an event for the Time-stamp sampler
        probe_sampler.TimestampSampling.eventclass = SIM_register_event(
            "probe_sampler:timestamp-sampler", confcls, 0,
            probe_sampler.TimestampSampling.class_event,
            None, None, None, None)

    @cls.attr.notifier_type.setter
    def set_notifier_type(self, notifier_type):
        if notifier_type and notifier_type not in [notif[0] for notif in conf.sim.notifier_list]:
            SIM_attribute_error(f"Unknown notifier type: {notifier_type}")
            return Sim_Set_Illegal_Value
        self.notifier_type = notifier_type
        return Sim_Set_Ok

    @cls.init
    def initialize(self):
        self.sprobes = sprobes.SampledProbes()
        self.presentation = None
        self.sampling = None
        self.start_sampling_time = 0.0
        self.acc_sampling_time = 0.0
        self.start_collecting_time = 0.0
        self.acc_collecting_time = 0.0
        self.stop_hap_id = None
        self.probe_sampler_cache_iface = conf.probes.iface.probe_sampler_cache

    @cls.finalize
    def finalize_instance(self):
        probes.register_probe_delete_cb(self.probe_proxy_deleted)
        self.start()

    @cls.deinit
    def deinit(self):
        if SIM_object_is_configured(self.obj):
            self.terminate()

    @cls.ports.sampling_time_probe.probe.value
    def sampling_time_probe_value(self):
        return self.acc_sampling_time

    @cls.ports.sampling_time_probe.probe.properties
    def sampling_time_probe_properties(self):
        return common.listify([
            (Probe_Key_Kind, "probe_sampler.sampling.time"),
            (Probe_Key_Display_Name, "Probe Sampling Time"),
            (Probe_Key_Unit, "hh:mm:ss.d"),
            (Probe_Key_Time_Format, True),
            (Probe_Key_Description,
             "Time spent sampling probes."),
            (Probe_Key_Type, "float"),
            (Probe_Key_Categories, ["time"]),
            (Probe_Key_Width, 11),
            (Probe_Key_Aggregates, [
                [
                    (Probe_Key_Kind, "sim.probe_sampler.sampling.time"),
                    (Probe_Key_Aggregate_Scope, "global"),
                    (Probe_Key_Owner_Object, conf.sim),
                    (Probe_Key_Aggregate_Function, "sum"),
                    (Probe_Key_Description,
                     "Total time spent sampling probes (all probe-samplers)")
                ]
            ]),
        ])

    @cls.ports.collecting_time_probe.probe.value
    def collecting_time_probe_value(self):
        return self.acc_collecting_time

    @cls.ports.collecting_time_probe.probe.properties
    def collecting_time_probe_properties(self):
        return common.listify([
            (Probe_Key_Kind, "probe_sampler.collecting.time"),
            (Probe_Key_Display_Name, "Probe Collecting Time"),
            (Probe_Key_Unit, "hh:mm:ss.d"),
            (Probe_Key_Time_Format, True),
            (Probe_Key_Description,
             "Time spent collecting probes."),
            (Probe_Key_Type, "float"),
            (Probe_Key_Categories, ["time"]),
            (Probe_Key_Width, 11),
            (Probe_Key_Aggregates, [
                [
                    (Probe_Key_Kind, "sim.probe_sampler.collecting.time"),
                    (Probe_Key_Aggregate_Scope, "global"),
                    (Probe_Key_Owner_Object, conf.sim),
                    (Probe_Key_Aggregate_Function, "sum"),
                    (Probe_Key_Description,
                     "Total time spent collecting probes (all probe-samplers)")
                ]
            ]),
        ])

    def measure_start_sampling(self):
        self.start_sampling_time = timeit.default_timer()

    def measure_stop_sampling(self):
        stop_sampling_time = timeit.default_timer()
        self.acc_sampling_time += stop_sampling_time - self.start_sampling_time

    def measure_start_collecting(self):
        self.start_collecting_time = timeit.default_timer()

    def measure_stop_collecting(self):
        stop_collecting_time = timeit.default_timer()
        self.acc_collecting_time += stop_collecting_time - self.start_collecting_time

    def sprobes_matching_name(self, name):
        return [sp for sp in self.sampled_probes()
                if sp.unique_id_matches_name(name)]

    def sampled_probes(self):
        return self.sprobes.all()

    def probes_updated(self):
        if self.sampling:
            self.sampling.probes_updated()
        self.presentation.update_probes(self.sampled_probes())

    def add_probes(self, mode, probe_kinds_to_add, probes_to_add, hidden,
                   no_sampling):

        def add_probe_proxies(proxies):
            added_cli_ids = []
            for proxy in sorted(proxies, key=lambda proxy: proxy.cli_id):
                try:
                    sp = self.sprobes.create(proxy, mode, hidden, no_sampling)
                except (sprobes.IllegalProbeValue,
                        sprobes.IllegalProbeMode, sprobes.ProbeAlreadySampled) as msg:
                    SIM_log_info(
                        1, self.obj, 0, f"Ignoring probe {proxy.cli_id}: {msg}")
                    continue
                self.sprobes.add(sp)
                added_cli_ids.append(proxy.cli_id)
            return added_cli_ids

        def add_probe_kind(probe_kind):
            proxies = common.get_matching_probe_kinds(probe_kind)
            if not proxies:
                SIM_log_info(1, self.obj, 0,
                             f"cannot find any probe matching: {probe_kind}")
                return []
            return add_probe_proxies(proxies)

        def add_probe(probe):
            proxies = common.get_matching_probes(probe)
            if not proxies:
                SIM_log_info(1, self.obj, 0,
                             f"cannot find any probe matching: {probe}")
                return []
            return add_probe_proxies(proxies)

        added_cli_ids = []
        for kind in probe_kinds_to_add:
            cli_ids = add_probe_kind(kind)
            added_cli_ids.extend(cli_ids)

        for probe in probes_to_add:
            cli_ids = add_probe(probe)
            added_cli_ids.extend(cli_ids)

        self.probes_updated()
        return sorted(added_cli_ids)

    def remove_probes(self, mode, probe_kinds_to_remove, probes_to_remove):

        def remove_probe_kind(kind):
            removed_sps = []
            for sp in self.sampled_probes():
                if (mode == sp.mode and
                    common.is_probe_kind_matching(kind, sp.probe_proxy)):
                    removed_sps.append(sp)

            removed_cli_ids = []
            for sp in removed_sps:
                is_removed = self.sprobes.remove(sp)
                if is_removed:
                    removed_cli_ids.append(sp.probe_proxy.cli_id)
            return sorted(removed_cli_ids)

        def remove_probe(probe_name):
            removed_sps = []
            for sp in self.sampled_probes():
                if (mode == sp.mode and
                    common.is_cli_id_matching(probe_name, sp.probe_proxy)):
                    removed_sps.append(sp)

            removed_cli_ids = []
            for sp in removed_sps:
                is_removed = self.sprobes.remove(sp)
                if is_removed:
                    removed_cli_ids.append(sp.probe_proxy.cli_id)
            return sorted(removed_cli_ids)

        removed_cli_ids = []
        for kind in probe_kinds_to_remove:
            cli_ids = remove_probe_kind(kind)
            removed_cli_ids.extend(cli_ids)

        for probe_name in probes_to_remove:
            cli_ids = remove_probe(probe_name)
            removed_cli_ids.extend(cli_ids)

        self.probes_updated()
        return removed_cli_ids

    def create_sampling(self):
        if self.mode == REALTIME_SYNC_MODE:
            return probe_sampler.SyncedRealTimeSampling(self, self.interval,
                                                        self.clock,
                                                        self.timestamp_file_name)
        if self.mode == REALTIME_MODE:
            return probe_sampler.RealTimeSampling(self, self.interval)
        elif self.mode == VIRTUAL_MODE:
            return probe_sampler.VirtualTimeSampling(
                self, self.interval, self.clock)
        elif self.mode == NOTIFIER_MODE:
            return probe_sampler.NotificationSampling(
                self, self.notifier_type, self.notifier_obj)
        elif self.mode == TIMESTAMP_MODE:
            return probe_sampler.TimestampSampling(
                self, self.clock, self.timestamp_file_name)
        else:
            assert 0

    def start(self):
        if self.sampling:
            self.sampling.stop()
        self.sampling = self.create_sampling()
        self.sampling.start()

        self.stop_hap_id = SIM_hap_add_callback(
            "Core_Simulation_Stopped", self.simulation_stopped, None)

    def stop(self):
        if self.sampling:
            self.sampling.stop()
            self.sampling = None

        if self.stop_hap_id != None:
            SIM_hap_delete_callback_id("Core_Simulation_Stopped",
                                       self.stop_hap_id)
            self.stop_hap_id = None

        self.presentation.sampler_stopped()

    def reset_session(self):
        self.sprobes.reset_session()

    def force_sample(self):
        if self.sampling:
            self.sampling.sample_event()

    def simulation_stopped(self, data, obj, exc, error):
        self.presentation.simulation_stopped()
        if self.sampling:
            self.sampling.simulation_stopped()

    def terminate(self):
        self.stop()
        self.sprobes.terminate()
        self.presentation.terminate()
        probes.unregister_probe_delete_cb(self.probe_proxy_deleted)

    def probe_proxy_deleted(self, p):
        SIM_log_info(4, self.obj, 0,
                     f"Deletion of probe {p.cli_id} detected")
        deleted_sps = []
        for sp in self.sampled_probes():
            if sp.probe_proxy == p:
                deleted_sps.append(sp)
        for sp in deleted_sps:
            SIM_log_info(1, self.obj, 0,
                         f"Used probe '{p.cli_id}' deleted,"
                         " removing it from sampler")
            self.sprobes.remove(sp)
        self.probes_updated()

    # Called by the current sampler class after a measurement sample
    def process_sample(self):
        if self.sprobes.none_sampled():
            SIM_log_info(1, self.obj, 0, "Not sampling any probes!")
            return

        self.measure_start_sampling()
        self.presentation.process_sample()
        self.measure_stop_sampling()

    def get_raw_data(self, sprobe_list, delta_sprobe_list):
        'Retrieve the raw values of the probes in the sprobe list'
        self.measure_start_collecting()

        # Possibly start caching of probes which are read multiple times
        self.probe_sampler_cache_iface.enable()

        for dsp in delta_sprobe_list:
            dsp.prepare_sample()

        data = [0] * len(sprobe_list)
        for idx, sp in enumerate(sprobe_list):  # Data are in the order set in probe list
            data[idx] = sp.sample_value()

        # Disable caching of probes.
        self.probe_sampler_cache_iface.disable()

        self.measure_stop_collecting()

        return data


    class Sampling(ABC):
        __slots__ = ("probe_sampler")

        def __init__(self, probe_sampler):
            self.probe_sampler = probe_sampler  # Probe-sampler owning this

        def sample_event(self):
            return self.probe_sampler.process_sample()  # Call the probe-sampler

        def simulation_stopped(self):
            pass

        @abstractmethod
        def start(self):
            pass

        @abstractmethod
        def stop(self):
            pass

        def probes_updated(self):
            pass


    class PeriodicSampling(Sampling):
        __slots__ = ("interval")

        def __init__(self, probe_sampler, interval):
            super().__init__(probe_sampler)
            self.interval = interval

        def start(self):
            self.post()

        @abstractmethod
        def post(self):
            pass


    class RealTimeSampling(PeriodicSampling):
        __slots__ = ("rt_event_id")

        def __init__(self, probe_sampler, interval):
            super().__init__(probe_sampler, interval)
            self.rt_event_id = None

        def post(self):
            self.rt_event_id = SIM_realtime_event(
                int(self.interval * 1000),  # time in ms
                self.event, None, False,
                f"realtime event for {self.probe_sampler.obj.name}")

        def handle_real_time_event(self):
            self.sample_event()

        def event(self, callback_data):
            if not SIM_simics_is_running():
                self.post()
                return   # Ignore samples when Simics is not running

            self.handle_real_time_event()
            self.post()             # Re-post

        def stop(self):
            if self.rt_event_id != None:
                SIM_cancel_realtime_event(self.rt_event_id)
                self.rt_event_id = None


    # This is a specialization of the RealTimeSampler which stops
    # execution when we have reached CPU0 again, making it sure that
    # we have run through all CPUs round-robin.
    class SyncedRealTimeSampling(RealTimeSampling):
        __slots__ = ("eventclass", "clock", "cell", "sync_posted",
                     "timestamp_file")

        def __init__(self, probe_sampler, interval, clock,
                     timestamp_file_name):
            super().__init__(probe_sampler, interval)
            self.sync_posted = False
            self.timestamp_file = None
            self.clock = clock
            self.cell = self.clock.cell
            if timestamp_file_name:
                self.timestamp_file = open(timestamp_file_name, "w")
                self.timestamp_file.write(
                    f"# Created by {self.probe_sampler.obj.name} with"
                    f" time-stamps for {self.clock.name}\n")

        def write_timestamp(self):
            if self.timestamp_file:
                cycle = SIM_cycle_count(self.clock)
                self.timestamp_file.write(f'{cycle}\n')

        # Post a sync event at the start of the quantum
        def post_sync(self, cycles):
            SIM_event_post_cycle(self.clock, self.eventclass, self.probe_sampler.obj,
                                 cycles, self)
            self.sync_posted = True

        @classmethod
        def class_sync_event(cls, obj, user_data):
            sampler = user_data
            # Execution threads may not run
            SIM_run_alone(sampler.alone_event, None)

        # Callback when all execution threads have stopped
        def alone_event(self, callback_data):
            self.sample_event()
            self.write_timestamp()
            self.sync_posted = False

        # Overrides superclass method.
        # We get here when we have a new real-time event that should be serviced
        # Instead of servicing this directly, we try execute to to the next
        # quantum start, forcing all processors to have executed at least once
        # in a the round-robin schedule.
        # The reasons for this:
        # 1. We want to record the time-stamp of the same CPU in the time-stamp file
        # 2. In very rare circumstances, when the simulation is dead slow, we want
        #    at least all processors to have executed one time-quantum before the
        #    sample is taken. Otherwise some global probes, such as sim.load_percent
        #    will report strange numbers.
        #
        # We only sync on a single-cell here, thus we don't have any guarantees on
        # (2) above when doing multi-machine-threading, subsystem-threading or
        # multi-core-threading. Increase the real-time sampling rate is probably
        # the best solution if global probes starts to report strange values.
        def handle_real_time_event(self):
            if len(self.cell.clocks) <= 1:
                self.sample_event() # just one cpu here, service it directly
                self.write_timestamp()
                return

            if self.sync_posted:
                SIM_log_info(
                    1, self.probe_sampler.obj, 0,
                    "Real-time event discarded, last event not yet handled"
                    " (slow simulation)")
                return

            # If we are currently running on our clock, make sure we first
            # finish our time-quantum and get back to the beginning of the
            # next time-quantum. Otherwise just post on the next cycle
            # which will be on the start on the time-quantum.
            cycles = (VT_cycles_to_quantum_end(self.clock)
                      if self.cell.scheduled_object == self.clock else 0)
            self.post_sync(cycles)

        def simulation_stopped(self):
            super().simulation_stopped()
            if self.timestamp_file:
                self.timestamp_file.flush()

        def stop(self):
            super().stop()
            if self.timestamp_file:
                self.timestamp_file.close()
                self.timestamp_file = None
            SIM_event_cancel_time(self.clock, self.eventclass,
                                  self.probe_sampler.obj,
                                  None, None)


    class VirtualTimeSampling(PeriodicSampling):
        __slots__ = ("eventclass",  # Set by probe sampler when registering the event
                     "clock")
        # Generic event callback for the class, dispatches to the object
        # specific sampler event callback.

        @classmethod
        def class_event(cls, obj, user_data):
            sampler = user_data
            sampler.event()  # event() below

        def __init__(self, probe_sampler, interval, clock):
            super().__init__(probe_sampler, interval)
            self.clock = clock

        def post(self):
            SIM_event_post_time(self.clock, self.eventclass, self.probe_sampler.obj,
                                self.interval, self)

        # Event-callback
        def event(self):
            # Execution threads may not run
            SIM_run_alone(self.alone_event, None)

        # Callback when all execution threads have stopped
        def alone_event(self, callback_data):
            self.sample_event()
            self.post()             # Re-post

        def stop(self):
            SIM_event_cancel_time(self.clock, self.eventclass,
                                  self.probe_sampler.obj,
                                  None, None)


    class NotificationSampling(Sampling):
        __slots__ = ("notifier_type", "notifier_obj",
                     "handle", "ctxt_checker")

        def __init__(self, probe_sampler, notifier_type, notifier_obj):
            super().__init__(probe_sampler)
            self.notifier_type = notifier_type
            self.notifier_obj = notifier_obj
            self.handle = None
            self.ctxt_checker = self.ContextChecker(probe_sampler)

        def notified(self, obj, src, data):
            # We let the sampler samples the probes in the current thread
            # (no use of SIM_run_alone). Sampling is thus performed without
            # any delay w.r.t. the notifier, and several notifiers can
            # trigger in a row without having probe samples overlapping
            # each other. Before sampling we nevertheless check there are
            # no compatibility issues between this notification's context and
            # the contexts the sampled probes run in.
            self.ctxt_checker.check()
            self.sample_event()

        def start(self):
            self.ctxt_checker.check_needed()
            assert self.handle == None
            self.handle = SIM_add_notifier(
                self.notifier_obj, SIM_notifier_type(
                    self.notifier_type), self.probe_sampler.obj,
                self.notified, None)

        def stop(self):
            if self.handle:
                SIM_delete_notifier(self.notifier_obj, self.handle)
                self.notifier_type = None
                self.notifier_obj = None
                self.handle = None

        def probes_updated(self):
            self.ctxt_checker.check_needed()

        class ContextChecker:
            __slots__ = ("sampler", "needed")

            def __init__(self, sampler):
                self.sampler = sampler
                self.needed = False

            class NotifierBasedSamplingContextException(SimExc_General):
                pass

            def check_needed(self):
                self.needed = True

            def check(self):
                if not self.needed:
                    return
                self.needed = False

                if not VT_outside_execution_context_violation():
                    return  # We can access any contexts from the global context so we
                            # can safely read any probes

                def find_probe_cells():
                    probe_cells = set()
                    for sp in self.sampler.sampled_probes():
                        owner_obj = sp.probe_proxy.prop.owner_obj
                        c = VT_object_cell(owner_obj) if not probes.is_singleton(owner_obj) else None
                        probe_cells.add(c)
                    return probe_cells

                probe_cells = find_probe_cells()
                if len(probe_cells) == 0:  # Means we aren't actually sampling any probes
                    return

                current_cell = VT_get_current_cell()
                if probe_cells == {current_cell}:
                    return  # There are no probes running outside of the current cell so
                            # we can safely read them all

                other_ctxts = []
                for c in probe_cells:
                    if c == current_cell:
                        continue
                    if c is None:
                        other_ctxts.append("global")
                    else:
                        other_ctxts.append(c.name)
                msg = (f"The notifier-based sampler {self.sampler.obj.name},"
                        f" which is notified from within the cell context {current_cell.name},"
                        " cannot sample probes running in the other context(s):"
                        f" {', '.join(other_ctxts)}")
                raise self.NotifierBasedSamplingContextException(msg)


    class TimestampSampling(Sampling):
        __slots__ = ("eventclass",  # Set by probe sampler in event registration
                     "timestamps", "clock")

        @classmethod
        def class_event(cls, obj, user_data):
            sampler = user_data
            sampler.event()  # event() below

        def __init__(self, probe_sampler, clock, timestamp_file_name):
            super().__init__(probe_sampler)
            self.clock = clock
            with open(timestamp_file_name, "r") as f:
                lines = f.readlines()

            vals = [int(l) for l in lines if l[0] != "#"] # Remove any comment
            self.timestamps = collections.deque(vals)

        def start(self):
            self.post()

        def post(self):
            cycle = SIM_cycle_count(self.clock)
            if len(self.timestamps):
                next = self.timestamps.popleft()
                cycles = next - cycle
                SIM_event_post_cycle(self.clock, self.eventclass,
                                     self.probe_sampler.obj,
                                     cycles, self)
            else:
                SIM_log_info(1, self.probe_sampler.obj, 0,
                             "No more recorded time-stamps left")

        # Event-callback
        def event(self):
            # Execution threads may not run
            SIM_run_alone(self.alone_event, None)

        # Callback when all execution threads have stopped
        def alone_event(self, callback_data):
            self.sample_event()
            self.post()             # Re-post

        def stop(self):
            SIM_event_cancel_time(self.clock, self.eventclass,
                                  self.probe_sampler.obj,
                                  None, None)
