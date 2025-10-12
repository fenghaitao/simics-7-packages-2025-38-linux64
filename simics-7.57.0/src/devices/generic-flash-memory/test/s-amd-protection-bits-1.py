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


# setup: a non-uniform 16-bit AMD CFI compatible flash on a 16-bit bus
#
# test:
# - dyb bits
# - ppb bits
# - ppb lock bit
#

SIM_source_python_in_module("common.py", __name__)

make_flash_configuration("S29GL256N", 1, 16)

# autoselect at correct address
set16(0x555*2, 0xAA)
set16(0x2AA*2, 0x55)
set16(0x555*2, 0x90)
expect_hex("manuf. ID:",    get16(0*2), 0x01)
expect_hex("device ID:",    get16(1*2), 0x227E)
expect_hex("lock status:",  get16(2*2), 0x0)
expect_hex("outside query", get16(3*2), 0x0)
expect_hex("wrap around at 256 bytes", get16(256*2), 0x01)
expect_hex("beginning of block 2, manuf. ID:",   get16(0x10000), 0x01)
expect_hex("beginning of block 2, device ID:",   get16(0x10000+1*2), 0x227E)
expect_hex("beginning of block 2, lock status:", get16(0x10000+2*2), 0x0)

# CFI
set16(0x55*2, 0x98)
expect_hex("CFI: signature 1", get16(0x10*2), 0x51)
expect_hex("CFI: signature 2", get16(0x11*2), 0x52)
expect_hex("CFI: signature 3", get16(0x12*2), 0x59)

expect_hex("CFI: extended 1", get16(0x40*2), 0x50)
expect_hex("CFI: extended 2", get16(0x41*2), 0x52)
expect_hex("CFI: extended 3", get16(0x42*2), 0x49)

# reset
set16(0, 0xF0)

# verify protection bits after bootup
expect("poweron ppb bits", conf.flash.ppb_bits[0], [1]*256)
expect("poweron dyb bits", conf.flash.dyb_bits[0], [1]*256)
expect("poweron ppb lock bit", conf.flash.amd_ppb_lock_bit[0], 1)

secsize = 128*1024

# set bits according to following:
# sector 0: unprotected
# sector 1: dynamically protected
# sector 2: persistent protected
# sector 3: both dynamically and persistently protected

set16(0x555*2, 0xAA)
set16(0x2AA*2, 0x55)
set16(0x555*2, 0xE0)
set16(0, 0xA0)
set16(secsize*1, 0x00) # DYI[1] = 0
set16(0, 0xA0)
set16(secsize*3, 0x00) # DYI[3] = 0
set16(0, 0x90)
set16(0, 0x00)

set16(0x555*2, 0xAA)
set16(0x2AA*2, 0x55)
set16(0x555*2, 0xC0)
set16(0, 0xA0)
set16(secsize*2, 0x00) # PPB[2] = 0
set16(0, 0xA0)
set16(secsize*3, 0x00) # PPB[3] = 0
set16(0, 0x90)
set16(0, 0x00)

# verify protection bits after setting them
expect("ppb bits after set", conf.flash.ppb_bits[0][:4], [1,1,0,0])
expect("dyb bits after set", conf.flash.dyb_bits[0][:4], [1,0,1,0])

set16(0x555*2, 0xAA)
set16(0x2AA*2, 0x55)
set16(0x555*2, 0xE0)
expect_hex("DYB 0", get16(secsize*0), 1)
expect_hex("DYB 1", get16(secsize*1), 0)
expect_hex("DYB 2", get16(secsize*2), 1)
expect_hex("DYB 3", get16(secsize*3), 0)
set16(0, 0x90)
set16(0, 0x00)

set16(0x555*2, 0xAA)
set16(0x2AA*2, 0x55)
set16(0x555*2, 0xC0)
expect_hex("PPB 0", get16(secsize*0), 1)
expect_hex("PPB 1", get16(secsize*1), 1)
expect_hex("PPB 2", get16(secsize*2), 0)
expect_hex("PPB 3", get16(secsize*3), 0)
set16(0, 0x90)
set16(0, 0x00)

# program test, protected sections should not be programmable
for i in range(4):
    set16(0x555*2, 0xAA)
    set16(0x2AA*2, 0x55)
    set16(0x555*2, 0xA0)
    set16(i*secsize, 0x1234)

expect_hex("two-byte program 0", get16(secsize*0), 0x1234)
expect_hex("two-byte program 1", get16(secsize*1), 0xffff)
expect_hex("two-byte program 2", get16(secsize*2), 0xffff)
expect_hex("two-byte program 3", get16(secsize*3), 0xffff)

# Set PPB lock bit and try to program a PPB - it should not work
set16(0x555*2, 0xAA) # enter ppb lock command set
set16(0x2AA*2, 0x55)
set16(0x555*2, 0x50)
expect_hex("read ppb lock bit before set", get16(0), 1)
set16(0, 0xA0) # do the programming
set16(0, 0x00)
expect_hex("read ppb lock bit after set", get16(0), 0)
set16(0, 0x90) # exit ppb lock command set
set16(0, 0x00)
expect("ppb lock bit after set", conf.flash.amd_ppb_lock_bit[0], 0)

set16(0x555*2, 0xAA)
set16(0x2AA*2, 0x55)
set16(0x555*2, 0xC0)
set16(0, 0xA0)
set16(secsize*0, 0x00) # try PPB[0] = 0
set16(0, 0x90)
set16(0, 0x00)
expect("ppb bits after tried set", conf.flash.ppb_bits[0][:4], [1,1,0,0])

# test that a reset will reset DYB bits, but not PPB bits
conf.flash.ports.Reset.signal.signal_raise()
conf.flash.ports.Reset.signal.signal_lower()

# verify protection bits after setting them
expect("reset ppb bits", conf.flash.ppb_bits[0][:4], [1,1,0,0])
expect("reset dyb bits", conf.flash.dyb_bits[0][:4], [1,1,1,1])
expect("reset ppb lock", conf.flash.amd_ppb_lock_bit[0], 0)
