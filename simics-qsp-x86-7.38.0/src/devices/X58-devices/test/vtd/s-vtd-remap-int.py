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


# s-vtd-remap-int.py

from vtd_tb import *

if not vtd_hw_drv.has_capability('IR'):
    if PRINT_DEBUG_INFO:
        print("Interrupt remapping is not supported, no need to do this test")

# pci_bus_id:        PCI bus ID in the root complex
# device_id:         device ID in the input PCI bus, 0-indexed
# dest_cpu_id:       destination processor ID
# vector:            interrupt vector of this remapping
# deliv_mode:        delivery mode, i.e., to which processor and which pin
# trig_mode:         trigger mode, level or edge
# redir_hint:        redirection hint, whether to the first or to others
# dest_mode:         destination mode, physical or logical ID
# valid_mode:        validation mode in the VTd interrupt remapping mechanism
# sid_qualifier:     source-id qualifier, which bits in source-id to compare
# vtd_mode:          whether to test using vtd remap spec or not
def do_test(pci_bus_id, device_id, func_id,
            dest_cpu_id, vector,
            deliv_mode, trig_mode,
            redir_hint, dest_mode,
            valid_mode, sid_qualifier,
            vtd_mode
            ):
    if PRINT_DEBUG_INFO:
        print("PCI bus/device/function: %d/%d/%d" \
              % (pci_bus_id, device_id, func_id))
    tb.vtd_hw_drv.reset_vtd_hw()
    tb.reset_test_bench_status()

    (handle, sh_valid, subhandle) = gen_int_req_handle(
                                        pci_bus_id, device_id, func_id)
    this_sid = gen_source_id(pci_bus_id, device_id, func_id)

    if valid_mode == 0:
        valid_sid = 1 # No request-id verification is required
    elif valid_mode == 1:
        valid_sid = 1 # Comparing SID of request initiator and that in the IRTE
    elif valid_mode == 2: # Comparing bus number
        start_bus = this_sid >> 8
        end_bus   = this_sid & 0xFF
        if pci_bus_id >= start_bus and pci_bus_id <= end_bus:
            valid_sid = 1
        else:
            valid_sid = 0
    else:
        raise Exception("Unknown valid mode %d in a interrupt remapping "
                        "table entry" % valid_mode)

    this_index     = handle
    if sh_valid:
        this_index = handle + subhandle
    irte_cnt = this_index + 10

    if PRINT_DEBUG_INFO:
        print(("This interrupt index: %d, SID validation result: %s"
            % (this_index, ("refused", "passed")[valid_sid])))
    # Construct the interrupt remapping tables
    irte_size  = VTdConst.interrupt_entry_size
    irte_base  = tb.alloc_permanent_mem(irte_size * irte_cnt, VTdConst.page_size)
    irte_addr  = irte_base
    for i in range(irte_cnt):
        if i != this_index:
            val = VTdConst.irte_bf.value(P = 0)
        else:
            val = VTdConst.irte_bf.value(
                               SVT = valid_mode,
                               SQ  = sid_qualifier,
                               SID = this_sid,
                               DST = dest_cpu_id << 8,
                               V   = vector,
                               DLM = deliv_mode,
                               TM  = trig_mode,
                               RH  = redir_hint,
                               DM  = dest_mode,
                               P   = 1
                            )
        tb.mem_space_drv.write_value_le(irte_addr, irte_size, val)
        irte_addr += irte_size

    # Configure the hardware to use the interrupt remapping table
    if PRINT_DEBUG_INFO:
        print("irte_base", irte_base)
    tb.vtd_hw_drv.config_irt_addr(irte_base, irte_cnt)

    tb.vtd_hw_drv.enable_int_remapping(1)

    # Set interrupt remapping spec
    if vtd_mode:
        tb.vtd.use_vtd_interrupt_decoding = True
    else:
        tb.vtd.use_vtd_interrupt_decoding = False

    # Issue an interrupt request to the remapping hardware
    if vtd_mode:
        msg_addr = VTdConst.remappable_int_msg_addr_bf_vtd.value(
                        FEE = 0xFEE,
                        IH = handle & 0xEFFF,
                        IH2 = 1 if handle & 0x8000 else 0,
                        SHV = sh_valid,
                    )
    else:
        msg_addr = VTdConst.remappable_int_msg_addr_bf.value(
                        FEE = 0xFEE,
                        IH  = handle & 0xFFFF,
                        SHV = sh_valid,
                    )
    msg_data = VTdConst.remappable_int_msg_data_bf.value(
                        SH  = subhandle,
                    )
    tb.vtd_hw_drv.issue_int_message(pci_bus_id, device_id, func_id,
                                    msg_addr, msg_data)

    # Intercept the interrupt sent by the VTd hardware if it sends
    (vtd_destination, vtd_vector, vtd_tm, vtd_dm, vtd_dlm_mode) = \
        vtd_hw_drv.get_and_clear_int_data()
    int_intercepted = (0, 1)[vtd_vector != 0]

    if valid_sid:
        # Check the destination processor and interrupt vector
        stest.expect_equal(vtd_vector, vector, "interrupt vector")
        stest.expect_equal(vtd_destination, dest_id, "destination ID")
        stest.expect_equal(vtd_tm, trig_mode, "trigger mode")
        stest.expect_equal(vtd_dm, dest_mode, "destination mode")
        stest.expect_equal(vtd_dlm_mode, deliv_mode, "delivery mode")
    else:
        stest.expect_equal(int_intercepted, 0,
                           "no interrupt generated by VTd hardware")

for (pci_bus, device, func,
     dest_id, vector,
     deliv_mode, trig_mode,
     redir_hint, dest_mode,
     valid_mode, sid_qualifier,
     vtd_mode
     ) in (
        (pci_bus, device, func,
         dest_id, vector,
         deliv_mode, trig_mode,
         redir_hint, dest_mode,
         valid_mode, sid_qualifier,
         vtd_mode)
            for pci_bus in (0,)   # PCI bus number
            for device in ((VTdTestBench.vtd_dev_num + 1) % 32,)# Device number on the PCI bus
            for func in (0, )#7)      # Function number in the PCI device
            for dest_id in (0, 15)  # Destination processor ID
            for vector in (16, 255) # Interrupt vector
            for deliv_mode in (VTdConst.irte_dlm_fixed,
                               #VTdConst.irte_dlm_lowest_prior,
                               #VTdConst.irte_dlm_smi,
                               #VTdConst.irte_dlm_nmi,
                               #VTdConst.irte_dlm_init,
                               #VTdConst.irte_dlm_ext_int,
                              )
            for trig_mode in (VTdConst.irte_tm_edge,
                              #VTdConst.irte_tm_level,
                             )
            for redir_hint in (0, )#1)
            for dest_mode in (VTdConst.irte_dm_physical,
                              #VTdConst.irte_dm_logical,
                             )
            for valid_mode in (0, 1, 2)
            for sid_qualifier in (0, 1, 2, 3)
            for vtd_mode in (False, True)
        ):
    do_test(pci_bus, device, func,
            dest_id, vector,
            deliv_mode, trig_mode,
            redir_hint, dest_mode,
            valid_mode, sid_qualifier,
            vtd_mode)
