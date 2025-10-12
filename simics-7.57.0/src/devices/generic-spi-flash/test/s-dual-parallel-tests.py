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
                                 sector_number   = 64,
                                 frdo_enabled    = True,
                                 frqo_enabled    = True,
                                 fpdi_enabled    = True,
                                 fpqi_enabled    = True,
                                 dual_parallel_enabled = True)

testbench.test_read_write_flash()
testbench.test_page_write_flash()
testbench.test_page_erase()
testbench.test_subsector_erase()
testbench.test_sector_erase()
testbench.test_bulk_erase()
testbench.test_rsfdp()

testbench.test_dual_parallel_mode_switch()
