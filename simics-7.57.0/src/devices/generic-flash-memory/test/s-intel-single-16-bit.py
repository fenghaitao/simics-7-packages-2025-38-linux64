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


# setup: a uniform 16-bit Intel CFI compatible flash on a 16-bit bus
#
# test:
# - Intel command set for 16-bits on 16-bits bus
# - variable write-buffer size
# - extended CFI
#

SIM_source_python_in_module("common.py", __name__)

make_flash_configuration("28F640J3", 1, 16)

# intel identifiers
set16(0, 0x90)
expect_hex("manuf. ID:",    get16(0*2), 0x89)
expect_hex("device ID:",    get16(1*2), 0x17)
expect_hex("lock status:",  get16(2*2), 0x0)
expect_hex("outside query", get16(3*2), 0x0)
expect_hex("beginning of block 2, manuf. ID:",   get16(0x20000), 0x89)
expect_hex("beginning of block 2, device ID:",   get16(0x20000+1*2), 0x17)
expect_hex("beginning of block 2, lock status:", get16(0x20000+2*2), 0x0)

# now set some lock status to test that we are talking to the right block
conf.flash.lock_status = [[1, 0, 1, 1, 0, 0, 1, 1,
                           1, 0, 0, 0, 1, 1, 1, 1,
                           0, 0, 0, 0, 1, 1, 1, 1,
                           1, 0, 0, 0, 0, 0, 1, 1,
                           1, 1, 1, 1, 0, 0, 0, 0,
                           0, 0, 1, 1, 1, 1, 1, 1,
                           1, 0, 0, 0, 0, 0, 0, 0,
                           1, 1, 1, 1, 1, 1, 1, 1]]

# read all lock status
lock_status_begin = []
for i in range(64):
    lock_status_begin.append(get16(0x20000*i + 2*2))
expect("lock status at beginning of blocks",
      [lock_status_begin], conf.flash.lock_status)

# reset
set16(0, 0xFF)

# CFI
set16(0, 0x98)
expect_hex("CFI: signature 1", get16(0x10*2), 0x51)
expect_hex("CFI: signature 2", get16(0x11*2), 0x52)
expect_hex("CFI: signature 3", get16(0x12*2), 0x59)

expect_hex("CFI: extended 1", get16(0x31*2), 0x50)
expect_hex("CFI: extended 2", get16(0x32*2), 0x52)
expect_hex("CFI: extended 3", get16(0x33*2), 0x49)

set16(0, 0xFF)


# extended CFI
cfi_struct = conf.flash.cfi_query
# pad with 0 up to 0x100
for i in range(0x100-0x46):
    cfi_struct = cfi_struct + (0x0,)
# add 0,1,2, ... at 0x100
for i in range(0x100):
    cfi_struct = cfi_struct + (i,)
conf.flash.cfi_query = cfi_struct

set16(0, 0x98)
expect_hex("CFI: signature 1", get16(0x10*2), 0x51)
expect_hex("CFI: signature 2", get16(0x11*2), 0x52)
expect_hex("CFI: signature 3", get16(0x12*2), 0x59)

expect_hex("CFI: extended 1", get16(0x31*2), 0x50)
expect_hex("CFI: extended 2", get16(0x32*2), 0x52)
expect_hex("CFI: extended 3", get16(0x33*2), 0x49)

# after 0x100
expect_hex("CFI: large 1", get16(0x100*2), 0x0)
expect_hex("CFI: large 2", get16(0x101*2), 0x1)
expect_hex("CFI: large 3", get16(0x1FF*2), 0xFF)

# at block limit, wrap around
expect_hex("CFI: wrap 1", get16(0x20000 + 0x10*2), 0x51)
expect_hex("CFI: wrap 2", get16(0x20000 + 0x11*2), 0x52)
expect_hex("CFI: wrap 3", get16(0x20000 + 0x12*2), 0x59)

set16(0, 0xFF)


# program test
fill(0, 0x10010, 0xcc)
set16(0, 0x40)
set16(0x10000, 0x1234)
expect_hex("two-byte program 1", get16(0x10000), 0x80) # status
set16(0x10000, 0x50) # clear status register
expect_hex("two-byte program 1", get16(0x10000), 0x1234)
expect_hex("two-byte program 2", get16(0x0), 0xcccc)
expect_hex("two-byte program 3", get16(0xFFFE), 0xcccc)
expect_hex("two-byte program 4", get16(0x10002), 0xcccc)

# write buffer - 16 words
set16(0x20200, 0xE8)
set16(0x20200, 15)

set16(0x20200, 0x0102)
set16(0x20202, 0x0404)
set16(0x20204, 0x0506)
set16(0x20206, 0x0708)
set16(0x20208, 0x0910)
set16(0x2020A, 0x1112)
set16(0x2020C, 0x1314)
set16(0x2020E, 0x1516)
set16(0x20210, 0x1718)
set16(0x20212, 0x1920)
set16(0x20214, 0x2122)
set16(0x20216, 0x2324)
set16(0x20218, 0x2526)
set16(0x2021A, 0x2728)
set16(0x2021C, 0x2930)
set16(0x2021E, 0x3132)

set16(0x20200, 0xD0)
set16(0, 0x50)

expect_hex("write buffer 1", get16(0x201FE), 0xffff)
expect_hex("write buffer 2", get16(0x20200), 0x0102)
expect_hex("write buffer 3", get16(0x20202), 0x0404)
expect_hex("write buffer 4", get16(0x20204), 0x0506)
expect_hex("write buffer 5", get16(0x20206), 0x0708)
expect_hex("write buffer 6", get16(0x20208), 0x0910)
expect_hex("write buffer 7", get16(0x2020A), 0x1112)
expect_hex("write buffer 8", get16(0x2020C), 0x1314)
expect_hex("write buffer 9", get16(0x2020E), 0x1516)
expect_hex("write buffer 10", get16(0x20210), 0x1718)
expect_hex("write buffer 11", get16(0x20212), 0x1920)
expect_hex("write buffer 12", get16(0x20214), 0x2122)
expect_hex("write buffer 13", get16(0x20216), 0x2324)
expect_hex("write buffer 14", get16(0x20218), 0x2526)
expect_hex("write buffer 15", get16(0x2021A), 0x2728)
expect_hex("write buffer 16", get16(0x2021C), 0x2930)
expect_hex("write buffer 17", get16(0x2021E), 0x3132)
expect_hex("write buffer 18", get16(0x20220), 0xffff)

# write buffer, 16 words, but unordered
set16(0x30200, 0xE8)
set16(0x30200, 15)

set16(0x30200, 0x0102)
set16(0x30218, 0x2526)
set16(0x3020C, 0x1314)
set16(0x3021C, 0x2930)
set16(0x30204, 0x0506)
set16(0x3021A, 0x2728)
set16(0x30214, 0x2122)
set16(0x30206, 0x0708)
set16(0x30202, 0x0404)
set16(0x30208, 0x0910)
set16(0x3020A, 0x1112)
set16(0x3020E, 0x1516)
set16(0x30210, 0x1718)
set16(0x30212, 0x1920)
set16(0x30216, 0x2324)
set16(0x3021E, 0x3132)

set16(0x30200, 0xD0)
set16(0, 0x50)

expect_hex("write buffer unordered 1", get16(0x301FE), 0xffff)
expect_hex("write buffer unordered 2", get16(0x30200), 0x0102)
expect_hex("write buffer unordered 3", get16(0x30202), 0x0404)
expect_hex("write buffer unordered 4", get16(0x30204), 0x0506)
expect_hex("write buffer unordered 5", get16(0x30206), 0x0708)
expect_hex("write buffer unordered 6", get16(0x30208), 0x0910)
expect_hex("write buffer unordered 7", get16(0x3020A), 0x1112)
expect_hex("write buffer unordered 8", get16(0x3020C), 0x1314)
expect_hex("write buffer unordered 9", get16(0x3020E), 0x1516)
expect_hex("write buffer unordered 10", get16(0x30210), 0x1718)
expect_hex("write buffer unordered 11", get16(0x30212), 0x1920)
expect_hex("write buffer unordered 12", get16(0x30214), 0x2122)
expect_hex("write buffer unordered 13", get16(0x30216), 0x2324)
expect_hex("write buffer unordered 14", get16(0x30218), 0x2526)
expect_hex("write buffer unordered 15", get16(0x3021A), 0x2728)
expect_hex("write buffer unordered 16", get16(0x3021C), 0x2930)
expect_hex("write buffer unordered 17", get16(0x3021E), 0x3132)
expect_hex("write buffer unordered 18", get16(0x30220), 0xffff)

# test with a smaller write buffer unordered
conf.flash.write_buffer_size = 16 # bytes

set16(0x40200, 0xE8)
set16(0x40200, 7)

set16(0x40200, 0x0102)
set16(0x40202, 0x2526)
set16(0x40204, 0x1314)
set16(0x40206, 0x2930)
set16(0x40208, 0x0506)
set16(0x4020A, 0x2728)
set16(0x4020C, 0x2122)
set16(0x4020E, 0x0708)

set16(0x40200, 0xD0)
set16(0, 0x50)

expect_hex("write buffer smaller 1", get16(0x401FE), 0xffff)
expect_hex("write buffer smaller 2", get16(0x40200), 0x0102)
expect_hex("write buffer smaller 3", get16(0x40202), 0x2526)
expect_hex("write buffer smaller 4", get16(0x40204), 0x1314)
expect_hex("write buffer smaller 5", get16(0x40206), 0x2930)
expect_hex("write buffer smaller 6", get16(0x40208), 0x0506)
expect_hex("write buffer smaller 7", get16(0x4020A), 0x2728)
expect_hex("write buffer smaller 8", get16(0x4020C), 0x2122)
expect_hex("write buffer smaller 9", get16(0x4020E), 0x0708)
expect_hex("write buffer smaller 10", get16(0x40210), 0xffff)

# sector erase
fill(0x5fff0, 0x80010, 0xcc)
set16(0x60000, 0x20)
set16(0x60014, 0xD0)                    # write to address inside block
set16(0, 0x50)

expect_hex("sector erase 1", get16(0x60000), 0xFFFF)
expect_hex("sector erase 2", get16(0x5FFFE), 0xcccc)
expect_hex("sector erase 3", get16(0x7FFFE), 0xFFFF)
expect_hex("sector erase 4", get16(0x80000), 0xcccc)

# sector erase (last sector, unaligned address)
fill(0x7dfff0, 0x800000, 0xcc)
set16(0x7f0000, 0x20)
set16(0x7f0000, 0xD0)
set16(0, 0x50)

expect_hex("sector erase 5", get16(0x7E0000), 0xFFFF)
expect_hex("sector erase 6", get16(0x7dFFFE), 0xcccc)
expect_hex("sector erase 7", get16(0x7FFFFE), 0xFFFF)


# simple lock system
# clear all lock bits
set16(0x0, 0x60)
set16(0x0, 0xD0)

# now set some lock status to test that we are talking to the right block
lock_status_cleared = [[0, 0, 0, 0, 0, 0, 0, 0,
                        0, 0, 0, 0, 0, 0, 0, 0,
                        0, 0, 0, 0, 0, 0, 0, 0,
                        0, 0, 0, 0, 0, 0, 0, 0,
                        0, 0, 0, 0, 0, 0, 0, 0,
                        0, 0, 0, 0, 0, 0, 0, 0,
                        0, 0, 0, 0, 0, 0, 0, 0,
                        0, 0, 0, 0, 0, 0, 0, 0]]

expect("lock status after clear",
      lock_status_cleared, conf.flash.lock_status)

# set lock on sector 0x80000
set16(0x0, 0x60)
set16(0x80000, 0x1)

lock_status_cleared[0][4] = 1
expect("lock status after set",
      lock_status_cleared, conf.flash.lock_status)
