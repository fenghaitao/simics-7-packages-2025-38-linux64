# © 2016 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import stest
import pyobj

image = simics.pre_conf_object('image', 'image')
image.size = 0x10000

flash = simics.pre_conf_object('flash','generic_spi_flash')
flash.mem_block = image
simics.SIM_add_configuration([flash, image], None)

old_sector_lock = conf.flash.sector_lock[:]
conf.flash.sector_lock = old_sector_lock[:]
new_sector_lock = conf.flash.sector_lock[:]

stest.expect_equal(new_sector_lock, old_sector_lock)
