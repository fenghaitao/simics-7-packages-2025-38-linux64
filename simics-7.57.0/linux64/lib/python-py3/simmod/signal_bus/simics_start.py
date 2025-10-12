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


import update_checkpoint as uc

def update_targets(obj):
    targets = list(obj.targets)
    for i in range(len(targets)):
        t = targets[i]
        if (isinstance(t, list)
            and t[0].classname in {'io-apic', 'pc-shadow', 'i8254', 'i8259x2'}
            and t[1] == "RESET" and t[0].build_id >= 6045):
            targets[i] = t[0].port.RESET
    obj.targets = targets

uc.SIM_register_class_update(6045, "signal-bus", update_targets)
