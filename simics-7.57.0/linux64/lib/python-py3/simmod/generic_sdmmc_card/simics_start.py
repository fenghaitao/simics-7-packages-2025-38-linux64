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


from update_checkpoint import *

def structure_mmc_attrs(obj):
    import struct
    data = ''.join(map(chr, obj.cmdq_task_list))
    size = 12
    obj.cmdq_task_list = [list(struct.unpack('<II??xx', data[start:start+size]))
            for start in range(0, 384, size)]

    data = ''.join(map(chr, obj.mem_part))
    size = 40
    unpacked = [
        struct.unpack('<QI20s?xxxI', data[start:start+size])
        for start in range(0, 280, size)]
    obj.mem_part = [[a, b, tuple(map(ord, c)), d, e]
                    for (a, b, c, d, e) in unpacked]
    return [obj]

install_class_configuration_update(
    6005, "mmc_card", structure_mmc_attrs)
