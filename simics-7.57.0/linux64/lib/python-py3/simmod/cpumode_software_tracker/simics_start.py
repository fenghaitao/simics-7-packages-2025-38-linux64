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

import update_checkpoint as uc
from simmod.os_awareness import osa_update_checkpoint as osa_uc

def from_comp_to_obj(tracker_comp):
    osa_uc.remove_component_attributes(tracker_comp)

uc.SIM_register_class_update(6173, "cpumode_software_tracker_comp",
                             from_comp_to_obj)
