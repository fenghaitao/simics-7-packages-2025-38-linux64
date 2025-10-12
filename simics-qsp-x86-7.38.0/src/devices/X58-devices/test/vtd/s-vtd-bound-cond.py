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


from vtd_tb import (VTdConst, tb, vtd_hw_drv, mem_space_drv,
                    gen_source_id, gen_int_req_handle)
import stest

frcd_cnt = VTdConst.cap_bf.fields(vtd_hw_drv.read_reg('CAP'))['NFR'] + 1
ce_size = VTdConst.context_entry_size
pte_size = VTdConst.pte_size


def test_pass_through(bus_id, dev_id, func_id,
                      guest_base, mapped_base, ce_base):
    vtd_hw_drv.enable_dma_remapping(1)
    this_ce = dev_id * 8 + func_id
    test_off = 0x88
    test_byte = 0x86
    mem_space_drv.write_mem(mapped_base + test_off, (test_byte,))
    read_byte = vtd_hw_drv.issue_dma_remapping(
        bus_id, dev_id, func_id, guest_base + test_off, vtd_hw_drv.dma_read, 1)
    stest.expect_equal(
        read_byte, (test_byte,),
        "read byte from mapped host address 0x%x of guest address 0x%x"
        % (mapped_base + test_off, guest_base + test_off))

    # Pass through a DMA transaction request in context entry
    ce_addr = ce_base + ce_size * this_ce
    old_ce_val = mem_space_drv.read_value_le(ce_addr, ce_size)
    fields = VTdConst.ce_bf.fields(old_ce_val)
    fields['T'] = 2
    new_ce_val = VTdConst.ce_bf.value_ex(fields)
    mem_space_drv.write_value_le(ce_addr, ce_size, new_ce_val)
    mem_space_drv.write_mem(guest_base + test_off, (test_byte + 1,))
    read_byte = vtd_hw_drv.issue_dma_remapping(
        bus_id, dev_id, func_id,
        guest_base + test_off, vtd_hw_drv.dma_read, 1)
    stest.expect_equal(
        read_byte, (test_byte + 1,),
        "read byte from pass-through guest address 0x%x"
        % (guest_base + test_off))

    mem_space_drv.write_value_le(ce_addr, ce_size, old_ce_val)
    read_byte = vtd_hw_drv.issue_dma_remapping(
        bus_id, dev_id, func_id, guest_base + test_off, vtd_hw_drv.dma_read, 1)
    stest.expect_equal(
        read_byte, (test_byte,),
        "read byte from mapped host address 0x%x of guest address 0x%x"
        % (mapped_base + test_off, guest_base + test_off))


def test_disabled_dma_remapping(bus_id, dev_id, func_id,
                                guest_base, mapped_base, ce_base):
    vtd_hw_drv.enable_dma_remapping(1)
    test_off = 0x88
    test_byte = 0x86
    mem_space_drv.write_mem(mapped_base + test_off, (test_byte,))
    read_byte = vtd_hw_drv.issue_dma_remapping(
        bus_id, dev_id, func_id, guest_base + test_off, vtd_hw_drv.dma_read, 1)
    stest.expect_equal(
        read_byte, (test_byte,),
        "read byte from mapped host address 0x%x of guest address 0x%x"
        % (mapped_base + test_off, guest_base + test_off))

    # Request a DMA remapping when it is disabled
    vtd_hw_drv.enable_dma_remapping(0)
    mem_space_drv.write_mem(guest_base + test_off, (test_byte + 1,))
    read_byte = vtd_hw_drv.issue_dma_remapping(
        bus_id, dev_id, func_id, guest_base + test_off, vtd_hw_drv.dma_read, 1)
    stest.expect_equal(
        read_byte, (test_byte + 1,),
        "read byte from pass-through guest address 0x%x"
        % (guest_base + test_off))


def test_disabled_int_remapping(bus_id, dev_id, func_id, int_vec, int_dest):
    vtd_hw_drv.enable_int_remapping(1)
    (handle, sh_valid, subhandle) = gen_int_req_handle(bus_id, dev_id, func_id)
    msg_addr = VTdConst.remappable_int_msg_addr_bf.value(FEE=0xFEE,
                                                         IH=handle & 0xFFFF,
                                                         SHV=sh_valid)
    msg_data = VTdConst.remappable_int_msg_data_bf.value(SH=subhandle)
    vtd_hw_drv.issue_int_message(bus_id, dev_id, func_id, msg_addr, msg_data)
    # Intercept the interrupt sent by the VTd hardware if it sends
    (vtd_destination, vtd_vector, vtd_tm, vtd_dm, vtd_dlm_mode) = \
        vtd_hw_drv.get_and_clear_int_data()
    stest.expect_equal(vtd_vector, int_vec, "interrupt vector")
    stest.expect_equal(vtd_destination, int_dest, "destination ID")

    # Request an interrupt remapping when it is disabled
    vtd_hw_drv.enable_int_remapping(0)
    # Now the interrupt request is sent directly as a normal
    # compatible request
    msg_addr = VTdConst.compat_int_msg_addr_bf.value(FEE=0xFEE,
                                                     DID=int_dest)
    msg_data = VTdConst.compat_int_msg_data_bf.value(V=int_vec)
    vtd_hw_drv.issue_int_message(bus_id, dev_id, func_id, msg_addr, msg_data)
    (vtd_destination, vtd_vector, vtd_tm, vtd_dm, vtd_dlm_mode) = \
        vtd_hw_drv.get_and_clear_int_data()
    stest.expect_equal(vtd_vector, int_vec, "interrupt vector")
    stest.expect_equal(vtd_destination, int_dest, "destination ID")


def test_no_present_ce_fault(bus_id, dev_id, func_id, ce_base):
    # Context entry not present fault
    this_ce = dev_id * 8 + func_id
    ce_size = VTdConst.context_entry_size
    ce_addr = ce_base + ce_size * this_ce
    old_ce_val = mem_space_drv.read_value_le(ce_addr, ce_size)
    fields = VTdConst.ce_bf.fields(old_ce_val)
    fields['P'] = 0
    new_ce_val = VTdConst.ce_bf.value_ex(fields)
    mem_space_drv.write_value_le(ce_addr, ce_size, new_ce_val)

    frr_idx = get_next_frr()

    vtd_hw_drv.enable_dma_remapping(1)
    vtd_hw_drv.issue_dma_remapping(bus_id, dev_id, func_id, 0, rw_len=1)

    val = vtd_hw_drv.read_reg("FRCD%d" % frr_idx)
    fields = VTdConst.frcd_bf.fields(val)
    stest.expect_equal(fields['F'], 1, "fault should be present")
    stest.expect_equal(fields['FR'],
                       VTdConst.fr_no_present_context_entry, "fault reason")

    # Restore the context entry table
    mem_space_drv.write_value_le(ce_addr, ce_size, old_ce_val)


def test_unsupported_level_fault(bus_id, dev_id, func_id, ce_base):
    this_ce = dev_id * 8 + func_id
    ce_addr = ce_base + ce_size * this_ce
    old_ce_val = mem_space_drv.read_value_le(ce_addr, ce_size)
    fields = VTdConst.ce_bf.fields(old_ce_val)
    fields['AW'] = fields['AW'] + 1
    new_ce_val = VTdConst.ce_bf.value_ex(fields)
    mem_space_drv.write_value_le(ce_addr, ce_size, new_ce_val)

    frr_idx = get_next_frr()
    vtd_hw_drv.enable_dma_remapping(1)
    vtd_hw_drv.issue_dma_remapping(bus_id, dev_id, func_id, 0, rw_len=1)

    val = vtd_hw_drv.read_reg("FRCD%d" % frr_idx)
    fields = VTdConst.frcd_bf.fields(val)
    stest.expect_equal(fields['F'], 1, "fault present")
    stest.expect_equal(fields['FR'],
                       VTdConst.fr_invalid_context_entry, "fault reason")

    # Restore the context entry table
    mem_space_drv.write_value_le(ce_addr, ce_size, old_ce_val)


def test_protected_read_write_fault(bus_id, dev_id, func_id,
                                    guest_base, mapped_base, ce_base):
    this_ce = dev_id * 8 + func_id
    ce_addr = ce_base + ce_size * this_ce
    ce_val = mem_space_drv.read_value_le(ce_addr, ce_size)
    fields = VTdConst.ce_bf.fields(ce_val)
    pte_addr = fields['ASR'] << 12
    pte_val = mem_space_drv.read_value_le(pte_addr, pte_size)
    pte_fields = VTdConst.pte_bf.fields(pte_val)

    pte_fields['R'] = 0
    mem_space_drv.write_value_le(pte_addr, pte_size,
                                 VTdConst.pte_bf.value_ex(pte_fields))

    frr_idx = get_next_frr()
    vtd_hw_drv.enable_dma_remapping(1)
    read_bytes = vtd_hw_drv.issue_dma_remapping(
        bus_id, dev_id, func_id, guest_base, rw_len=1)
    stest.expect_equal(read_bytes, (), "no bytes read")
    val = vtd_hw_drv.read_reg("FRCD%d" % frr_idx)
    fields = VTdConst.frcd_bf.fields(val)
    stest.expect_equal(fields['F'], 1, "fault present")
    stest.expect_equal(fields['FR'],
                       VTdConst.fr_read_a_not_read_pte, "fault reason")

    pte_fields['W'] = 0
    mem_space_drv.write_value_le(pte_addr, pte_size,
                                 VTdConst.pte_bf.value_ex(pte_fields))
    frr_idx = get_next_frr()
    vtd_hw_drv.issue_dma_remapping(
        bus_id, dev_id, func_id, guest_base, vtd_hw_drv.dma_write, 1, (1,))
    val = vtd_hw_drv.read_reg("FRCD%d" % frr_idx)
    fields = VTdConst.frcd_bf.fields(val)
    stest.expect_equal(fields['F'], 1, "fault present")
    stest.expect_equal(fields['FR'],
                       VTdConst.fr_write_a_read_pte, "fault reason")

    # Restore previous page table entry
    pte_fields['R'] = 1
    pte_fields['W'] = 1
    pte_val = VTdConst.pte_bf.value_ex(pte_fields)
    mem_space_drv.write_value_le(pte_addr, pte_size, pte_val)


def do_test():
    vtd_hw_drv.reset_vtd_hw()
    tb.reset_test_bench_status()

    supported_widths = vtd_hw_drv.supported_guest_address_widths()
    if supported_widths == []:
        one_width = 39
    else:
        one_width = supported_widths[0]
    levels = vtd_hw_drv.get_page_table_levels(one_width)
    supported_levels = vtd_hw_drv.supported_page_table_levels()
    stest.expect_true(levels in supported_levels,
                      "level %d page table is not supported by this"
                      " hardware" % levels)
    bus = 0
    dev = (tb.vtd_dev_num + 1) % 32
    func = 3
    this_sid = gen_source_id(bus, dev, func)

    one_domain = 0x66
    one_space = 0x100000  # 1MB DOS space
    # Last 4KB bytes in guest space is mapped to a dynamic
    # 4KB bytes in host memory
    one_addr = one_space - VTdConst.page_size
    one_mapped = tb.alloc_dynamic_mem(VTdConst.page_size)

    # Interrupt parameters
    one_vector = 16
    one_dest_cpu = 3

    # Construct a page table for this guest space
    table_size = vtd_hw_drv.get_page_table_size(one_width, one_space)
    table_root = vtd_hw_drv.prepare_domain_page_table(
        one_space, levels,
        tb.alloc_permanent_mem(table_size, VTdConst.page_size), table_size)
    # Map the guest address to a different host address
    vtd_hw_drv.map_guest_page_to_host(table_root, levels, one_addr, one_mapped)

    # Construct the context entry for this device
    ce_size = VTdConst.context_entry_size
    ce_cnt = (dev + 1) * 8
    this_ce = dev * 8 + func
    ce_base = tb.alloc_permanent_mem(ce_size * ce_cnt, VTdConst.page_size)
    ce_addr = ce_base
    for ce in range(ce_cnt):
        if ce == this_ce:
            # Let the context entry of this device point to this page table
            ce_val = VTdConst.ce_bf.value(DID=one_domain,
                                          AW=levels - 2,
                                          ASR=table_root >> 12,
                                          T=0, P=1)
        else:
            ce_val = 0
        tb.mem_space_drv.write_value_le(ce_addr, ce_size, ce_val)
        ce_addr += ce_size

    # Construct the root entry for this PCI bus
    re_size = VTdConst.root_entry_size
    re_cnt = bus + 1
    re_base = tb.alloc_permanent_mem(re_size * re_cnt, VTdConst.page_size)
    re_addr = re_base
    for re in range(re_cnt):
        if re == bus:
            val = VTdConst.re_bf.value(CTP=ce_base >> 12, P=1)
        else:
            val = 0
        tb.mem_space_drv.write_value_le(re_addr, re_size, val)
        re_addr += re_size

    vtd_hw_drv.config_rt_addr(re_base)

    # Construct the interrupt remapping entry for this device
    (handle, sh_valid, subhandle) = \
        gen_int_req_handle(bus, dev, func)
    this_index = handle
    if sh_valid:
        this_index = handle + subhandle
    irte_cnt = this_index + 1
    irte_size = VTdConst.interrupt_entry_size
    irte_base = tb.alloc_permanent_mem(irte_size * irte_cnt,
                                       VTdConst.page_size)
    irte_addr = irte_base
    for irte in range(irte_cnt):
        if irte == this_index:
            val = VTdConst.irte_bf.value(SVT=0, SQ=0, SID=this_sid,
                                         DST=one_dest_cpu << 8,
                                         V=one_vector,
                                         DLM=VTdConst.irte_dlm_fixed,
                                         TM=VTdConst.irte_tm_edge,
                                         DM=VTdConst.irte_dm_physical,
                                         RH=0, P=1)
        else:
            val = 0
        tb.mem_space_drv.write_value_le(irte_addr, irte_size, val)
        irte_addr += irte_size

    # Configure the hardware to use the interrupt remapping table
    tb.vtd_hw_drv.config_irt_addr(irte_base, irte_cnt)

    # Do the boundary conditional tests
    test_pass_through(
        bus, dev, func, one_addr, one_mapped, ce_base)
    test_disabled_dma_remapping(bus, dev, func,
                                one_addr, one_mapped, ce_base)
    test_disabled_int_remapping(bus, dev, func,
                                one_vector, one_dest_cpu)
    test_no_present_ce_fault(bus, dev, func, ce_base)

    # Other than 4-level table walking fault
    test_unsupported_level_fault(bus, dev, func, ce_base)

    # Read/write protected fault
    test_protected_read_write_fault(bus, dev, func,
                                    one_addr, one_mapped, ce_base)

    # Fault overflow and fault buffer wrap around
    frr_idx = get_next_frr()
    if frr_idx < frcd_cnt:
        for i in range(frcd_cnt - frr_idx):
            test_no_present_ce_fault(bus, dev, func, ce_base)
    stest.expect_exception(get_next_frr, (), exc=stest.TestFailure)

    # Make room by clearing the fault record in the first recording register
    vtd_hw_drv.write_reg("FRCD0", VTdConst.frcd_bf.value(F=1))
    test_no_present_ce_fault(bus, dev, func, ce_base)


def get_next_frr():
    for i in range(frcd_cnt):
        val = vtd_hw_drv.read_reg("FRCD%d" % i)
        fields = VTdConst.frcd_bf.fields(val)
        if fields['F'] == 0:
            return i
    stest.fail("No free FRCD")


do_test()
