# INTEL CONFIDENTIAL

# -*- python -*-

# © 2019 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# This file implements tcf_target_identification interface that provides
# CPUID and PCI register values that can be used to identify X86 targets.

import json
import simics

from simmod.tcf_agent import system_id

def get_service_version(tcf):
    return json.dumps({"Major": 1,"Minor": 0, "Patch": 0})

def get_targets(tcf):
    return json.dumps(system_id.list_system_id())

def register():
    target_identification_iface_type = simics.SIM_get_python_interface_type(
        'tcf_target_identification')
    target_identification_iface = target_identification_iface_type(
        get_service_version=get_service_version, get_targets=get_targets)
    simics.SIM_register_interface(
        'tcf-agent',
        'tcf_target_identification', target_identification_iface)
