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


# s-vtd-switch-domain.py
# tests the switch of several domains in the Intel (r) VT-d hardware

from vtd_tb import *

magic_text = "that government of the people, by the people, for the people"

# domain_cnt    -- domain count
# domain_id     -- list of identifier of all domains
# domain_gaw    -- list of guest address width of all domains
# domain_space  -- list of memory space size of all domains
# guest_addr    -- memory address in the guest software to be used in mapping
# device_cnt    -- count of physical I/O devices to issue the DMA request
def do_test(domain_cnt, domain_id, domain_gaw, domain_space,
            guest_addr = 0x00, device_cnt = 2):
    tb.vtd_hw_drv.reset_vtd_hw()
    tb.reset_test_bench_status()

    page_size = VTdConst._page_size

    # Prepare several domains in the memory
    # with every domain has its special remapping
    asr_list     = [0x00 for d in range(domain_cnt)]
    context_root = [0x00 for d in range(domain_cnt)]
    host_addr    = [0x00 for d in range(domain_cnt)]
    magic_str    = [0x00 for d in range(domain_cnt)]
    for d in range(domain_cnt):
        width = domain_gaw[d]
        space = domain_space[d]
        levels = tb.vtd_hw_drv.get_page_table_levels(width)
        supported_levels = vtd_hw_drv.supported_page_table_levels()
        if not (levels in supported_levels):
            if PRINT_DEBUG_INFO:
                print(("level %d page table is not supported by this"
                       " Intel (r) VT-d" % levels))
            return
        table_size = tb.vtd_hw_drv.get_page_table_size(width, space)
        base = tb.alloc_permanent_mem(table_size, VTdConst._page_size)
        table_root = tb.vtd_hw_drv.prepare_domain_page_table(
                        space, levels, base, table_size)

        host_addr[d] = tb.alloc_dynamic_mem(page_size)
        tb.vtd_hw_drv.map_guest_page_to_host(
                        table_root, levels, guest_addr, host_addr[d])
        if PRINT_DEBUG_INFO:
            print("Address 0x%x in domain %d is mapped to host address 0x%x" \
                  % (guest_addr, d, host_addr[d]))
        asr_list[d] = table_root

        # Fill respective magic codes in the host page assigned to one domain
        magic_str[d] = tuple(map(ord, magic_text[d * 4 : d * 4 + 4]))
        tb.mem_space_drv.write_mem(host_addr[d], magic_str[d])

        # Construct the context entries for I/O devices assigned to this domain
        ce_size = VTdConst._context_entry_size
        ce_base = tb.alloc_permanent_mem(ce_size * device_cnt, VTdConst._page_size)
        ce_addr = ce_base
        for v in range(device_cnt):
            if v == VTdTestBench._vtd_dev_num:
                ce_val = 0
            else:
                ce_val = VTdConst.ce_bf.value(
                            DID = domain_id[d],
                            AW = levels - 2,
                            ASR = asr_list[d] >> 12,
                            ALH = 0,
                            EH  = 0,
                            T = 0,
                            FPD = 0,
                            P = 1,
                        )
            tb.mem_space_drv.write_value_le(ce_addr, ce_size, ce_val)
            ce_addr += ce_size * 8
        context_root[d] = ce_base

    # Construct the common root table for all domains
    re_size = VTdConst._root_entry_size
    re_addr = tb.alloc_permanent_mem(re_size, VTdConst._page_size)
    re_val = VTdConst.re_bf.value(
                       CTP = 0,
                       P = 0
                    )
    tb.mem_space_drv.write_value_le(re_addr, re_size, re_val)

    # Switch on these domains one by one
    vtd_hw_drv.config_rt_addr(re_addr)
    vtd_hw_drv.enable_dma_remapping(1)
    for d in range(domain_cnt):
        tb.vtd_hw_drv.switch_domain(context_root[d])
        for v in range(device_cnt):
            if v == VTdTestBench._vtd_dev_num:
                continue
            read_bytes = vtd_hw_drv.issue_dma_remapping(0, v, 0,
                guest_addr, VTdHwDriver._dma_read, 4)
            stest.expect_equal(read_bytes, magic_str[d],
                        "magic string of domain %d" % d)

    for d in range(domain_cnt - 2, -1, -1):
        tb.vtd_hw_drv.switch_domain(context_root[d])
        for v in range(device_cnt):
            if v == VTdTestBench._vtd_dev_num:
                continue
            read_bytes = vtd_hw_drv.issue_dma_remapping(0, v, 0,
                guest_addr, VTdHwDriver._dma_read, 4)
            stest.expect_equal(read_bytes, magic_str[d],
                        "magic string of domain %d" % d)

do_test(3, list(map(ord, ['a', 'b', 'c'])),
        [48, 48, 48], [0x100000, 0x1000000, 0x10000000])
