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


from update_checkpoint import SIM_register_generic_update


def update_conf_space(objects):
    changed = []
    deleted = []
    for (n, obj) in list(objects.items()):
        if obj.build_id > 6184:
            continue
        if obj.classname == 'pcie-downstream-port-legacy':
            conf_space = objects.get(f'{n}.conf_space', None)
            if conf_space:
                conf_space.classname = 'memory-space'
                conf_space.default_target = None
                changed.append(conf_space)

            conf_translator = objects.pop(f'{n}.port.conf_translator', None)
            if conf_translator:
                deleted.append(conf_translator)
    return (deleted, changed, [])


SIM_register_generic_update(6185, update_conf_space)
