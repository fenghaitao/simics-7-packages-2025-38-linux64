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


# setup: same chip as the mpc8260 board (from which the commands have been taken)
# test: if chip ends up in 'Unimplemented' mode, it should be possible to reset the chip
#

from stest import expect_equal

SIM_source_python_in_module("common.py", __name__)

make_flash_configuration("Am29DL323GB", interleave=4, bus_width=64, big_endian=1)

# set chip-mode to "Unimplemented", this could happen and should not block state machine
conf.flash.chip_mode = ['Unimplemented'] * 4

# reset flash, test state then write something
set64(0x0000000000000000, 0xf000f000f000f000)
expect_equal(conf.flash.chip_mode, ['Read-Array'] * 4, 'reset to read-array mode')
set64(0x0000000000002aa8, 0xaa00aa00aa00aa00)
set64(0x0000000000001550, 0x5500550055005500)
set64(0x0000000000002aa8, 0xa000a000a000a000)
set64(0x0000000000e80218, 0xdeadbeef00000000)
expect_hex("memory", get64(0xe80218), 0xdeadbeef00000000)
