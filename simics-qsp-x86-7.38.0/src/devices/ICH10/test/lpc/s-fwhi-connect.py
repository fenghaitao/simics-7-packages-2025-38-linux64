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


from lpc_tb import *


test_times = 10
sel1_dev_num = 4
sel2_dev_num = 4


# Flash space
fla_space = pre_conf_object('fla_space', 'memory-space')
SIM_add_configuration([fla_space], None)
fla_space = conf.fla_space

# Flash RAM (1M)
image_size = 0x100000
ram_image0 = pre_conf_object('ram_image0', 'image')
ram_image0.size = image_size
SIM_add_configuration([ram_image0], None)
ram_image0 = conf.ram_image0

flash_mem = pre_conf_object('flash_mem', 'ram')
flash_mem.image = ram_image0
SIM_add_configuration([flash_mem], None)
flash_mem = conf.flash_mem

fla_space.map = [[0x00, flash_mem, 0, 0, image_size]]

# Device list with eight 1M-flash devices
fwh_list = []
for i in range(8):
    fake_fwh = pre_conf_object('fake_1M_%d' %i, 'new-flash-memory')
    fake_fwh.bus_width      = 16
    fake_fwh.storage_ram    = flash_mem
    fake_fwh.interleave     = 1
    fake_fwh.max_chip_width = 16
    fake_fwh.unit_size      = [0x10000 for j in range(16)]
    fake_fwh.command_set    = 1
    SIM_add_configuration([fake_fwh], None)
    fwh_list.append([SIM_get_object("fake_1M_%d" % i), flash_mem, ram_image0])
for i in range(4):
    fwh_list.append(None)


def do_test():
    # connect devices to fwhi
    tb.lpc.fwh_device = fwh_list

    # set register
    tb.write_conf_le(lpc_reg_addr+0xD0, 32, 0x00112233)
    tb.write_conf_le(lpc_reg_addr+0xD4, 16, 0x4567)
    tb.write_conf_le(lpc_reg_addr+0xD8, 16, 0xFF0F)

    # test
    for i in range(test_times):
        write_val = dev_util.value_to_tuple_le(i, 4)
        fla_space.iface.memory_space.write(None, i,           write_val, 0)
        fla_space.iface.memory_space.write(None, 0x80000 + i, write_val, 0)

        for j in range(sel2_dev_num):
            for addr_base in [0xFF000000, 0xFF400000, 0xFF080000, 0xFF480000]:
                read_val = tb.read_io(addr_base + 0x100000 * j + i, 4)
                expect(read_val, write_val, "FWH devices read in SEL2")

        for j in range(sel1_dev_num):
            for addr_base in [0xFF800000, 0xFFC00000, 0xFF880000, 0xFFC80000]:
                read_val = tb.read_io(addr_base + 0x100000 * j + i, 4)
                expect(read_val, write_val, "FWH devices read in SEL1")

do_test()
