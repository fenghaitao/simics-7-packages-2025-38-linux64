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
import cli_impl

class uefi_fw_tracker_comp(framework.tracker_composition):
    """Composition of UEFI tracker and mapper"""
    _class_desc = 'UEFI tracker composition'

    parameters_type = "uefi_fw_tracker"

    def add_objects(self):
        tracker = simics.SIM_create_object(
            'uefi_fw_tracker', f'{self.obj.name}.tracker_obj',
            [['parent', self.tracker_domain.val]])
        simics.SIM_create_object(
            'uefi_fw_mapper', f'{self.obj.name}.mapper_obj',
            [['parent', self.mapper_domain.val], ['tracker', tracker]])

    def get_efi_phase(self):
        tracker = self.get_tracker()
        return tracker.efi_phase

    def get_map_file(self):
        tracker = self.get_tracker()
        map_file = "none"
        if tracker.params:
            map_file = tracker.params.get("map_file", "none")
        return map_file

    def _tracking_text(self):
        return {
            'exec_tracking': 'Execution Tracking',
            'notification_tracking': 'Notification Tracking',
            'map_tracking': 'Map Based Tracking',
            'pre_dxe_tracking': 'Pre-DXE Tracking',
            'dxe_tracking': 'DXE Tracking',
            'dxe_phase_tracking': 'DXE Phase Tracking',
            'dxe_module_tracking': 'DXE Module Tracking',
            'hand_off_tracking': 'Hand-off Tracking',
            'smm_tracking': 'SMM Tracking',
            'reset_tracking': 'Reset Tracking',
        }

    def _range_info(self, tracker, yes, no, enabled, pre_dxe):
        if enabled:
            prefix = 'pre_' if pre_dxe else ''
            return '%s (start: 0x%x, end: 0x%x)' % (
                yes,
                tracker.params[prefix + 'dxe_start'],
                tracker.params[prefix + 'dxe_start']
                + tracker.params[prefix + 'dxe_size'])
        return no

    def _info(self):
        tracker_info = []
        tracker = self.get_tracker()
        tracker_info.append(["Objects",
                             [["Tracker", tracker],
                              ["Mapper", self.get_mapper()],
                              ["Tracker parent", self.tracker_domain.val],
                              ["Mapper parent", self.mapper_domain.val]]])
        configured = 'Configured'
        disabled = 'Disabled'
        config = []

        config.append(
            [self._tracking_text()['exec_tracking'],
             "%s (scan-size: 0x%x)" % (
                 configured, tracker.params['exec_scan_size']) if
             tracker.params['exec_tracking'] else disabled])

        config.append([self._tracking_text()['notification_tracking'],
                       configured if tracker.params['notification_tracking']
                       else disabled])

        map_file = self.get_map_file()
        config.append([self._tracking_text()['map_tracking'],
                       configured if map_file else disabled])
        if map_file:
            config.append(["Map file", map_file])

        pre_dxe_status = self._range_info(
            tracker, configured, disabled, tracker.params['pre_dxe_tracking'],
            True)
        config.append(
            [self._tracking_text()['pre_dxe_tracking'], pre_dxe_status])

        dxe_status = self._range_info(
            tracker, configured, disabled, tracker.params['dxe_tracking'],
            False)
        config.append([self._tracking_text()['dxe_tracking'], dxe_status])

        config.append([self._tracking_text()['hand_off_tracking'], configured if
                       tracker.params['hand_off_tracking'] else disabled])

        config.append([self._tracking_text()['smm_tracking'], configured if
                       tracker.params['smm_tracking'] else disabled])

        config.append([self._tracking_text()['reset_tracking'], configured if
                       tracker.params['reset_tracking'] else disabled])

        tracker_info.append(["Configuration", config])
        return tracker_info

    def _tracking_status(self, text_key, configured, active):
        tracking_text = self._tracking_text()[text_key]
        if configured:
            status = 'Active' if active else 'Inactive'
        else:
            status = 'Disabled'
        return (tracking_text, status)

    def _tracking_status_all(self):
        tracker = self.get_tracker()
        return (
            self._tracking_status(
                'exec_tracking', tracker.params['exec_tracking'],
                tracker.exec_tracking_enabled),
            self._tracking_status(
                'notification_tracking',
                tracker.params['notification_tracking'],
                tracker.notification_tracking_enabled),
            self._tracking_status(
                'map_tracking', tracker.params['map_file'],
                tracker.map_tracking_enabled),
            self._tracking_status(
                'pre_dxe_tracking', tracker.params['pre_dxe_tracking'],
                tracker.mem_scan_tracking_enabled),
            self._tracking_status(
                'dxe_phase_tracking', tracker.params['dxe_tracking'],
                tracker.dxe_phase_tracking_enabled),
            self._tracking_status(
                'dxe_module_tracking', tracker.params['dxe_tracking'],
                tracker.dxe_module_tracking_enabled),
            self._tracking_status(
                'hand_off_tracking', tracker.params['hand_off_tracking'],
                tracker.hand_off_tracking_enabled),
            self._tracking_status(
                'smm_tracking', tracker.params['smm_tracking'],
                tracker.smm_tracking_enabled),
            self._tracking_status(
                'reset_tracking', tracker.params['reset_tracking'],
                tracker.reset_tracking_enabled))

    def _status(self):
        enabled_str = {True: "Enabled", False: "Disabled"}
        tracker_status = []


        tracker_status.append(
            ["Enable status",
             [["Tracker", enabled_str[self.get_tracker().enabled]],
              ["Mapper", enabled_str[self.get_mapper().enabled]]]])
        tracker_status.append(
            ["Processors", [["Tracking", self.get_tracker().cpus]]])
        tracker_status.append(
            ["State", [["Estimated phase", self.get_efi_phase()]]])
        tracker_status.append(
            ['Tracking status', self._tracking_status_all()])
        return tracker_status

    def get_tracker(self):
        return self.obj.tracker_obj

    def get_mapper(self):
        return self.obj.mapper_obj

    class osa_parameters(pyobj.Interface):
        def get_parameters(self, include_children):
            return [True, [self._top.parameters_type,
                           self._up.obj.tracker_obj.params]]

        def set_parameters(self, parameters):
            [tracker, params] = parameters
            if not self.is_kind_supported(tracker):
                return [False,
                        'UEFI tracker cannot handle parameters of type %s'
                        % (tracker,)]
            try:
                self._up.obj.tracker_obj.params = params
            except simics.SimExc_IllegalValue:
                return [False,
                        'Error setting parameters, rejected by tracker %s'
                        % (tracker,)]

            return [True, None]

        def is_kind_supported(self, kind):
            return kind == self._top.parameters_type
