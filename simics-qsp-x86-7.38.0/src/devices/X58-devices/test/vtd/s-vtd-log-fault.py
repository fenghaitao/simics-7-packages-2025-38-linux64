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


# s-vtd-log-fault.py

from vtd_tb import *

fr_size        = VTdConst.fault_record_size
fault_log_cnt  = 1000 # 1000 is enough for multiplication of test parameters
fault_log_base = tb.alloc_permanent_mem(fault_log_cnt * fr_size,
                                        VTdConst.page_size)
fault_log_idx  = 0

def do_test():
    for (fr, advanced_log) in (
            (fr, advanced_log)
                for fr in VTdConst.fault_reason_list
                for advanced_log in (0, 1)):

        if advanced_log and not vtd_hw_drv.has_capability('AFL'):
            continue

        vtd_hw_drv.reset_vtd_hw()
        if advanced_log:
            vtd_hw_drv.config_advanced_fault_log(
                fault_log_base, fault_log_cnt * fr_size)
            mem_space_drv.write_mem(fault_log_base,
                [0x00 for i in range(fault_log_cnt * fr_size)])
            vtd_hw_drv.enable_advanced_fault_log(1)

        # Generate a fault of this reason
        if (fr == VTdConst.fr_non_existing_rt_addr
            or fr == VTdConst.fr_no_present_root_entry):
            if PRINT_DEBUG_INFO:
                print("fault reason: 0x%x" % fr)
            if fr == VTdConst.fr_no_present_root_entry:
                re_base = tb.alloc_permanent_mem(VTdConst.page_size)
                mem_space_drv.write_mem(re_base,
                                        tuple([0x00] * VTdConst.page_size))
                vtd_hw_drv.config_rt_addr(re_base)
            vtd_hw_drv.enable_dma_remapping(1)
            vtd_hw_drv.issue_dma_remapping(
                0, 0, 0, 0x10000, VTdHwDriver.dma_read, 4)
            # Check the fault reason is correctly recorded
            if advanced_log:
                log_val = mem_space_drv.read_value_le(
                            fault_log_base + fault_log_idx * fr_size, fr_size)
            else:
                log_val = vtd_hw_drv.read_reg("FRCD0")

            fields = VTdConst.frcd_bf.fields(log_val)
            stest.expect_equal(fields['FR'], fr, "fault reason")

do_test()
