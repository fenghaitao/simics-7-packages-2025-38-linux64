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


# s-vtd-fault-event.py
# tests fault event reporting in the Intel (r) VT-d hardware

from vtd_tb import *

vtd_dest_cpu    = 0x3
vtd_vector      = 0x88

one_msg_addr = VTdConst.compat_int_msg_addr_bf.value(
                    FEE  = 0xFEE,
                    DID  = vtd_dest_cpu,
                    IF   = 0,
                    RH   = 0,
                    DM   = 0,
                )

one_msg_data = VTdConst.compat_int_msg_data_bf.value(
                    TM   = VTdConst.irte_tm_edge,
                    TML  = 0,
                    DM   = VTdConst.irte_dlm_fixed,
                    V    = vtd_vector,
                )

def do_test():
    vtd_hw_drv.reset_vtd_hw()
    vtd_hw_drv.config_fault_event_int(one_msg_addr, one_msg_data)
    # To pend an interrupt, IM (Interrupt Mask) should be set
    vtd_hw_drv.enable_fault_event_int(0)

    # Generate a fault
    vtd_hw_drv.enable_dma_remapping(1)
    vtd_hw_drv.issue_dma_remapping(0, 0, 0, 0x10000, VTdHwDriver._dma_read, 4)
    (real_cpu, real_vector, tm, dm, dlm) = \
        vtd_hw_drv.get_and_clear_int_data()
    stest.expect_equal(real_cpu, vtd_dest_cpu,
            "destination cpu of Intel (r) VT-d hardware interrupt")
    stest.expect_equal(real_vector, vtd_vector,
            "vector of Intel (r) VT-d hardware interrupt")
    # Check the interrupt status
    fields = VTdConst.fectl_bf.fields(vtd_hw_drv.read_reg("FECTL"))
    stest.expect_equal(fields['IP'], 1, "pending interrupt")
    fields = VTdConst.fsts_bf.fields(vtd_hw_drv.read_reg("FSTS"))
    stest.expect_equal(fields['PPF'], 1, "primary pending fault")
    # Clear the interrupt status
    vtd_hw_drv.write_reg("FRCD0", VTdConst.frcd_bf.value(F = 1))
    fields = VTdConst.fsts_bf.fields(vtd_hw_drv.read_reg("FSTS"))
    stest.expect_equal(fields['PPF'], 0, "cleared primary pending fault")

do_test()
