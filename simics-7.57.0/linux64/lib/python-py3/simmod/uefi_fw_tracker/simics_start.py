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


import update_checkpoint as uc
import cli
from simmod.os_awareness import osa_update_checkpoint as osa_uc

cli.add_tech_preview('uefi-fw-tracker-active-modules')
cli.add_tech_preview('uefi-fw-tracker-risc-v')

def remove_unknown_maps_attributes(tracker_obj):
    if not hasattr(tracker_obj, "unknown_maps"):
        return
    known_maps = tracker_obj.maps
    known_smm_maps = tracker_obj.smm_maps
    unknown_maps = tracker_obj.unknown_maps
    smm_unknown_maps = tracker_obj.smm_unknown_maps

    tracker_obj.maps = known_maps + unknown_maps
    tracker_obj.smm_maps = known_smm_maps + smm_unknown_maps

    uc.remove_attr(tracker_obj, "unknown_maps")
    uc.remove_attr(tracker_obj, "smm_unknown_maps")

def include_entities_in_cpus_attribute(tracker_obj):
    # As part of adding an OS node cpus attribute changed from being a list of
    # cpus to being a list with [cpu, entity]. Do a best effort to set entity,
    # active nodes will not be handled for an old checkpoint anyway as mapper
    # does not have information about entity to node.
    old_cpus = tracker_obj.cpus
    if len(old_cpus) == 0:
        return
    if isinstance(old_cpus[0], list):
        # Already updated
        return

    new_cpus = []
    for (entity, cpu) in enumerate(old_cpus, 1):
        new_cpus.append([cpu, entity])
    tracker_obj.cpus = new_cpus

def remove_cpus_with_enter_hap(tracker_obj):
    if hasattr(tracker_obj, "smm_cpus_with_enter_hap"):
        uc.remove_attr(tracker_obj, "smm_cpus_with_enter_hap")

def set_uefi_and_os_nodes(mapper_obj):
    if hasattr(mapper_obj, "uefi_node"):
        # Already new format
        return

    # Set UEFI and OS nodes to same as root. The old view will remain and events
    # will be send out on uefi_node which is the same as the old root
    # node. Things will look and work in the same way as it prior to having
    # separate OS and UEFI nodes.
    mapper_obj.uefi_node = mapper_obj.root_node
    mapper_obj.os_node = mapper_obj.root_node


def from_comp_to_obj(tracker_comp):
    osa_uc.remove_component_attributes(tracker_comp)

uc.SIM_register_class_update(6005, "uefi_fw_tracker",
                             remove_unknown_maps_attributes)
uc.SIM_register_class_update(6126, "uefi_fw_tracker",
                             include_entities_in_cpus_attribute)
uc.SIM_register_class_update(6161, "uefi_fw_tracker",
                             remove_cpus_with_enter_hap)
uc.SIM_register_class_update(6126, "uefi_fw_mapper",
                             set_uefi_and_os_nodes)
uc.SIM_register_class_update(6173, "uefi_fw_tracker_comp", from_comp_to_obj)
