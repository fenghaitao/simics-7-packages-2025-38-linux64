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


# Bug 18081 - Erase problem with multi-chips amd flash module:
# only the last chip can go back to FS_read_array after erase done

SIM_source_python_in_module("common.py", __name__)

make_flash_configuration("S29GL256N", 2, 32)

# need a clock to be able to test timing
SIM_create_object("clock", "clock", freq_mhz=1)
conf.flash.queue = conf.clock
conf.flash.timing_model['AMD Erase In Progress'] = 50e-6

secsize = 256*1024

fill(1 * secsize - 1, 1 * secsize + 1, 0xaa)
fill(2 * secsize - 1, 2 * secsize + 1, 0xbb)
fill(3 * secsize - 1, 3 * secsize + 1, 0xcc)

expect("idle", conf.flash.chip_mode, ["Read-Array", "Read-Array"])

# send erase to chip 0
set16(0x555*4, 0xAA)
set16(0x2AA*4, 0x55)
set16(0x555*4, 0x80)
set16(0x555*4, 0xAA)
set16(0x2AA*4, 0x55)
set16(1 * secsize, 0x30)

expect("chip 0 in progress", conf.flash.chip_mode,
       ["AMD Erase In Progress", "Read-Array"])

# send erase to chip 1
set16(0x555*4 + 2, 0xAA)
set16(0x2AA*4 + 2, 0x55)
set16(0x555*4 + 2, 0x80)
set16(0x555*4 + 2, 0xAA)
set16(0x2AA*4 + 2, 0x55)
set16(1 * secsize + 2, 0x30)

expect("both chips in progress", conf.flash.chip_mode,
       ["AMD Erase In Progress", "AMD Erase In Progress"])

# cancel chip 0
set16(0x555*4, 0xF0)

expect("both chips in progress", conf.flash.chip_mode,
       ["Read-Array", "AMD Erase In Progress"])

SIM_continue(60) # let time pass

expect("both chips idle again", conf.flash.chip_mode,
       ["Read-Array", "Read-Array"])
