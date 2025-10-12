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

import random

from simics import SIM_create_object
from dev_util import bank_regs
from stest import expect_equal

offset_to_write_at = 0x200
size_of_test_data = 0x100

uut = SIM_create_object('simics-uefi','uut')
regs = bank_regs(uut.bank.pcie_config)

expect_equal(regs.caps.legacy_bios_data.read(),
             0,
             'Should return 0 with unconnected image.')

regs.caps.legacy_bios_data.write(99)  # should not crash with unconnected image

img = SIM_create_object('image','img', size = 0x400)

uut.legacy_bios_rom_image = img
uut.legacy_bios_rom_offset = offset_to_write_at

expect_equal(all([b == 0 for b in img.iface.image.get(0, 0x400)]),
         True,
         'Image should be empty.')

expect_equal(regs.caps.legacy_bios_data.read(),
             42,
             'Should return 42 with connected image.')

random.seed(42)  # seed with a fixed value to keep repeatable

# generate "random" data to write
input_data = [int.from_bytes(random.randbytes(1), 'little') for i in range(size_of_test_data)]

for d in input_data:
    regs.caps.legacy_bios_data.write(d)

expect_equal([b for b in img.iface.image.get(offset_to_write_at, size_of_test_data)],
         input_data,
         'Input data should have arrived in image.')

expect_equal(all([b == 0 for b in img.iface.image.get(0, offset_to_write_at)]),
         True,
         'Area before target offset should be untouched.')


start_of_unused_area_at_end = offset_to_write_at + size_of_test_data
size_of_unused_area_at_end = 0x400 - start_of_unused_area_at_end
expect_equal(all([b == 0 for b in img.iface.image.get(start_of_unused_area_at_end, size_of_unused_area_at_end)]),
         True,
         'Area before target offset should be untouched.')
