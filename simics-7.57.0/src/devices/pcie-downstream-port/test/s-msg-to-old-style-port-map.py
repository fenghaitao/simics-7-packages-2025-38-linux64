# © 2025 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.
import simics
import stest
import cli

mem_size = 4096

uuts = []
for cls in ['pcie-downstream-port', 'pcie-downstream-port-legacy']:
    uut = SIM_create_object(cls, 'uut_' + cls.replace('-','_'))
    uut.msg_space.map = [[0x42000, uut.msg_space, 0, 0x1000, 4]]
    uuts.append(uut)

tgts = []
for i in range(2):
    tgts.append(SIM_create_object('pcie-downstream-port', f'tgt{i}'))
    mem = SIM_create_object('ram', f'tgt{i}.mem',
                            image = None, self_allocated_image_size = mem_size)
    tgts[-1].cfg_space.map = [[0x0, mem, 0, 0x4, 0x4],
                              [0x420000, mem, 0, 0, 0x1000]]

for uut in uuts:
    uut.msg_space.map += [[0x1000, tgts[0].port.ecam, 0, 0, 4]]
    uut.msg_space.map += [[0x2000, [tgts[1], 'ecam'], 0, 0, 4]]
    for tgt in tgts:
        tgt.mem.own_image.iface.image.clear_range(0, mem_size)
        v = tgt.mem.own_image.cli_cmds.get(address = 0x0, size = 4, _l = True)
        stest.expect_equal(v, 0)

    # below access will hit all msg_space members at offset 0x42000
    # the ecam mappings will shift that by 4 so that this will hit their cfg_space
    # at 0x420000. If the msg_space of uut _was_ also hit, it would go to offset
    # 0x1000 in itself, so would hit tgt0 (ecam) and hence tgt0 cfg_space at
    # offset 0. So if msg_space would broadcast to itself, we would find
    # an entry at offset 0x4 in tgt0 mem. But since msg_space should filter
    # itself from the broadcast, we must not see anything there.
    cli.global_cmds.write_device_offset(bank = f'{uut.name}.port.broadcast',
                                        offset = 0x42000,
                                        data = 0xdeadbeef,
                                        size = 4)
    for tgt in tgts:
        v = tgt.mem.own_image.cli_cmds.get(address = 0x0, size = 4, _l = True)
        stest.expect_equal(v, 0xdeadbeef)
    v = tgts[0].mem.own_image.cli_cmds.get(address = 0x4, size = 4, _l = True)
    stest.expect_equal(v, 0)
