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


# s-vtd-remap-dma.py

from vtd_tb import *

# pci_bus_cnt:       PCI bus count in the root complex
# device_cnt:        device count in every PCI bus, assuming ID be from 0 to cnt - 1
# domain_cnt:        domain count of running guest software
# guest_addr_width:  guest address width
def do_test(pci_bus_cnt, device_cnt, domain_cnt, guest_addr_width, is_super):
    if is_super and not vtd_hw_drv.has_capability("SPS"):
        return
    tb.vtd_hw_drv.reset_vtd_hw()
    tb.reset_test_bench_status()
    levels = tb.vtd_hw_drv.get_page_table_levels(guest_addr_width)
    supported_levels = vtd_hw_drv.supported_page_table_levels()
    if not (levels in supported_levels):
        if PRINT_DEBUG_INFO:
            print(("level %d page table is not supported by this"
                   " hardware" % levels))
        return
    space_size = 0x100000 # 1MB space for the guest
    guest_addr = 0x10000
    page_size  = VTdConst.page_size
    super_page_size = 0x10000 # 64KB
    if is_super:
        host_addr  = tb.alloc_dynamic_mem(super_page_size)
        rw_len     = super_page_size
        rw_bytes   = tuple([i & 0xFF for i in range(rw_len)])
    else:
        host_addr  = tb.alloc_dynamic_mem(page_size)
        rw_len     = page_size
        rw_bytes   = tuple([i & 0xFF for i in range(rw_len)])
    # Construct the page tables
    did_list = [0x00 for i in range(domain_cnt)]
    asr_list = [0x00 for i in range(domain_cnt)] # ASR -- Address Space Root
    for i in range(domain_cnt):
        # Prepare a page table for each domain
        table_size = tb.vtd_hw_drv.get_page_table_size(
                            guest_addr_width, space_size)
        base = tb.alloc_permanent_mem(table_size, page_size)
        table_root = tb.vtd_hw_drv.prepare_domain_page_table(
                            space_size, levels, base, table_size)
        # Map the predefined guest address to dynamic host address
        if is_super:
            tb.vtd_hw_drv.map_guest_page_to_host(
                        table_root, levels - 1, guest_addr, host_addr, 1)
        else:
            tb.vtd_hw_drv.map_guest_page_to_host(
                        table_root, levels, guest_addr, host_addr, 0)
        did_list[i] = i
        asr_list[i] = table_root

    source_id_list = []
    for b in range(pci_bus_cnt):
        for d in range(device_cnt):
            if d == VTdTestBench.vtd_dev_num:
                continue
            source_id_list.append((b, d, 0))
    for (bus, dev, func) in source_id_list:
        if PRINT_DEBUG_INFO:
            print("bus/dev/func: %d/%d/%d" % (bus, dev, func))
        tb.vtd_hw_drv.reset_vtd_hw()
        # Construct the context entries of each device
        ce_size = VTdConst.context_entry_size
        ce_base = tb.alloc_permanent_mem(ce_size * device_cnt, page_size)
        ce_addr = ce_base
        for v in range(device_cnt):
            if v != dev:
                ce_val = 0
            else:
                ce_val = VTdConst.ce_bf.value(
                        DID = did_list[v % domain_cnt],
                        AW  = levels - 2,
                        ASR = asr_list[v % domain_cnt] >> 12,
                        T   = 0,
                        P   = 1)
            tb.mem_space_drv.write_value_le(ce_addr, ce_size, ce_val)
            # Every device occupy 8 entries for it can has 8 functions
            if PRINT_DEBUG_INFO:
                print("CE addr: 0x%x, value: 0x%x" % (ce_addr, ce_val))
            ce_addr += (ce_size << 3)
        if PRINT_DEBUG_INFO:
            print("CE base: 0x%x" % ce_base)

        # Construct the root entries
        re_size = VTdConst.root_entry_size
        re_base = tb.alloc_permanent_mem(re_size * pci_bus_cnt, page_size)
        re_addr = re_base
        for b in range(pci_bus_cnt):
            if b != bus:
                val = 0
            else:
                val = VTdConst.re_bf.value(
                            CTP = ce_base >> 12,
                            P   = 1)
            tb.mem_space_drv.write_value_le(re_addr, re_size, val)
            if PRINT_DEBUG_INFO:
                print("RE addr: 0x%x, value: 0x%x" % (re_addr, val))
            re_addr += re_size
        if PRINT_DEBUG_INFO:
            print("RE base: 0x%x" % re_base)

        # Configure the remapping hardware to use above tables
        tb.vtd_hw_drv.config_rt_addr(re_base)

        tb.vtd_hw_drv.enable_dma_remapping(1)

        # Issue a write DMA request to the remapping hardware
        vtd_hw_drv.issue_dma_remapping(
            bus, dev, func,
            guest_addr, VTdHwDriver.dma_write,
            rw_len, rw_bytes)

        # Check the wrote address
        real_bytes = mem_space_drv.read_mem(host_addr, rw_len)
        stest.expect_equal(real_bytes, rw_bytes,
            "wrote bytes to guest address 0x%x (host address 0x%x)"
            % (guest_addr, host_addr))

        # Issue a read DMA request to the remapping hardware
        read_bytes = vtd_hw_drv.issue_dma_remapping(
            bus, dev, func,
            guest_addr, VTdHwDriver.dma_read, rw_len)

        # Check the read is same as the write
        stest.expect_equal(read_bytes, rw_bytes,
            "read bytes from guest address 0x%x (host address 0x%x)"
            % (guest_addr, host_addr))

supported_pci_cnt = (1,)
supported_widths = vtd_hw_drv.supported_guest_address_widths()

for (pci, device, domain, guest, is_super) in (
        (pci, device, domain, guest, is_super)
            for pci in supported_pci_cnt
            for device in (3,)
            for domain in (3,)
            for guest in supported_widths
            for is_super in (0, 1)):
    do_test(pci, device, domain, guest, is_super)
