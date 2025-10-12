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


# setup: same as s-amd-sector-erase-per-chip.py (bug 18081)
# test: if chip suspends the erase, it should not end up in 'Unimplemented' mode,
#       it should end up in Read-Array mode (i.e. suspend completes the erase and
#       resume is a NOP)
#

def filter_flash_events(queue):
    chip_id = []
    for (_, desc, id, _, _) in queue:
        if "operation done" in desc:
            chip_id.append(id)
    return chip_id

SIM_source_python_in_module("common.py", __name__)

make_flash_configuration("S29GL256N", 2, 32)  # bug 21451 is S29GL512N

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
expect("one pending event", filter_flash_events(conf.clock.time_queue), [0])

# send erase to chip 1
set16(0x555*4 + 2, 0xAA)
set16(0x2AA*4 + 2, 0x55)
set16(0x555*4 + 2, 0x80)
set16(0x555*4 + 2, 0xAA)
set16(0x2AA*4 + 2, 0x55)
set16(1 * secsize + 2, 0x30)

expect("both chips in progress", conf.flash.chip_mode,
       ["AMD Erase In Progress", "AMD Erase In Progress"])
expect("two pending events", filter_flash_events(conf.clock.time_queue), [0, 1])

# suspend chip 0
set16(0x555*4, 0xB0)

expect("chip 0 completed, chip 1 still in progress", conf.flash.chip_mode,
       ["Read-Array", "AMD Erase In Progress"])
expect("one pending event", filter_flash_events(conf.clock.time_queue), [1])

SIM_continue(60) # let time pass

expect("both chips idle again", conf.flash.chip_mode,
       ["Read-Array", "Read-Array"])
expect("no pending events", filter_flash_events(conf.clock.time_queue), [])

# resume chip 0
set16(0x555*4, 0x30)

expect("both chips still idle", conf.flash.chip_mode,
       ["Read-Array", "Read-Array"])
expect("still no pending events", filter_flash_events(conf.clock.time_queue), [])
