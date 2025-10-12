# © 2015 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import pyobj
from simmod.os_awareness import framework
import cli
import simics

class cpumode_software_tracker_comp(framework.tracker_composition):
    """CPU mode tracker composition."""
    _class_desc = 'a CPU mode tracker'

    basename = "cpumode_software_tracker"

    class osa_parameters(pyobj.Interface):
        def get_parameters(self, include_children):
            return [True, [self._top.basename, {}]]

        def set_parameters(self, parameters):
            [tracker, params] = parameters
            if not self.is_kind_supported(tracker):
                return [False,
                        'cpumode tracker cannot handle parameters of type %s'
                        % (tracker,)]
            return [True, None]

        def is_kind_supported(self, kind):
            return kind == self._top.basename

    def add_objects(self):
        tracker = simics.SIM_create_object(
            'cpumode_software_tracker', f'{self.obj.name}.tracker_obj',
            [['parent', self.tracker_domain.val]])
        simics.SIM_create_object(
            'cpumode_software_mapper', f'{self.obj.name}.mapper_obj',
            [['parent', self.mapper_domain.val], ['tracker', tracker]])

    def get_tracker(self):
        return self.obj.tracker_obj

    def get_mapper(self):
        return self.obj.mapper_obj

    def _info(self):
        tracker_info = [("Objects",
                         [("Tracker", self.get_tracker()),
                          ("Mapper", self.get_mapper()),
                          ("Tracker parent", self.tracker_domain.val),
                          ("Mapper parent", self.mapper_domain.val),
                         ])]

        return tracker_info

    def _status(self):
        def __enabled_str(enabled):
            return "Enabled" if enabled else "Disabled"

        modes = {simics.Sim_CPU_Mode_User: "User",
                 simics.Sim_CPU_Mode_Supervisor: "Supervisor",
                 simics.Sim_CPU_Mode_Hypervisor: "Hypervisor"}
        name_and_mode = sorted([(cpu.name, modes.get(mode)) for (cpu, mode)
                         in self.get_tracker().cpus])
        tracker_status = [("Enable status",
                           [("Tracker",
                             __enabled_str(self.get_tracker().enabled)),
                            ("Mapper",
                             __enabled_str(self.get_mapper().enabled)),]),
                          ("Processor modes", name_and_mode)]
        return tracker_status
