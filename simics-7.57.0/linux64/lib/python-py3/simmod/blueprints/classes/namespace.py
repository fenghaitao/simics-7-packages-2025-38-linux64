# © 2024 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import simics, cli
import target_info

# Simics namespace-like object for storing blueprint meta-data.

class SubsystemNamespace:
    cls = simics.confclass(
        "subsystem-namespace",
        short_doc="sub-system meta-data extension class",
        doc=("Extension class that defines an attribute for storing meta-data"
             " about the sub-system."))

    cls.attr.blueprint("s", doc="The blueprint that created the hierarchy")
    cls.attr.icon("s", default="empty_machine.png",
                  doc="The system icon filename.")
    cls.attr.info("s", default="<machine information missing>",
                  doc="The system information.")

    def __init__(self):
        self.target_info_changed_hap = None

    @cls.finalize
    def finalize(self):
        target_info.ensure_target_info_changed_hap()
        self.target_info_changed_hap = simics.SIM_hap_get_number("Target_Info_Changed")

    @cls.objects_finalized
    def objects_finalized(self):
        simics.SIM_hap_occurred_always(self.target_info_changed_hap, None, 0, [])

class BlueprintNamespace(SubsystemNamespace):
    cls = simics.confclass(
        'blueprint-namespace', parent=SubsystemNamespace.cls,
        short_doc="root object of blueprint created object hierarchy",
        doc=("Class for objects created at the root of a hierarchy coming"
             " from a blueprint."))

def get_info(obj):
    return [(None, [
        ("Blueprint", obj.blueprint),
        ("Icon", obj.icon),
        ("Information", obj.info),
    ])]

def get_status(obj):
    return [(None, [])]

cli.new_info_command(BlueprintNamespace.cls.classname, get_info)
cli.new_status_command(BlueprintNamespace.cls.classname, get_status)
