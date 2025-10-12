# © 2024 Intel Corporation
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
from stest import expect_equal, expect_log

uut = SIM_create_object('simics-uefi','uut')
regs = bank_regs(uut.bank.pcie_config)

# Test correct bit mask when no images are available
expect_equal(regs.caps.added_tbls.read(),
             0,
             'Reported set of tables should be empty')

# Test correct bit mask when exactly one image is available
img = SIM_create_object('image',f'uut.img', size = 42)
for i in range(32):
    if i > 0:
        uut.additional_acpi_tables[i-1] = None
    uut.additional_acpi_tables[i] = img
    expect_equal(regs.caps.added_tbls.read(),
                 1 << (31 - i),
                 f'Bit {31 - i} should be set')

# Test a "random" bit pattern
img_cfgs = [ ('img0', 42),
             ('img3', 99),
             ('img9', 4711),
             ('img12', 4096),
             ('img30', 128),
             ('img31', 256),]

images = [None] * 32
expected_bit_mask = 0

for n, s in img_cfgs:
    images[int(n[3:])] = SIM_create_object('image',f'uut.{n}', size = s)
    expected_bit_mask |= (1 << (31 - int(n[3:])))

uut.additional_acpi_tables = images
expect_equal(regs.caps.added_tbls.read(),
             expected_bit_mask,
             f'Bit mask should match connected images')

# Test incorrect selection triggers log message
expect_log(regs.caps.added_tbls.write, args = [0],
           log_type = 'info',
           regex = 'No table selected. Will not do anything.',
           msg = 'Should inform of invalid selection (none selected)',
           with_log_level = 2)

expect_log(regs.caps.added_tbls.write, args = [0xa],
           log_type = 'info',
           regex = 'More than one table selected. Will not do anything.',
           msg = 'Should inform of invalid selection (more than one selected)',
           with_log_level = 2)

# Ensure incorrect selection return 0 on size and data
expect_equal(regs.caps.tbl_size.read(),
             0,
             'Tbl size should be 0, with bad image selection')
expect_equal(regs.caps.tbl_data.read(),
             0,
             'Tbl data should be 0, with bad image selection')

uut.additional_acpi_tables = [None] * 32 # no images available
regs.caps.added_tbls.write(0x10) # correct selection

# Ensure return 0 on size and data in absence of image
expect_equal(regs.caps.tbl_size.read(),
             0,
             'Tbl size should be 0, with bad image selection')
expect_equal(regs.caps.tbl_data.read(),
             0,
             'Tbl data should be 0, with bad image selection')

random.seed(42)  # seed with a fixed value to keep repeatable

test_images = [12, 30]

# first, fill the images
for test_image in test_images:
    for i in range(images[test_image].size):
        images[test_image].iface.image.set(i, random.randbytes(1))

uut.additional_acpi_tables = images # re-attach our "random" image set

for test_image in test_images:
    regs.caps.added_tbls.write(1 << (31 - test_image)) # select image
    expect_equal(regs.caps.tbl_size.read(),
                 images[test_image].size,
                 f'Tbl size should be {images[test_image].size} on image {test_image}')

    for i in range(images[test_image].size):
        expect_equal(regs.caps.tbl_data.read(),
                     ord(images[test_image].iface.image.get(i,1)),
                     f'Tbl data mismatch between stream and image {test_image} at offset {i}')

    # continued reading should wrap around (we will stop half-way through)
    for i in range(int(images[test_image].size/2)):
        expect_equal(regs.caps.tbl_data.read(),
                 ord(images[test_image].iface.image.get(i,1)),
                 f'Tbl data mismatch between stream and image {test_image} at offset {i}')

    regs.caps.added_tbls.write(1 << (31 - test_image)) # select image again to reset stream
    # read should start from beginning again
    for i in range(images[test_image].size):
        expect_equal(regs.caps.tbl_data.read(),
                 ord(images[test_image].iface.image.get(i,1)),
                 f'Tbl data mismatch between stream and image {test_image} at offset {i}')
