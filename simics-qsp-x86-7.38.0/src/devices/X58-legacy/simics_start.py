# © 2010 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from update_checkpoint import (rename_attr,
                               SIM_register_class_update,
                               SIM_register_generic_update)

def rename_legacy_classes(objects):
    changed = []
    for o in objects.values():
        if o.classname.startswith('x58_'):
            cls = o.classname.split('.')
            cls[0] = cls[0].replace('_', '-') + '-legacy'
            o.classname = ".".join(cls)
            changed.append(o)
    return ([], changed, [])


SIM_register_generic_update(6118, rename_legacy_classes)
