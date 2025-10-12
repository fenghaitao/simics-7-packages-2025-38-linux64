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

from . import sampler
from . import presentation
from . import common
from . import sprobes

class probe_streamer(sampler.probe_sampler):
    __slots__ = ("csv_output_file_name", "metadata_enabled",
                 "timestamping", "timestamp_probe")

    cls = confclass("probe_streamer", parent=sampler.probe_sampler.cls,
                    pseudo=True,
                    short_doc="probe streamer",
                    doc="Probe sampler and data collector that streams collected data out.")

    cls.attr.csv_output_file_name(
        "s",
        default=None,
        doc="CSV output file name.")
    cls.attr.metadata_enabled(
        "b",
        default=True,
        doc="Enable metadata.")
    cls.attr.timestamping(
        "b",
        default=True,
        doc="Enable timestamping.")
    cls.attr.timestamp_probe(
        "n|s",
        default=None,
        doc="Probe used for timestamping.")

    @cls.attr.timestamp_probe.setter
    def set_timestamp_probe(self, timestamp_probe):
        if timestamp_probe:
            # Check this is a valid probe
            (_, error_msg) = self.get_timestamp_probe_proxy(timestamp_probe)
            if error_msg:
                SIM_attribute_error(error_msg)
                return Sim_Set_Illegal_Value
        self.timestamp_probe = timestamp_probe
        return Sim_Set_Ok

    @cls.init
    def initialize(self):
        super().initialize()
        self.sprobes = StreamedProbes()

    @cls.finalize
    def finalize_instance(self):
        self.presentation = presentation.StreamPresentation(
            self, self.csv_output_file_name, self.metadata_enabled)

        if self.timestamping:
            if self.timestamp_probe:
                t_probe = self.timestamp_probe
            else:
                t_probe = self.get_default_timestamp_probe()
            if t_probe:
                (t_proxy, error_msg) = self.get_timestamp_probe_proxy(t_probe)
                if error_msg:
                    SIM_log_error(self.obj, 0, error_msg)
                else:
                    self.sprobes.add_timestamp(t_proxy)
                    self.probes_updated()

        super().finalize_instance()

    def get_default_timestamp_probe(self):
        if self.mode == sampler.REALTIME_MODE:
            timestamp_probe = "sim.time.wallclock"
        elif self.mode in [
                sampler.REALTIME_SYNC_MODE,
                sampler.TIMESTAMP_MODE,
                sampler.VIRTUAL_MODE]:
            timestamp_probe = f"{self.clock.name}:cpu.time.virtual"
        elif self.mode == sampler.NOTIFIER_MODE:
            clock = SIM_object_clock(self.notifier_obj)
            if clock:
                timestamp_probe = f"{clock.name}:cpu.time.virtual"
            else:
                SIM_log_info(2, self.obj, 0,
                            f"{self.notifier_obj.name} has no clock, hence no timestamping enabled")
                timestamp_probe = None
        else:
            assert 0
        return timestamp_probe

    def get_timestamp_probe_proxy(self, timestamp_probe):
        if ":" in timestamp_probe: # Explicit probe specified (obj:probe-kind)
            matches = common.get_matching_probes(timestamp_probe)
        else:                   # Only probe-kind specified
            matches = common.get_matching_probe_kinds(timestamp_probe)
        matches_len = len(matches)
        if matches_len == 0:
            return (None, f"Timestamp probe {timestamp_probe} not found")
        if matches_len > 1:
            return (None, f"Several timestamp probes {timestamp_probe}"
                    " found, use only one")
        return (matches[0], None)


class StreamedProbes(sprobes.SampledProbes):
    '''Extends SampledProbes to include the management of a timestamp probe'''

    def __init__(self):
        super().__init__()
        self.timestamp_proxy = None

    def generate_unique_id(self, probe_proxy, mode):
        unique_id = super().generate_unique_id(probe_proxy, mode)
        if probe_proxy == self.timestamp_proxy:
            unique_id += "-ts"  # ensure the timestamp id is unique
        return unique_id

    def add_timestamp(self, t_proxy):
        self.timestamp_proxy = t_proxy
        t_sp = self.create(t_proxy, mode=sprobes.CURRENT_MODE, hidden=False,
                           no_sampling=False)
        self.add(t_sp)
        # The timestamp probe is always in first position
        self._sprobes.move_to_end(t_sp.unique_id, False)
