# © 2023 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from cli import new_info_command, new_status_command
from simics import SIM_log_info, SIM_get_object, SIM_get_all_modules, CORE_get_extra_module_info
import os

cls_name = "sample_device_pkg_prio"

def info(obj):
    return [ (None,
              [ ("Loaded from", "%s" %  get_pkg_name())])]

def status(obj):
    return [ (None,
              [ ("Integer Attribute", "%d" % obj.attr.int_attr )])]

new_info_command(cls_name, info)
new_status_command(cls_name, status)


def get_pkg_name():
    pkg = 'UNKNOWN??'
    module = None
    #Get module that has this class
    for mod in SIM_get_all_modules():
        for cls in mod[7]:
            if cls == cls_name:
                module = mod
    if module:
        #Check if module is from project
        buildID_ns = CORE_get_extra_module_info(module[0])[0]
        if buildID_ns == '__simics_project__':
            return 'current Simics project'
        #If not, find the package that holds the shared lib
        path = os.path.abspath(module[1])
        #Below should not fail
        try:
            pkg = ( m[1] for m in SIM_get_object('sim').package_info if path.startswith(os.path.abspath(m[9])) ).__next__()
        except:
            pass
    return pkg


SIM_log_info(1, SIM_get_object('sim'), 0, 'Loading <sample_device_pkg_prio> from %s'%(get_pkg_name()))
