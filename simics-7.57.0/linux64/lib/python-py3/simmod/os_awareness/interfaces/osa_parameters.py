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

import simics
from simmod.os_awareness import framework

def get_parameters(osa_obj, include_children):
    tracker = osa_obj.current_tracker
    if not tracker:
        return [False, 'No tracker to get parameters from']
    if not hasattr(tracker.iface, 'osa_parameters'):
        return [False, 'Current tracker does not support parameters']
    return tracker.iface.osa_parameters.get_parameters(
        include_children)

def tracker_class_ok(tracker_class, params_tracker_name):
    # TODO: Better mapping between tracker name and component
    return tracker_class == params_tracker_name + '_comp'

def tracker_class_exists(tracker_class):
    try:
        simics.SIM_get_class_interface(tracker_class, 'osa_tracker_component')
    except:
        return False
    return True

def set_parameters(osa_obj, parameters):
    [tracker_name, params] = parameters
    tracker = osa_obj.current_tracker
    if tracker:
        if not hasattr(tracker.iface, 'osa_parameters'):
            return [False, 'Current tracker does not support parameters']
        if tracker_class_ok(tracker.classname, tracker_name):
            return tracker.iface.osa_parameters.set_parameters(parameters)
        else:
            return [False,
                    'Parameters not compatible with tracker. Expected'
                    f' parameters for a {tracker.classname} tracker, got'
                    f' parameters for a {tracker_name} tracker.']
    else:
        suffix = 'comp'
        tracker_class = f'{tracker_name}_{suffix}'
        if not tracker_class_exists(tracker_class):
            return [False, f'No class {tracker_class} found']
        try:
            framework.insert_tracker(
                osa_obj, osa_obj.object_data.child_base_name(), tracker_class,
                parameters)
        except framework.FrameworkException as e:
            return [False, str(e)]
        return [True, None]

def is_kind_supported(osa_obj, kind):
    tracker_comp_name = f'{kind}_comp'
    try:
        tracker_class = simics.SIM_get_class(tracker_comp_name)
    except simics.SimExc_General:
        return False
    return hasattr(tracker_class.iface, 'osa_parameters')

def register():
    simics.SIM_register_interface(
        'os_awareness', 'osa_parameters',
        simics.osa_parameters_interface_t(
            get_parameters=get_parameters,
            set_parameters=set_parameters,
            is_kind_supported=is_kind_supported))
