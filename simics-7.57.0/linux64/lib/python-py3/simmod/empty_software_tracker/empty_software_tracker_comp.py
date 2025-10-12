# © 2016 Intel Corporation

import pyobj
import simics
from simmod.os_awareness import framework

class empty_software_tracker_comp(framework.tracker_composition):
    """Skeleton for creating a composition"""
    _class_desc = 'tracker composition skeleton'
    parameter_type = "empty_software_tracker"

    def add_objects(self):
        tracker = simics.SIM_create_object(
            'empty_software_tracker', f'{self.obj.name}.tracker_obj',
            [['parent', self.tracker_domain.val]])
        simics.SIM_create_object(
            'empty_software_mapper', f'{self.obj.name}.mapper_obj',
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
             (("Tracking", self.get_tracker().cpus),)))
        return tracker_status

    def get_tracker(self):
        return self.obj.tracker_obj

    def get_mapper(self):
        return self.obj.mapper_obj

    class osa_parameters(pyobj.Interface):
        def get_parameters(self, include_children):
            return [True, [self._top.parameter_type, {}]]

        def set_parameters(self, parameters):
            return [True, None]

        def is_kind_supported(self, kind):
            return kind == self._top.parameter_type
