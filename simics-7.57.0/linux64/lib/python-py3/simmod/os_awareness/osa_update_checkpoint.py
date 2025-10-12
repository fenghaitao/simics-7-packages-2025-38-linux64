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

def remove_component_attributes(obj):
    for attr in ('components',
                 'domain',
                 'instantiated',
                 'machine_icon',
                 'object_prefix',
                 'pending_cell_object_factories',
                 'system_info',
                 'top_component',
                 'top_level',
                 # Below attributes can exist in old checkpoints.
                 'dynamic_slots',
                 'static_slots',
                 'process_tracker'):
        uc.remove_attr(obj, attr)
