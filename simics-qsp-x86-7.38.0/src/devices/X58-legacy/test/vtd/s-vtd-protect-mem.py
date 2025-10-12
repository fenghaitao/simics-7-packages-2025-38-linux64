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


# s-vtd-protect-mem.py
# tests memory region DMA-protecting in the Intel (r) VT-d hardware

from vtd_tb import *

request_type_untranslated   = 1
request_type_translated     = 2

translation_type_only_untranslated  = 0
translation_type_all                = 1
translation_type_pass_through       = 2

low_base = VTdTestBench._main_mem_base + VTdTestBench._main_mem_length // 8
low_len  = 0x1000000
high_len = low_len
high_base= VTdTestBench._main_mem_base + VTdTestBench._main_mem_length - high_len

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

def do_test(low_base, low_len, high_base, high_len,
            enable_dma_remapping,
            request_type = request_type_untranslated,
            trans_type = translation_type_only_untranslated):
    vtd_hw_drv.reset_vtd_hw()
    tb.reset_test_bench_status()
    vtd_hw_drv.config_protected_memory(low_base, low_len, high_base, high_len)
    vtd_hw_drv.enable_protected_memory(1)
    vtd_hw_drv.config_fault_event_int(one_msg_addr, one_msg_data)
    vtd_hw_drv.enable_fault_event_int(1)
    vtd_hw_drv.enable_dma_remapping(enable_dma_remapping)

    if (trans_type == translation_type_pass_through
        and (not vtd_hw_drv.has_capability('PT'))):
        return

    supported_widths = vtd_hw_drv.supported_guest_address_widths()
    if supported_widths == []:
        one_width = 39
    else:
        one_width = supported_widths[0]
    levels    = vtd_hw_drv.get_page_table_levels(one_width)
    supported_levels = vtd_hw_drv.supported_page_table_levels()
    if not (levels in supported_levels):
        if PRINT_DEBUG_INFO:
            print(("level %d page table is not supported by this"
                   " Intel (r) VT-d" % levels))
        return

    one_pci   = 0
    one_dev   = (VTdTestBench._vtd_dev_num + 1) % 32
    one_func  = 3

    one_domain  = 0x66
    # Last 4KB bytes in guest space is mapped to a dynamic 4KB bytes in host memory
    one_space   = low_len + high_len
    low_addr    = 0
    high_addr   = low_len
    low_mapped  = low_base
    high_mapped = high_base

    # Construct  page table for this guest space
    table_size = vtd_hw_drv.get_page_table_size(one_width, one_space)
    table_root = vtd_hw_drv.prepare_domain_page_table(
                    one_space, levels,
                    tb.alloc_permanent_mem(table_size, VTdConst._page_size),
                    table_size)
    # Map the low and high guest addresses to the low and high base in host mem
    vtd_hw_drv.map_guest_page_to_host(table_root, levels, low_addr, low_mapped)
    vtd_hw_drv.map_guest_page_to_host(table_root, levels,
                                      high_addr, high_mapped)

    # Construct the context entry for this device
    ce_size = VTdConst._context_entry_size
    ce_cnt  = (one_dev + 1) * 8
    this_ce = one_dev * 8 + one_func
    ce_base = tb.alloc_permanent_mem(ce_size * ce_cnt, VTdConst._page_size)
    ce_addr = ce_base
    for ce in range(ce_cnt):
        if ce == this_ce:
            # Let the context entry of this device point to this page table
            ce_val = VTdConst.ce_bf.value(
                        DID = one_domain,
                        AW  = levels - 2,
                        ASR = table_root >> 12,
                        T   = trans_type,
                        P   = 1,
                    )
        else:
            ce_val = 0
        tb.mem_space_drv.write_value_le(ce_addr, ce_size, ce_val)
        ce_addr += ce_size

    # Construct the root entry for this PCI bus
    re_size = VTdConst._root_entry_size
    re_cnt  = one_pci + 1
    re_base = tb.alloc_permanent_mem(re_size * re_cnt, VTdConst._page_size)
    re_addr = re_base
    for re in range(re_cnt):
        if re == one_pci:
            val = VTdConst.re_bf.value(
                        CTP = ce_base >> 12,
                        P   = 1,
                    )
        else:
            val = 0
        tb.mem_space_drv.write_value_le(re_addr, re_size, val)
        re_addr += re_size

    vtd_hw_drv.config_rt_addr(re_base)

    # Issue a DMA request to the address in low protected region
    if vtd_hw_drv.has_capability('PLMR'):
        read_addr = low_addr
        if (enable_dma_remapping == 0
            or trans_type == translation_type_pass_through):
            read_addr = low_mapped
        real_bytes = vtd_hw_drv.issue_dma_remapping(
            one_pci, one_dev, one_func,
            read_addr, VTdHwDriver._dma_read, 4)
        if (enable_dma_remapping == 0
            or trans_type == translation_type_pass_through):
            # Check the request is blocked
            stest.expect_equal(real_bytes, (), "no data read from low region")

    # Issue a DMA request to the address in high protected region
    if vtd_hw_drv.has_capability('PHMR'):
        read_addr = high_addr
        if (enable_dma_remapping == 0
            or trans_type == translation_type_pass_through):
            read_addr = high_mapped
        real_bytes = vtd_hw_drv.issue_dma_remapping(
            one_pci, one_dev, one_func,
            read_addr, VTdHwDriver._dma_read, 4)
        if (enable_dma_remapping == 0
            or trans_type == translation_type_pass_through):
            # Check the request is blocked
            stest.expect_equal(real_bytes, (), "no data read from high region")

do_test(low_base, low_len, high_base, high_len, 0)
do_test(low_base, low_len, high_base, high_len, 1,
        request_type_untranslated, translation_type_only_untranslated)
do_test(low_base, low_len, high_base, high_len, 1,
        request_type_untranslated, translation_type_pass_through)
