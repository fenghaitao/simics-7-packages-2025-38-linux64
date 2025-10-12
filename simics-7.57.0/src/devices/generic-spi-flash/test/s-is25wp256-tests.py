# © 2022 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import test_bench

#run_command('log-level 4')
testbench = test_bench.TestBench(#bp_mask         = 0x3,
                                 sector_size     = 64 * 1024,
                                 sector_number   = 512,
                                 elec_signature  = 0x17,
                                 JEDEC_signature = [0x9d, 0x60, 0x19])

testbench.test_elec_signature()
testbench.test_elec_signature(expected=0x13, result=False)
testbench.test_flash_status()
testbench.test_read_write_flash()
testbench.test_sector_erase()
testbench.test_bulk_erase()
testbench.test_jedec_id()
testbench.test_write_bank_address_volatile()
testbench.test_write_bank_address_non_volatile()
