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


# s-vtd-inv-cache.py
# tests two interfaces of invalidating context, PDE, IOTLB, device-IOTLB,
# and interrupt entry caches

from vtd_tb import *

inv_if_reg      = 0 # Invalidate interface of register
inv_if_queue    = 1 # Invalidate interface of queue

cache_context   = VTdConst.inv_desc_context # Cache of context
cache_iotlb     = VTdConst.inv_desc_iotlb   # Cache of IOTLB
cache_ie        = VTdConst.inv_desc_int_entry # Cache of interrupt entry
cache_wait      = VTdConst.inv_desc_wait    # Wait

cache_supported = False

def test_inv_cache(inv_if, inv_cache):
    tb.vtd_hw_drv.reset_vtd_hw()
    tb.reset_test_bench_status()
    vtd_hw_drv.config_fault_event_int(
                    VTdConst.compat_int_msg_addr_bf.value(
                        FEE = 0xFEE, DID = vtd_dest_cpu),
                    VTdConst.compat_int_msg_data_bf.value(V = vtd_vector))
    vtd_hw_drv.enable_fault_event_int(1)

    if inv_if == inv_if_queue and not vtd_hw_drv.has_capability('QI'):
        return

    if ((not vtd_hw_drv.has_capability('QI'))
         and ((inv_cache == cache_ie) or (inv_cache == cache_wait))):
        if PRINT_DEBUG_INFO:
            print("The interrupt entry cache and invalidation wait only " \
                  "have the queue interface")
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
                   " hardware" % levels))
        return

    one_pci   = 0
    one_dev   = (VTdTestBench.vtd_dev_num + 1) % 32
    one_func  = 3
    this_sid  = gen_source_id(one_pci, one_dev, one_func)

    one_domain  = 0x66
    one_space   = 0x100000 # 1MB DOS space
    # Last 4KB bytes in guest space is mapped to a dynamic 4KB bytes in host memory
    one_addr    = one_space - VTdConst.page_size
    one_mapped  = tb.alloc_dynamic_mem(VTdConst.page_size)
    one_len     = VTdConst.page_size # Must be at least one page

    # Interrupt parameters
    one_vector   = 16
    one_dest_cpu = 3

    # Construct a page table for this guest space
    table_size = vtd_hw_drv.get_page_table_size(one_width, one_space)
    table_root = vtd_hw_drv.prepare_domain_page_table(
                    one_space, levels,
                    tb.alloc_permanent_mem(table_size, VTdConst.page_size),
                    table_size)
    # Map the guest address to a different host address
    vtd_hw_drv.map_guest_page_to_host(table_root, levels, one_addr, one_mapped)

    # Construct the context entry for this device
    ce_size = VTdConst.context_entry_size
    ce_cnt  = (one_dev + 1) * 8
    this_ce = one_dev * 8 + one_func
    ce_base = tb.alloc_permanent_mem(ce_size * ce_cnt, VTdConst.page_size)
    ce_addr = ce_base
    for ce in range(ce_cnt):
        if ce == this_ce:
            # Let the context entry of this device point to this page table
            ce_val = VTdConst.ce_bf.value(
                        DID = one_domain,
                        AW  = levels - 2,
                        ASR = table_root >> 12,
                        T   = 0,
                        P   = 1,
                    )
        else:
            ce_val = 0
        tb.mem_space_drv.write_value_le(ce_addr, ce_size, ce_val)
        ce_addr += ce_size

    # Construct the root entry for this PCI bus
    re_size = VTdConst.root_entry_size
    re_cnt  = one_pci + 1
    re_base = tb.alloc_permanent_mem(re_size * re_cnt, VTdConst.page_size)
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

    # Construct the interrupt remapping entry for this device
    (handle, sh_valid, subhandle) = gen_int_req_handle(
                                        one_pci, one_dev, one_func)
    this_index     = handle
    if sh_valid:
        this_index = handle + subhandle
    print("This interrupt index: ", this_index)
    irte_cnt = this_index + 1
    irte_size  = VTdConst.interrupt_entry_size
    irte_base  = tb.alloc_permanent_mem(irte_size * irte_cnt, VTdConst.page_size)
    irte_addr  = irte_base
    this_irte  = 0
    for irte in range(irte_cnt):
        if irte == this_index:
            val = VTdConst.irte_bf.value(
                               SVT = 0,
                               SQ  = 0,
                               SID = this_sid,
                               DST = one_dest_cpu << 8,
                               V   = one_vector,
                               DLM = VTdConst.irte_dlm_fixed,
                               TM  = VTdConst.irte_tm_edge,
                               RH  = 0,
                               DM  = VTdConst.irte_dm_physical,
                               P   = 1,
                            )
            this_irte = irte_addr
        else:
            val = 0
        tb.mem_space_drv.write_value_le(irte_addr, irte_size, val)
        irte_addr += irte_size

    # Configure the hardware to use the interrupt remapping table
    tb.vtd_hw_drv.config_irt_addr(irte_base, irte_cnt)

    # Enable the two remapping
    vtd_hw_drv.enable_dma_remapping(1)
    vtd_hw_drv.enable_int_remapping(1)

    if inv_cache == cache_context:
        for (rw, g) in ((rw, g)
                        for rw in (VTdHwDriver.dma_read,
                                   VTdHwDriver.dma_write)
                        for g in (VTdConst.inv_granularity_global,
                                  VTdConst.inv_granularity_domain,
                                  VTdConst.inv_granularity_device)
                        ):
            rw_len = 4
            rw_bytes = tuple(i & 0xFF for i in range(rw_len))
            if rw == VTdHwDriver.dma_read:
                mem_space_drv.write_mem(one_mapped, rw_bytes)

            # Do a remapping to fill an entry into the context cache
            real_bytes = vtd_hw_drv.issue_dma_remapping(
                one_pci, one_dev, one_func,
                one_addr, rw, rw_len, rw_bytes)
            if rw == VTdHwDriver.dma_read:
                stest.expect_equal(real_bytes, rw_bytes,
                    "bytes read in host memory address 0x%x" % one_mapped)
            else:
                real_bytes = mem_space_drv.read_mem(one_mapped, rw_len)
                stest.expect_equal(real_bytes, rw_bytes,
                    "bytes written into host memory address 0x%x"
                    % one_mapped)

            # Change the context entry in the memory stealthily
            new_mapped = one_mapped + one_len
            vtd_hw_drv.map_guest_page_to_host(table_root, levels,
                                              one_addr, new_mapped)
            new_rw = tuple((0xFF - i) & 0xFF for i in range(rw_len))
            if rw == VTdHwDriver.dma_read:
                mem_space_drv.write_mem(new_mapped, new_rw)

            # Remap the address again to use the context entry in the cache,
            # so the read is read into the address in the context cache
            # and the write is written into the address in the context cache
            new_real = vtd_hw_drv.issue_dma_remapping(
                one_pci, one_dev, one_func,
                one_addr, rw, rw_len, new_rw)
            if cache_supported:
                if rw == VTdHwDriver.dma_read:
                    stest.expect_equal(new_real, rw_bytes,
                        "bytes read in host memory address 0x%x" % one_mapped)
                else:
                    new_real = mem_space_drv.read_mem(one_mapped, rw_len)
                    stest.expect_equal(new_real, new_rw,
                        "bytes written into host memory address 0x%x"
                        % one_mapped)

            # Invalidate the cache
            vtd_hw_drv.inv_context_cache(g, one_domain, one_dev,
                                         (0, 1)[inv_if == inv_if_queue])

            # Now remap the address again will take effect of new page table
            if rw == VTdHwDriver.dma_read:
                new_real = vtd_hw_drv.issue_dma_remapping(
                    one_pci, one_dev, one_func,
                    one_addr, rw, rw_len, new_rw)
                stest.expect_equal(new_real, new_rw,
                    "bytes read in host memory address 0x%x" % new_mapped)
            else:
                new_real = mem_space_drv.read_mem(new_mapped, rw_len)
                stest.expect_equal(new_real, new_rw,
                    "bytes written into host memory address 0x%x"
                    % new_mapped)

            # Restore the original context entry and clear all caches
            vtd_hw_drv.map_guest_page_to_host(table_root,
                                              levels, one_addr, one_mapped)
            vtd_hw_drv.inv_context_cache(VTdConst.inv_granularity_global,
                                       (0, 1)[inv_if == inv_if_queue])

    elif inv_cache == cache_iotlb:
        for (rw, g) in ((rw, g)
                        for rw in (VTdHwDriver.dma_read,
                                   VTdHwDriver.dma_write)
                        for g in (VTdConst.inv_granularity_global,
                                  VTdConst.inv_granularity_domain,
                                  VTdConst.inv_granularity_page)
                        ):
            if (g == VTdConst.inv_granularity_page
                and not vtd_hw_drv.has_capability('PSI')):
                continue
            rw_len = 4
            rw_bytes = tuple(i & 0xFF for i in range(rw_len))
            if rw == VTdHwDriver.dma_read:
                mem_space_drv.write_mem(one_mapped, rw_bytes)

            # Do a remapping to fill an entry into the IOTLB cache
            real_bytes = vtd_hw_drv.issue_dma_remapping(
                            one_pci, one_dev, one_func,
                            one_addr, rw, rw_len, rw_bytes)
            if rw == VTdHwDriver.dma_read:
                stest.expect_equal(real_bytes, rw_bytes,
                    "bytes read in host memory address 0x%x" % one_mapped)
            else:
                real_bytes = mem_space_drv.read_mem(one_mapped, rw_len)
                stest.expect_equal(real_bytes, rw_bytes,
                    "bytes written into host memory address 0x%x"
                    % one_mapped)

            # Change the memory content stealthily
            new_rw = tuple((0xFF - i) & 0xFF for i in range(rw_len))
            if rw == VTdHwDriver.dma_read:
                mem_space_drv.write_mem(one_mapped, new_rw)

            # Remap the address again to use the data in the IOTLB cache,
            # so the read is read into the old value
            # and the write is written into the cache, not the host memory
            new_real = vtd_hw_drv.issue_dma_remapping(
                one_pci, one_dev, one_func,
                one_addr, rw, rw_len, new_rw)
            if cache_supported:
                if rw == VTdHwDriver.dma_read:
                    stest.expect_equal(new_real, rw_bytes,
                        "bytes read from cache of host memory address 0x%x"
                        % one_addr)
                else:
                    new_real = mem_space_drv.read_mem(one_mapped, rw_len)
                    stest.expect_equal(new_real, rw_bytes,
                        "bytes read from host memory address 0x%x"
                        "after a write to cache" % one_addr)

            # Invalidate the cache
            vtd_hw_drv.inv_iotlb_cache(g, one_domain, one_addr,
                                       (0, 1)[inv_if == inv_if_queue])

            # Now remap the address again will take effect of new read/write
            if rw == VTdHwDriver.dma_read:
                new_real = vtd_hw_drv.issue_dma_remapping(
                    one_pci, one_dev, one_func,
                    one_addr, rw, rw_len, new_rw)
                stest.expect_equal(new_real, new_rw,
                    "actual bytes read in host memory address 0x%x"
                    % one_addr)
            else:
                new_real = mem_space_drv.read_mem(one_mapped, rw_len)
                stest.expect_equal(new_real, new_rw,
                    "bytes written into host memory address 0x%x"
                    % one_addr)

            # Restore the original context entry and clear all caches
            vtd_hw_drv.inv_iotlb_cache(VTdConst.inv_granularity_global,
                                       (0, 1)[inv_if == inv_if_queue])

    elif inv_cache == cache_ie:
        for globally in (0, 1):
            # Issue an interrupt request to the remapping hardware
            msg_addr = VTdConst.remappable_int_msg_addr_bf.value(
                                FEE = 0xFEE,
                                IH  = handle & 0xFFFF,
                                SHV = sh_valid,
                            )
            msg_data = VTdConst.remappable_int_msg_data_bf.value(
                                SH  = subhandle,
                            )
            vtd_hw_drv.issue_int_message(one_pci, one_dev, one_func,
                                         msg_addr, msg_data)

            # Verify the interrupt vector and destination cpu
            (real_cpu, real_vector, tm, dm, dlm) = \
                vtd_hw_drv.get_and_clear_int_data()
            stest.expect_equal(real_vector, one_vector, "interrupt vector")
            stest.expect_equal(real_cpu, one_dest_cpu, "destination cpu")

            # Change the interrupt remapping entry of this device
            new_vector = one_vector + 1
            new_cpu    = one_dest_cpu + 1
            old_val = mem_space_drv.read_value_le(this_irte, irte_size)
            new_val = VTdConst.irte_bf.value(
                                   SVT = 0,
                                   SQ  = 0,
                                   SID = this_sid,
                                   DST = new_cpu << 8,
                                   V   = new_vector,
                                   DLM = VTdConst.irte_dlm_fixed,
                                   TM  = VTdConst.irte_tm_edge,
                                   RH  = 0,
                                   DM  = VTdConst.irte_dm_physical,
                                   P   = 1,
                                )
            mem_space_drv.write_value_le(this_irte, irte_size, new_val)

            vtd_hw_drv.issue_int_message(one_pci, one_dev, one_func,
                                         msg_addr, msg_data)

            # Verify the interrupt vector and destination cpu are still old ones
            if cache_supported:
                (real_cpu, real_vector, tm, dm, dlm) = \
                    vtd_hw_drv.get_and_clear_int_data()
                stest.expect_equal(real_vector, one_vector, "interrupt vector")
                stest.expect_equal(real_cpu, one_dest_cpu, "destination cpu")

            vtd_hw_drv.inv_int_entry_cache(globally, this_index)

            vtd_hw_drv.issue_int_message(one_pci, one_dev, one_func,
                                         msg_addr, msg_data)

            # Verify the interrupt vector and destination cpu become new ones
            (real_cpu, real_vector, tm, dm, dlm) = \
                vtd_hw_drv.get_and_clear_int_data()
            stest.expect_equal(
                real_vector, new_vector, "new interrupt vector")
            stest.expect_equal(real_cpu, new_cpu, "new destination cpu")

            # Restore the old IRTE value
            vtd_hw_drv.inv_int_entry_cache(1)
            mem_space_drv.write_value_le(this_irte, irte_size, old_val)

    elif inv_cache == cache_wait:
        inv_cc_val = VTdConst.cc_inv_desc_bf.value(
                        FM   = 0,
                        SID  = this_sid,
                        DID  = one_domain,
                        G    = 0,
                        T    = VTdConst.inv_desc_context,
                    )
        vtd_hw_drv.wait_inv_desc_list_done([inv_cc_val])

        (real_cpu, real_vector, tm, dm, dlm) = \
            vtd_hw_drv.get_and_clear_int_data()
        stest.expect_equal(real_cpu, vtd_dest_cpu,
               "destination cpu of interrupts from VTd hardware")

qsize = 0x100 # 256 descriptors is enough
qbase = tb.alloc_permanent_mem(qsize * VTdConst.inv_descriptor_size)
vtd_hw_drv.config_inv_queue(qbase, qsize)

vtd_dest_cpu = 0
vtd_vector   = 0x28

for (inv_if, inv_cache) in (
        (inv_if, inv_cache)
            for inv_if in (inv_if_reg, inv_if_queue)
            for inv_cache in (#cache_context, cache_iotlb,
                              cache_ie,)#, cache_wait)
        ):
    test_inv_cache(inv_if, inv_cache)
