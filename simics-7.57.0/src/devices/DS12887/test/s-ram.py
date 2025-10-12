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


# Test 114 bytes general purpose RAM of the DS12887.

from common import *
from stest import expect_equal

(ds, clk, pic_state) = create_config()
regs = ds_regs(ds)

# The common code does not map the DS12887 device, so let's do that here
phys_mem = pre_conf_object('phys_mem', 'memory-space')
phys_mem.map = [[0,      [ds, 'registers'], 0, 0, 0x1000],
                [0x1000, [ds, 'port_registers'], 0, 0, 2]]
SIM_add_configuration([phys_mem], None)

# Easy-to-use read/write methods.
def read_reg(reg_ofs):
    (val, ) = conf.phys_mem.iface.memory_space.read(None, reg_ofs, 1, 0)
    return val

def write_reg(reg_ofs, val):
    conf.phys_mem.iface.memory_space.write(None, reg_ofs, (val,), 0)

def read_indirect_reg(reg_ofs):
    conf.phys_mem.iface.memory_space.write(None, 0x1000, (reg_ofs,), 0)
    (val, ) = conf.phys_mem.iface.memory_space.read(None, 0x1001, 1, 0)
    return val

def write_indirect_reg(reg_ofs, val):
    conf.phys_mem.iface.memory_space.write(None, 0x1000, (reg_ofs,), 0)
    conf.phys_mem.iface.memory_space.write(None, 0x1001, (val,), 0)

def test_ram(read, write):
    print("Testing ram")
    n = 114
    data = [(167 * (i + 1)) & 0xff for i in range(n)]

    # Fill the ram with some arbitrary data
    for i in range(n):
        write(14 + i, data[i])

    # and verify that it's still there
    for i in range(n):
        expect_equal(read(14 + i), data[i])

test_ram(read_reg, write_reg)
test_ram(read_indirect_reg, write_indirect_reg)
test_ram(lambda ofs: read_indirect_reg(ofs | 128),
         lambda ofs,val: write_indirect_reg(ofs | 128, val))
