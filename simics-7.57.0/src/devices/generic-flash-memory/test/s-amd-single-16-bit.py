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
# - AMD command set for 16-bits on 16-bits bus (all + unlock bypass)
# - non-uniform sectors (lock info, erase)
# - CFI
# - chip erase
#

SIM_source_python_in_module("common.py", __name__)

make_flash_configuration("Am29SL160CT", 1, 16)

# autoselect at correct address
set16(0x555*2, 0xAA)
set16(0x2AA*2, 0x55)
set16(0x555*2, 0x90)
expect_hex("manuf. ID:",    get16(0*2), 0x01)
expect_hex("device ID:",    get16(1*2), 0x22A4)
expect_hex("lock status:",  get16(2*2), 0x0)
expect_hex("outside query", get16(3*2), 0x0)
expect_hex("wrap around at 256 bytes", get16(256*2), 0x01)
expect_hex("beginning of block 2, manuf. ID:",   get16(0x10000), 0x01)
expect_hex("beginning of block 2, device ID:",   get16(0x10000+1*2), 0x22A4)
expect_hex("beginning of block 2, lock status:", get16(0x10000+2*2), 0x0)

# now set some lock status to test that we are talking to the right block
conf.flash.lock_status = [[1, 0, 1, 1, 0, 0, 1, 1,
                           1, 0, 0, 0, 1, 1, 1, 1,
                           0, 0, 0, 0, 1, 1, 1, 1,
                           1, 0, 0, 0, 0, 0, 1, 1,
                           1, 1, 1, 1, 0, 0, 0]]

# read all lock status
lock_status_begin = []
for i in range(31):
    lock_status_begin.append(get16(0x10000*i + 2*2))
for i in range(8):
    lock_status_begin.append(get16(0x1F0000 + 0x2000*i + 2*2))
expect("lock status at beginning of blocks",
      [lock_status_begin], conf.flash.lock_status)

# reset
set16(0, 0xF0)

# CFI
set16(0x55*2, 0x98)
expect_hex("CFI: signature 1", get16(0x10*2), 0x51)
expect_hex("CFI: signature 2", get16(0x11*2), 0x52)
expect_hex("CFI: signature 3", get16(0x12*2), 0x59)

expect_hex("CFI: extended 1", get16(0x40*2), 0x50)
expect_hex("CFI: extended 2", get16(0x41*2), 0x52)
expect_hex("CFI: extended 3", get16(0x42*2), 0x49)

set16(0, 0xF0)

# program test
fill(0, 0x10004, 0xcc)
set16(0x555*2, 0xAA)
set16(0x2AA*2, 0x55)
set16(0x555*2, 0xA0)
set16(0x10000, 0x1234)
expect_hex("two-byte program 1", get16(0x10000), 0x1234)
expect_hex("two-byte program 2", get16(0x0), 0xcccc)
expect_hex("two-byte program 3", get16(0xFFFE), 0xcccc)
expect_hex("two-byte program 4", get16(0x10002), 0xcccc)

# unlock bypass/program
set16(0x555*2, 0xAA)
set16(0x2AA*2, 0x55)
set16(0x555*2, 0x20)

set16(0, 0xA0)
set16(0x20000, 0xABCD)
set16(0, 0xA0)
set16(0x20002, 0x5321)
set16(0, 0xA0)
set16(0x30010, 0x8765)
set16(0, 0xA0)
set16(0x40012, 0x1357)

# unlock bypass/reset
set16(0, 0x90)
set16(0, 0)

expect_hex("unlock bypass program 1", get16(0x1FFFE), 0xffff)
expect_hex("unlock bypass program 2", get16(0x20000), 0xABCD)
expect_hex("unlock bypass program 3", get16(0x20002), 0x5321)
expect_hex("unlock bypass program 4", get16(0x20004), 0xffff)
expect_hex("unlock bypass program 5", get16(0x3000E), 0xffff)
expect_hex("unlock bypass program 6", get16(0x30010), 0x8765)
expect_hex("unlock bypass program 7", get16(0x30012), 0xffff)
expect_hex("unlock bypass program 8", get16(0x40010), 0xffff)
expect_hex("unlock bypass program 9", get16(0x40012), 0x1357)
expect_hex("unlock bypass program 10", get16(0x40014), 0xffff)

# unlock bypass/write to buffer program
set16(0x555*2, 0xAA)
set16(0x2AA*2, 0x55)
set16(0x555*2, 0x20)

set16(0x30050, 0x25)      # write to buffer command
set16(0x30050, 0x0002)    # start address and number of words - 1 (max 512)
set16(0x30050, 0x1234)
set16(0x30052, 0x5678)
set16(0x30054, 0x9abc)
set16(0x30050, 0x29)      # confirm

# In Unlock Bypass mode, the chip can be read as if it were in read-array mode.
expect_hex("unlock bypass buffer program 1", get16(0x3004E), 0xffff)
expect_hex("unlock bypass buffer program 2", get16(0x30050), 0x1234)
expect_hex("unlock bypass buffer program 3", get16(0x30052), 0x5678)
expect_hex("unlock bypass buffer program 4", get16(0x30054), 0x9abc)
expect_hex("unlock bypass buffer program 5", get16(0x30056), 0xffff)

# Test unlock bypass sector erase
fill(0x30000, 0x40004, 0xcc)
set16(0, 0x80)
set16(0x30098, 0x30)
expect_hex("unlock bypass sector erase", get16(0x30000), 0xffff)
expect_hex("unlock bypass sector erase", get16(0x3fffe), 0xffff)
expect_hex("unlock bypass sector erase", get16(0x40000), 0xcccc)

# unlock bypass/reset
set16(0, 0x90)
set16(0, 0)

# sector erase
set16(0x555*2, 0xAA)
set16(0x2AA*2, 0x55)
set16(0x555*2, 0x80)
set16(0x555*2, 0xAA)
set16(0x2AA*2, 0x55)
set16(0x10000, 0x30)

expect_hex("sector erase 1", get16(0x10000), 0xFFFF)
expect_hex("sector erase 2", get16(0xFFFE),  0xcccc)
expect_hex("sector erase 3", get16(0x1FFFE), 0xFFFF)
expect_hex("sector erase 4", get16(0x20000), 0xABCD)

# sector erase (a smaller sector)
fill(0x1f7ff0, 0x1fa010, 0xcc)
set16(0x555*2, 0xAA)
set16(0x2AA*2, 0x55)
set16(0x555*2, 0x80)
set16(0x555*2, 0xAA)
set16(0x2AA*2, 0x55)
set16(0x1F8000, 0x30)

expect_hex("sector erase 5", get16(0x1F8000), 0xFFFF)
expect_hex("sector erase 6", get16(0x1F7FFE), 0xcccc)
expect_hex("sector erase 7", get16(0x1F9FFE), 0xFFFF)
expect_hex("sector erase 8", get16(0x1FA000), 0xcccc)

# sector erase (last sector, non-aligned address)
set16(0x555*2, 0xAA)
set16(0x2AA*2, 0x55)
set16(0x555*2, 0x80)
set16(0x555*2, 0xAA)
set16(0x2AA*2, 0x55)
set16(0x1FF000, 0x30) # last sector 0x1fe000-0x1fffff
expect_hex("sector erase 9", get16(0x1FE000), 0xFFFF)
expect_hex("sector erase 10", get16(0x1FFFFE), 0xFFFF)

# chip erase
expect_hex("chip erase 1", get16(0x20000), 0xABCD)
set16(0x555*2, 0xAA)
set16(0x2AA*2, 0x55)
set16(0x555*2, 0x80)
set16(0x555*2, 0xAA)
set16(0x2AA*2, 0x55)
set16(0x555*2, 0x10)
expect_hex("chip erase 2", get16(0x2000), 0xFFFF)

# unlock bypass/chip erase
set16(0x555*2, 0xAA)
set16(0x2AA*2, 0x55)
set16(0x555*2, 0x20)

# According to bug 20011, it should be possible to do a reset in unlock bypass
# mode, and it should stay in unlock bypass mode.
set16(0x555*2, 0xF0)  # 1-cycle reset

set16(0x555*2, 0xAA)  # 3-cycle reset
set16(0x2AA*2, 0x55)
set16(0x555*2, 0xF0)

fill(0x40000, 0x40004, 0xcc)

# Test unlock bypass chip erase
set16(0, 0x80)
set16(0, 0x10)
expect_hex("unlock bypass chip erase", get16(0x40000), 0xffff)

# unlock bypass/reset
set16(0, 0x90)
set16(0, 0)

# read/program lock register
set16(0x555*2, 0xAA)
set16(0x2AA*2, 0x55)
set16(0x555*2, 0x40)
expect("lock register status 1", conf.flash.chip_mode[0], "AMD Lock Register Command Set")
expect("lock register default value", conf.flash.amd_lock_register[0], 0xffff)
conf.flash.amd_lock_register[0] = 0xbabe
expect_hex("lock register read", get16(0), 0xbabe)
set16(0,       0xA0)
set16(0,       0x7f7f)
expect_hex("lock register program", get16(0), 0x3a3e)
set16(0,       0x90)
set16(0,       0x00)
expect_hex("lock register exit", get16(0), 0xFFFF)
