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


# s-dmi-cache.py

# Test to check that inquiry accesses to Configuration Space Data register
# (io_reg.config_data register in x58_dmi device) doesn't cause real accesses.

from dmi_common import *

def do_test():
    reg_config_data = dev_util.Register_LE(tb.pci_bus.bridge.bank.io_regs,
                                            io_reg_offsets.config_data)
    reg_config_address = dev_util.Register_LE(tb.pci_bus.bridge.bank.io_regs,
                                              io_reg_offsets.config_address)

    new_value = 0xDEADBEEF

    for (addr, val) in [[0x81828384, 0x12345678],
                           [0x84858687, 0x9abcdf21]]:
        reg_config_address.write(addr)
        reg_config_data.write(val)

        # Read data from memory (SIM_get_mem_op_inquiry() is False)
        reg_config_address.write(addr)
        data_from_memory = reg_config_data.read()
        stest.expect_equal(data_from_memory, val,
                           "Invalid data read from config_data" )

        # Replace data in memory. NB: config address register ignores
        # two lower bits so we mask them also for pci_addr computation.
        pci_addr = conf_addr_to_pci_addr(addr & ~0x3)
        tb.vtd_hw_drv.mem_space_drv.write_mem(pci_addr,
                                              int_to_bytes(new_value, 4) )
        bytes_form_mem = tb.vtd_hw_drv.mem_space_drv.read_mem(pci_addr, 4)
        bad_data_form_mem = bytes_to_int(bytes_form_mem)

        stest.expect_equal(bad_data_form_mem, new_value,
                           "Invalid \"bad\" value read from memory" )

        # Read cached value from config_data reg
        # (SIM_get_mem_op_inquiry() is True)
        data_from_cache = run_command(
            "get-device-reg register = bridge.io_regs.config_data")
        stest.expect_equal(data_from_cache, val,
                           "Invalid data read from config_data cache" )

        # Read data from memory (SIM_get_mem_op_inquiry() is False)
        reg_config_address.write(addr)
        data_from_memory = reg_config_data.read()
        stest.expect_equal(data_from_memory, new_value,
                           "Invalid data read from config_data" )

do_test()
