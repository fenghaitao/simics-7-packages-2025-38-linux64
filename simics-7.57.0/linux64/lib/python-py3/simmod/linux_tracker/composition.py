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
import simics
from simmod.os_awareness import framework
from . import commands
from . import linux_analyzer_cmds

class linux_tracker_comp(framework.tracker_composition):
    """A Linux Tracker top object that can be inserted into a domain."""
    _class_desc = 'a Linux Tracker'
    class osa_parameters(pyobj.Interface):
        def get_parameters(self, include_children):
            return [True, ['linux_tracker', self._up.obj.tracker_obj.params]]

        def set_parameters(self, parameters):
            [tracker, params] = parameters
            if not self.is_kind_supported(tracker):
                return [False,
                        'Linux tracker cannot handle parameters of type %s'
                        % (tracker,)]
            try:
                self._up.obj.tracker_obj.params = params
            except simics.SimExc_IllegalValue:
                return [False,
                        'Error setting parameters, rejected by tracker %s'
                        % (tracker,)]

            return [True, None]

        def is_kind_supported(self, kind):
            return kind == 'linux_tracker'


    def _info(self):
        # Both tracker and mapper have no top level header (list has size one
        # and header field is set to None for that element.
        tracker_info = commands.get_lx_tracker_info(self.get_tracker())[0][1]
        mapper_info = commands.get_lx_mapper_info(self.get_mapper())[0][1]
        combined_info = [("Tracker", tracker_info),
                         ("Mapper", mapper_info)]
        return combined_info

    def _status(self):
        # Both tracker and mapper have no top level header (list has size one
        # and header field is set to None for that element.
        tracker_status = commands.get_lx_tracker_status(
            self.get_tracker())[0][1]
        mapper_status = commands.get_lx_mapper_status(self.get_mapper())[0][1]
        combined_status = [("Tracker", tracker_status),
                           ("Mapper", mapper_status)]
        return combined_status

    def get_tracker(self):
        return self.obj.tracker_obj

    def get_mapper(self):
        return self.obj.mapper_obj

    def add_objects(self):
        try:
            self.tracker_obj = simics.SIM_create_object(
                'linux_tracker', f'{self.obj.name}.tracker_obj',
                [['osa_admin', self.osa_admin.val],
                 ['parent', self.tracker_domain.val]])
            self.mapper_obj = simics.SIM_create_object(
                'linux_mapper', f'{self.obj.name}.mapper_obj',
                [['tracker_state_query', self.osa_admin.val],
                 ['tracker_state_notification', self.mapper_domain.val],
                 ['node_tree_admin', self.mapper_domain.val],
                 ['tracker', self.tracker_obj]])
        except simics.SimExc_General:
            return False
        return True

def register():
    linux_tracker_comp.register()
    linux_analyzer_cmds.register()
