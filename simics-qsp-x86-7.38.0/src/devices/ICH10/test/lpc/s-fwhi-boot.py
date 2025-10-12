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


number = 16

# Flash space
fla_space = pre_conf_object('fla_space', 'memory-space')
SIM_add_configuration([fla_space], None)
fla_space = conf.fla_space

# Flash RAM (128K)
image_size = 0x20000
ram_image2 = pre_conf_object('ram_image2', 'image')
ram_image2.size = image_size
SIM_add_configuration([ram_image2], None)
ram_image2 = conf.ram_image2

flash_leg = pre_conf_object('flash_leg', 'ram')
flash_leg.image = ram_image2
SIM_add_configuration([flash_leg], None)
flash_leg = conf.flash_leg

fla_space.map = [[0x000000, flash_leg, 0, 0, image_size]]

# Fake 64k device for boot
fake_fwh_b = pre_conf_object('fake_fwh_b', 'new-flash-memory')
fake_fwh_b.bus_width      = 16
fake_fwh_b.storage_ram    = flash_leg
fake_fwh_b.interleave     = 1
fake_fwh_b.max_chip_width = 16
fake_fwh_b.unit_size      = [0x20000]
fake_fwh_b.command_set    = 1
SIM_add_configuration([fake_fwh_b], None)
fake_fwh_b = conf.fake_fwh_b


def do_test():

    # initialize flash device data
    fla_data = []
    for i in range(number):
        fla_data.append(dev_util.value_to_tuple_le(i, 4))
    offset = 0
    for var in fla_data:
        fla_space.iface.memory_space.write(None, 0x00 + offset, var, 0)
        offset += 4

    # set register
    # fwhi write register('fwh_dev_en', 0x40)
    tb.write_conf_le(lpc_reg_addr+0xD8, 16, 0x40)

    # connect to legacy flash
    dev_list = tb.lpc.fwh_device
    dev_list[0] = [fake_fwh_b, flash_leg, ram_image2]

    # read from  legacy flash
    io_data = []
    offset = 0
    for i in range(number):
        read_val = tb.read_io(0xE0000+offset, 4)
        io_data.append(read_val)
        offset += 4

    expect(io_data, fla_data, "read data from legacy flash")



do_test()
