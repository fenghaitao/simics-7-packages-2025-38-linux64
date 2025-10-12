# © 2017 Intel Corporation
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
testbench = test_bench.TestBench(#bp_mask         = 0x7,
                                 sector_size     = 0x10000,
                                 sector_number   = 256,
                                 elec_signature  = 0x17,
                                 JEDEC_signature = [0xef, 0x40, 0x18],
                                 frdo_enabled    = True,
                                 frqo_enabled    = True,
                                 fpdi_enabled    = True,
                                 fpqi_enabled    = True)

testbench.test_elec_signature()
testbench.test_elec_signature(expected=0x11, result=False)
testbench.test_flash_status()
testbench.test_read_write_flash()
testbench.test_page_write_flash()
testbench.test_page_erase()
testbench.test_subsector_erase()
testbench.test_sector_erase()
testbench.test_32KB_block_erase()
testbench.test_bulk_erase()
testbench.test_chip_erase()
testbench.test_jedec_id()
testbench.test_rmdid()
testbench.test_cmd_counter()
testbench.test_rsfdp()
