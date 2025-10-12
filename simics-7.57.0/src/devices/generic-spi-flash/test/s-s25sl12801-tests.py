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


import test_bench

#run_command('log-level 4')
testbench = test_bench.TestBench(#bp_mask         = 0x15,
                                 sector_size     = 0x10000,
                                 sector_number   = 256,
                                 #elec_signature  = 0x15,
                                 JEDEC_signature = [0x01, 0x20, 0x18],
                                 extended_id = [0x03, 0x0])

testbench.test_elec_signature()
testbench.test_elec_signature(expected=0x11, result=False)
testbench.test_flash_status()
testbench.test_read_write_flash()
testbench.test_sector_erase()
testbench.test_bulk_erase()
testbench.test_jedec_id()
testbench.test_jedec_id([0x20, 0x20, 0x15], result=False)
testbench.test_sector_protection(2, 252)
testbench.test_program_protection(0, 256)
testbench.test_program_protection(1, 254)
testbench.test_program_protection(2, 252)
testbench.test_program_protection(3, 248)
testbench.test_program_protection(4, 240)
testbench.test_program_protection(5, 224)
testbench.test_program_protection(6, 192)
testbench.test_program_protection(7, 128)
testbench.test_program_protection(8, -1)
