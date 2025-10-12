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


import update_checkpoint as uc
from simics import pre_conf_object
import cli
from simmod.os_awareness import osa_update_checkpoint as osa_uc

cli.add_tech_preview("track-shared-objects")

def booted_attribute_update(tracker_obj):
    if not isinstance(tracker_obj.booted, bool):
        # Already new type for attribute
        return
    if tracker_obj.booted:
        tracker_obj.booted = 1  # Linux_Booted
        return

    if tracker_obj.root_entity_added:
        # Legacy mode if tracker was enabled prior to taking checkpoint.
        tracker_obj.booted = 3  # Linux_Not_Booted_Legacy
    else:
        tracker_obj.booted = 0  # Linux_Not_Entered_Kernel

def from_comp_to_obj(tracker_comp):
    osa_uc.remove_component_attributes(tracker_comp)

# A new boolean entry last in task_cache was added to handle threads using
# task_struct.thread_node.
def task_cache_thread_node(tracker_obj):
    if not tracker_obj.task_cache:
        return
    # Old format had 16 entries, new has 17, return if it does not match old
    # format.
    if len(tracker_obj.task_cache[0]) != 16:
        return
    new_val = [e + [False] for e in tracker_obj.task_cache]
    tracker_obj.task_cache = new_val

uc.SIM_register_class_update(6022, "linux_tracker", booted_attribute_update)
uc.SIM_register_class_update(6173, "linux_tracker_comp", from_comp_to_obj)
uc.SIM_register_class_update(6365, "linux_tracker", task_cache_thread_node)
