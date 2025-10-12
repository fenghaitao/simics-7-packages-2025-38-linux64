# © 2016 Intel Corporation
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
import simics
from simmod.os_awareness import framework

class sample_linux_tracker_comp(framework.tracker_composition):
    """Example for creating a linux tracker composition"""
    _class_desc = 'linux tracker composition example'

    parameters_type = "sample_linux_tracker"

    def add_objects(self):
        tracker = simics.SIM_create_object(
            'sample_linux_tracker', f'{self.obj.name}.tracker_obj',
            [['parent', self.tracker_domain.val]])
        simics.SIM_create_object(
            'sample_linux_mapper', f'{self.obj.name}.mapper_obj',
            [['parent', self.mapper_domain.val], ['tracker', tracker]])


    def _info(self):
        tracker_info = (("Objects",
                         (("Tracker", self.get_tracker()),
                          ("Mapper", self.get_mapper()),
                          ("Tracker parent", self.tracker_domain.val),
                          ("Mapper parent", self.mapper_domain.val),
                         )),)

        return tracker_info

    def _status(self):
        enabled_str = {True: "Enabled", False: "Disabled"}
        tracker_status = (
            ("Enable status",
             (("Tracker", enabled_str[self.get_tracker().enabled]),
              ("Mapper", enabled_str[self.get_mapper().enabled]))),
            ("Processors",
             (("Tracking", self.get_tracker().cpu),)))
        return tracker_status

    def get_tracker(self):
        return self.obj.tracker_obj

    def get_mapper(self):
        return self.obj.mapper_obj

    class osa_parameters(pyobj.Interface):
        def get_parameters(self, include_children):
            return [True, [self._top.parameters_type,
                           self._up.obj.tracker_obj.parameters]]

        def set_parameters(self, parameters):
            [tracker, params] = parameters
            if not self.is_kind_supported(tracker):
                return [
                    False,
                    'Sample Linux tracker cannot handle parameters of type %s'
                    % (tracker,)]
            try:
                self._up.obj.tracker_obj.parameters = params
            except (simics.SimExc_IllegalValue, simics.SimExc_Type) as ex:
                return [False,
                        'Error setting parameters, rejected by %s: %s'
                        % (tracker, str(ex))]

            return [True, None]

        def is_kind_supported(self, kind):
            return kind == self._top.parameters_type
