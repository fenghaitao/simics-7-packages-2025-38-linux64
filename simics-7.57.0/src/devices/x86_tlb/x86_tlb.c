/*
  x86_tlb.c

  © 2010 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#define DEVICE_INFO_STRING \
  "Default X86 TLB class."

#include <string.h>

#include <simics/device-api.h>
#include <simics/arch/x86.h>

// TODO: This violates the Device API (need supported way to flush)
#include <simics/processor/stc.h>

#include "x86_tlb.h"
#include "radix-tree.h"

#define DEVICE_NAME "x86-tlb"

static const char *const x86_memory_type_descr[8] = {
        [X86_None] = "none",
        [X86_Strong_Uncacheable] = "UC",
        [X86_Uncacheable] = "UC-",
        [X86_Write_Combining] = "WC",
        [X86_Write_Through] = "WT",
        [X86_Write_Back] = "WB",
        [X86_Write_Protected] = "WP",
};

hap_type_t x86_hap_tlb_invalidate[TLB_WAYS];
hap_type_t x86_hap_tlb_replace[TLB_WAYS];
hap_type_t x86_hap_tlb_fill[TLB_WAYS];
hap_type_t x86_hap_tlb_miss[TLB_WAYS];

int
size_k_to_page_code(int page_size_k)
{
        if (page_size_k == 1024 * 1024)
                return 3;
        else if (page_size_k == 4 * 1024)
                return 2;
        else if (page_size_k == 2 * 1024)
                return 1;
        ASSERT(page_size_k == 4);
        return 0;
}

static void
x86_tlb_flush_all(conf_object_t *obj, int keep_global_entries)
{
        x86_tlb_t *tlb = (x86_tlb_t *)obj;

        SIM_LOG_INFO(3, &tlb->obj, 0, "flush all (keep global: %d)",
                     keep_global_entries);

        rt_flush_all(tlb, keep_global_entries);
}

static void
x86_tlb_flush_page(conf_object_t *obj,
                   linear_address_t laddr)
{
        x86_tlb_t *tlb = (x86_tlb_t *)obj;

        SIM_LOG_INFO(3, &tlb->obj, 0, "flush page 0x%llx", laddr);

        rt_flush_page(tlb, laddr);
}

data_or_instr_t
select_from_access(access_t access)
{
        if (access & Sim_Access_Execute)
                return Sim_DI_Instruction;
        else
                return Sim_DI_Data;
}

static x86_tlb_entry_v3_t *
tlb_entry_to_tlb_entry_v3(conf_object_t *obj, const x86_tlb_entry_t *entry)
{
        // *FIXME* we MUST return pointer, but this pointer will be never freed.
        // Pointer to device data static variable used but pointee
        // can be overwritten by next call
        x86_tlb_t *tlb = (x86_tlb_t *)obj;
        x86_tlb_entry_v3_t *ret = &tlb->retval_v3;

        if (!entry)
                return NULL;

        ret->linear_page_start = entry->linear_page_start;
        ret->physical_page_start = entry->physical_page_start;
        ret->attrs.pat_type = entry->attrs.pat_type;
        ret->attrs.mtrr_type = entry->attrs.mtrr_type;
        ret->attrs.page_size_k = entry->attrs.page_size_k;
        ret->attrs.pte_attrs =
                   ((uint64)entry->attrs.user_access << X86_TLB_PTE_USER_SHIFT)
                || ((uint64)entry->attrs.supervisor_access
                    << X86_TLB_PTE_SVISOR_SHIFT)
                || (X86_TLB_PTE_GLOBAL ? entry->attrs.global_page : 0);
        return ret;
}

static x86_tlb_entry_t *
x86_tlb_lookup_common(x86_tlb_t *tlb, processor_mode_t mode,
                      access_t access, linear_address_t laddr,
                      physical_address_t *out_addr, bool inquiry)
{
        linear_address_t offset = 0;
        x86_tlb_entry_t *tlb_entry = NULL;

        tlb_entry = rt_lookup(tlb, mode, access, laddr, &offset);

        if (tlb_entry) {
                access_t cmp_access;

                if (mode == Sim_CPU_Mode_User)
                        cmp_access = tlb_entry->attrs.user_access;
                else
                        cmp_access = tlb_entry->attrs.supervisor_access;

                if ((cmp_access & access) == access) {
                        *out_addr = tlb_entry->physical_page_start + offset;
                        return tlb_entry;
                }
        }

        if (!inquiry) {
                data_or_instr_t tlb_type = select_from_access(access);

                SIM_c_hap_occurred_always(x86_hap_tlb_miss[tlb_type],
                                          &tlb->obj, laddr, (int64)laddr);
                (void)SIM_clear_exception();
        }
        return NULL;
}

static int
x86_tlb_lookup(conf_object_t *obj,
               x86_memory_transaction_t *mem_tr)
{
        x86_tlb_t *tlb = (x86_tlb_t *)obj;

        /* 
        ** Perform TLB lookup 
        ** Measurement on booting Linux showed that we hit roughly 75% in the 
        ** 4 meg TLB and 25% in the 4 k TLB (of all TLB hits) 
        */
        access_t access = (access_t)0;
        if (SIM_mem_op_is_write(&mem_tr->s) || mem_tr->fault_as_if_write)
                access |= Sim_Access_Write;
        if (SIM_mem_op_is_read(&mem_tr->s))
                access |= Sim_Access_Read;
        if (!SIM_mem_op_is_data(&mem_tr->s))
                access |= Sim_Access_Execute;

        x86_tlb_entry_t *entry =
                x86_tlb_lookup_common(tlb, mem_tr->mode, access,
                                      mem_tr->linear_address,
                                      &mem_tr->s.physical_address,
                                      SIM_get_mem_op_inquiry(&mem_tr->s));
        if (entry) {
                mem_tr->mtrr_type = entry->attrs.mtrr_type;
                mem_tr->pat_type = entry->attrs.pat_type;
        }
        return entry != NULL;
}

static const x86_tlb_entry_t *
x86_tlb_lookup_v2(conf_object_t *obj,
                  x86_memory_transaction_t *mem_tr)
{
        x86_tlb_t *tlb = (x86_tlb_t *)obj;

        /* 
        ** Perform TLB lookup 
        ** Measurement on booting Linux showed that we hit roughly 75% in the 
        ** 4 meg TLB and 25% in the 4 k TLB (of all TLB hits) 
        */
        access_t access = (access_t)0;
        if (!SIM_mem_op_is_data(&mem_tr->s)) {
                access |= Sim_Access_Execute;
        } else {
                if (SIM_mem_op_is_read(&mem_tr->s))
                        access |= Sim_Access_Read;
                if (SIM_mem_op_is_write(&mem_tr->s) || mem_tr->fault_as_if_write)
                        access |= Sim_Access_Write;
        }

        x86_tlb_entry_t *entry =
                x86_tlb_lookup_common(tlb, mem_tr->mode, access,
                                      mem_tr->linear_address,
                                      &mem_tr->s.physical_address,
                                      SIM_get_mem_op_inquiry(&mem_tr->s));
        if (entry) {
                mem_tr->mtrr_type = entry->attrs.mtrr_type;
                mem_tr->pat_type = entry->attrs.pat_type;
        }
        return entry;
}

static const x86_tlb_entry_v3_t *
x86_tlb_lookup_v3(conf_object_t *obj, uint64 pcid,
                  x86_memory_transaction_t *mem_tr)
{
        if (pcid != 0)
                return NULL;

        const x86_tlb_entry_t *entry = x86_tlb_lookup_v2(obj, mem_tr);
        return tlb_entry_to_tlb_entry_v3(obj, entry);
}

/* The read_or_write argument corresponds to the actual instruction that
   triggered the memory access, and NOT the PTE entry. It is important
   to insert TLB entries caused by a memory read as R/O tlb entries,
   so that we can detect a write that would mark the TLB as dirty. */

static void
x86_tlb_add(conf_object_t *obj,
            processor_mode_t mode,
            read_or_write_t read_or_write,
            data_or_instr_t tlb_select,
            int global_page,
            x86_memory_type_t pat_type,
            x86_memory_type_t mtrr_type,
            linear_address_t laddr,
            physical_address_t paddr,
            int page_code)
{
        x86_tlb_entry_t new_tlb_entry;
        x86_tlb_t *tlb = (x86_tlb_t *)obj;

        SIM_LOG_INFO(4, &tlb->obj, 0, "add %s %s %s: logical-address=0x%llx, "
                     "physical-address=0x%llx, size=%d",
                     read_or_write == Sim_RW_Read ? "read" : "write",
                     tlb_select == Sim_DI_Data ? "data" : "instruction",
                     global_page ? "global" : "nonglobal",
                     laddr, paddr, page_code);

        /* Note: We cannot insert the page in the TLB with writes
           enabled if the current access is a read/fetch. A later write
           will generate a 'false' TLB miss that updates the dirty bit
           correctly. */
        access_t access;
        if (tlb_select == Sim_DI_Instruction)
                access = Sim_Access_Execute;
        else if (read_or_write == Sim_RW_Write)
                access = (Sim_Access_Read | Sim_Access_Write);
        else
                access = Sim_Access_Read;
        if (mode == Sim_CPU_Mode_User)
                new_tlb_entry.attrs.user_access = access;
        else
                new_tlb_entry.attrs.user_access = 0;
        new_tlb_entry.attrs.supervisor_access = access;
        new_tlb_entry.attrs.global_page = global_page;
        new_tlb_entry.attrs.pat_type = pat_type;
        new_tlb_entry.attrs.mtrr_type = mtrr_type;

        linear_address_t pagesize_k;
        if (page_code == 3) {
                /* 1 GiB */
                pagesize_k = 1024 * 1024;
        } else if (page_code == 2) {
                /* 4 MiB */
                pagesize_k = 4 * 1024;
        } else if (page_code == 1) {
                /* 2 MiB */
                pagesize_k = 2 * 1024;
        } else {
                /* 4 KiB */
                pagesize_k = 4;
        }
        new_tlb_entry.attrs.page_size_k = pagesize_k;
        new_tlb_entry.linear_page_start = laddr & ~((linear_address_t)pagesize_k * 1024 - 1);
        new_tlb_entry.physical_page_start = paddr & ~((physical_address_t)pagesize_k * 1024 - 1);

        rt_add(tlb, &new_tlb_entry);
}

static void
x86_tlb_add_v2(conf_object_t *obj,
               linear_address_t laddr,
               physical_address_t paddr,
               x86_tlb_attrs_t attrs)
{
        x86_tlb_entry_t new_tlb_entry = {};
        x86_tlb_t *tlb = (x86_tlb_t *)obj;

        SIM_LOG_INFO(4, &tlb->obj, 0, "add %s%s%s/%s%s%s %s: logical-address=0x%llx, "
                     "physical-address=0x%llx, size_k=%d",
                     (attrs.supervisor_access & Sim_Access_Read) ? "r" : "-",
                     (attrs.supervisor_access & Sim_Access_Write) ? "w" : "-",
                     (attrs.supervisor_access & Sim_Access_Execute) ? "x" : "-",
                     (attrs.user_access & Sim_Access_Read) ? "r" : "-",
                     (attrs.user_access & Sim_Access_Write) ? "w" : "-",
                     (attrs.user_access & Sim_Access_Execute) ? "x" : "-",
                     attrs.global_page ? "global" : "nonglobal",
                     laddr, paddr, attrs.page_size_k);

        new_tlb_entry.attrs = attrs;
        new_tlb_entry.linear_page_start = laddr & ~((linear_address_t)attrs.page_size_k * 1024 - 1);
        new_tlb_entry.physical_page_start = paddr & ~((physical_address_t)attrs.page_size_k * 1024 - 1);

        rt_add(tlb, &new_tlb_entry);
}

static void
x86_tlb_add_v3(conf_object_t *obj,
               uint64 pcid,
               linear_address_t laddr,
               physical_address_t paddr,
               x86_tlb_attrs_v3_t attrs)
{
        if (pcid != 0)
                return;

        x86_tlb_attrs_t attrs_v2;
        attrs_v2.supervisor_access = (attrs.pte_attrs
                & X86_TLB_PTE_SVISOR_MASK) >> X86_TLB_PTE_SVISOR_SHIFT;
        attrs_v2.user_access = (attrs.pte_attrs
                & X86_TLB_PTE_USER_MASK) >> X86_TLB_PTE_USER_SHIFT;
        attrs_v2.global_page = attrs.pte_attrs & X86_TLB_PTE_GLOBAL;
        attrs_v2.page_size_k = attrs.page_size_k;
        attrs_v2.mtrr_type = attrs.mtrr_type;
        attrs_v2.pat_type = attrs.pat_type;

        x86_tlb_add_v2(obj, laddr, paddr, attrs_v2);
}

static tagged_physical_address_t
x86_tlb_itlb_lookup(conf_object_t *obj,
                    linear_address_t laddr,
                    processor_mode_t mode)
{
        x86_tlb_t *tlb = (x86_tlb_t *)obj;
        tagged_physical_address_t ret = {0, 0};
        ret.valid = x86_tlb_lookup_common(tlb, mode, Sim_Access_Execute,
                                          laddr, &ret.paddr, false) != NULL;
        return ret;
}

static tagged_physical_address_t
x86_tlb_itlb_lookup_v3(conf_object_t *obj,
                    uint64 pcid,
                    linear_address_t laddr,
                    processor_mode_t mode)
{
        if (pcid != 0)
                return (tagged_physical_address_t){0, 0};

        return x86_tlb_itlb_lookup(obj, laddr, mode);
}

static void
x86_tlb_set_pae_mode(conf_object_t *obj, bool enabled)
{
        /* We no longer care about PAE / non-PAE */
}

static void
x86_tlb_invalidate_page_v3(conf_object_t *obj, uint64 pcid,
                           linear_address_t laddr)
{
        if (pcid != 0)
                return;
        x86_tlb_flush_page(obj, laddr);
}

static void
x86_tlb_invalidate_v3(conf_object_t *obj, uint32 type, uint64 pcid,
                      linear_address_t laddr)
{
        if (pcid != 0)
                return;

        switch (type) {
        case X86_Tlb_Invalidate_Page:
                x86_tlb_flush_page(obj, laddr);
                return;

        case X86_Tlb_Invalidate_Address_Space_NonGlobal:
        case X86_Tlb_Invalidate_All_NonGlobal:
                x86_tlb_flush_all(obj, 1);
                return;

        case X86_Tlb_Invalidate_Address_Space:
        case X86_Tlb_Invalidate_All:
                x86_tlb_flush_all(obj, 0);
                return;

        default:
                ASSERT(0);
        }
}

static conf_object_t *
alloc_object(void *arg)
{
        x86_tlb_t *tlb = MM_ZALLOC(1, x86_tlb_t);
        return &tlb->obj;
}

static int
delete_instance(conf_object_t *obj)
{
        x86_tlb_t *tlb = (x86_tlb_t *)obj;
        rt_leave_mode(tlb);
        MM_FREE(tlb);
        return 0;
}

static void *
init_object(conf_object_t *obj, void *arg)
{
        x86_tlb_t *tlb = (x86_tlb_t *)obj;

        rt_enter_mode(tlb);

        return obj;
}

static set_error_t
set_cpu(void *_id, conf_object_t *obj, attr_value_t *val, attr_value_t *idx)
{
        x86_tlb_t *ptr = (x86_tlb_t *)obj;
        conf_object_t *cpu = SIM_attr_object(*val);
        if (!SIM_c_get_interface(cpu, "stc")) {
                SIM_c_attribute_error(
                        "The object %s does not implement the stc interface.",
                        SIM_object_name(cpu));
                return Sim_Set_Interface_Not_Found;
        }
        ptr->cpu = cpu;
        return Sim_Set_Ok;
}

static attr_value_t
get_cpu(void *_id, conf_object_t *obj, attr_value_t *idx)
{
        x86_tlb_t *ptr = (x86_tlb_t *)obj;
        if (ptr->cpu) {
                return SIM_make_attr_object(ptr->cpu);
        }
        return SIM_make_attr_nil();
}

static int
parse_memtype(const char *str)
{
        int i;
        for (i = 0; x86_memory_type_descr[i]; i++)
                if (strcmp(x86_memory_type_descr[i], str) == 0)
                        return i;
        return -1;
}

/* Convert an attribute list (assumed well-formed with respect to
   attribute types, but not necessarily its contents) to a TLB entry.
   Return true on success, false on error. */
bool
tlb_entry_from_attr(x86_tlb_entry_t *e, attr_value_t *a)
{
        uint64 la    = SIM_attr_integer(SIM_attr_list_item(*a, 0));
        uint64 pa    = SIM_attr_integer(SIM_attr_list_item(*a, 1));
        uint64 super = SIM_attr_integer(SIM_attr_list_item(*a, 2));
        uint64 user  = SIM_attr_integer(SIM_attr_list_item(*a, 3));
        uint64 glob  = SIM_attr_integer(SIM_attr_list_item(*a, 4));
        const char *pat_name =
                        SIM_attr_string(SIM_attr_list_item(*a, 5));
        const char *mtrr_name =
                        SIM_attr_string(SIM_attr_list_item(*a, 6));
        uint64 psize = SIM_attr_integer(SIM_attr_list_item(*a, 7));

        int pat = parse_memtype(pat_name);
        if (pat == -1)
                return false;
        int mtrr = parse_memtype(mtrr_name);
        if (mtrr == -1)
                return false;

        e->linear_page_start = la;
        e->physical_page_start = pa;
        e->attrs.supervisor_access = super;
        e->attrs.user_access = user;
        e->attrs.global_page = glob;
        e->attrs.pat_type = pat;
        e->attrs.mtrr_type = mtrr;
        e->attrs.page_size_k = psize;

        return true;
}

attr_value_t
attr_from_tlb_entry(x86_tlb_entry_t *entry)
{
        return SIM_make_attr_list(
                8,
                SIM_make_attr_uint64(entry->linear_page_start),
                SIM_make_attr_uint64(entry->physical_page_start),
                SIM_make_attr_uint64(entry->attrs.supervisor_access),
                SIM_make_attr_uint64(entry->attrs.user_access),
                SIM_make_attr_uint64(entry->attrs.global_page),
                SIM_make_attr_string(x86_memory_type_descr[entry->attrs.pat_type]),
                SIM_make_attr_string(x86_memory_type_descr[entry->attrs.mtrr_type]),
                SIM_make_attr_uint64(entry->attrs.page_size_k));
}

static set_error_t
set_x86_tlb(void *_id, conf_object_t *obj,
            attr_value_t *val, attr_value_t *_unused)
{
        x86_tlb_t *ptr = (x86_tlb_t *)obj;

        if (!SIM_attr_is_list(*val) && !SIM_attr_is_nil(*val))
                return Sim_Set_Illegal_Type;

        set_error_t ret = rt_attr_set(ptr, val);

        /* Flush data structures that depend on the address mapping. */
        if (ptr->cpu)
                SIM_STC_flush_cache(ptr->cpu);
        return ret;
}

static attr_value_t
get_x86_tlb(void *_id, conf_object_t *obj, attr_value_t *_unused)
{
        x86_tlb_t *ptr = (x86_tlb_t *)obj;
        return rt_attr_get(ptr);
}

void
init_local()
{
        const class_data_t class_data = {
                .alloc_object = alloc_object,
                .init_object = init_object,
                .description = DEVICE_INFO_STRING,
                .class_desc = "model of X86 TLB",
                .delete_instance = delete_instance
        };
        conf_class_t *class = SIM_register_class(DEVICE_NAME, &class_data);

        static const x86_tlb_interface_t tlb_iface = {
                .flush_all = x86_tlb_flush_all,
                .flush_page = x86_tlb_flush_page,
                .lookup = x86_tlb_lookup,
                .add = x86_tlb_add,
                .itlb_lookup = x86_tlb_itlb_lookup,
                .set_pae_mode = x86_tlb_set_pae_mode
        };
        SIM_register_interface(class, X86_TLB_INTERFACE, &tlb_iface);

        static const x86_tlb_v2_interface_t tlb_v2_iface = {
                .flush_all = x86_tlb_flush_all,
                .flush_page = x86_tlb_flush_page,
                .lookup = x86_tlb_lookup_v2,
                .add = x86_tlb_add_v2,
                .itlb_lookup = x86_tlb_itlb_lookup
        };
        SIM_register_interface(class, X86_TLB_V2_INTERFACE, &tlb_v2_iface);

        static const x86_tlb_v3_interface_t tlb_v3_iface = {
                .add = x86_tlb_add_v3,
                .lookup = x86_tlb_lookup_v3,
                .itlb_lookup = x86_tlb_itlb_lookup_v3,
                .invalidate_page = x86_tlb_invalidate_page_v3,
                .invalidate = x86_tlb_invalidate_v3
        };
        SIM_register_interface(class, X86_TLB_V3_INTERFACE, &tlb_v3_iface);

        SIM_register_typed_attribute(class, "cpu",
                                     get_cpu, NULL, set_cpu, NULL,
                                     Sim_Attr_Required,
                                     "o", NULL,
                                     "CPU object to which TLB object is "
                                     "bound.");

        SIM_register_typed_attribute(class, "tlb",
                                     get_x86_tlb, NULL, set_x86_tlb, NULL,
                                     Sim_Attr_Optional,
                                     "[[iiiiissi]*]", NULL,
                                     "((la, pa, supervisor_access, user_access,"
                                     " g, pat_type, mtrr_type, page_size_k)*)."
                                     " TLB.");

        x86_hap_tlb_fill[Sim_DI_Instruction] =
                SIM_hap_add_type("TLB_Fill_Instruction",
                                 "III", "linear physical page_size",
                                 "page_size",
                                 "Triggered when a TLB entry is filled after "
                                 "a table walk. Page size encoding: 0==4k, "
                                 "1==2M, 2==4M, 3==1G.", 0);
        x86_hap_tlb_fill[Sim_DI_Data] =
                SIM_hap_add_type("TLB_Fill_Data",
                                 "III", "linear physical page_size",
                                 "page_size",
                                 "Triggered when a TLB entry is filled after "
                                 "a table walk. Page size encoding: 0==4k, "
                                 "1==2M, 2==4M, 3==1G.", 0);
        x86_hap_tlb_replace[Sim_DI_Instruction] =
                SIM_hap_add_type("TLB_Replace_Instruction",
                                 "III", "linear physical page_size",
                                 "page_size",
                                 "This hap is triggered when a TLB entry is "
                                 "replaced by another. The parameters relate "
                                 "to the old entry, and the insertion of the "
                                 "new entry will trigger a fill hap. Page "
                                 "size encoding: 0==4k, 1==2M, 2==4M, 3==1G.", 0);
        x86_hap_tlb_replace[Sim_DI_Data] =
                SIM_hap_add_type("TLB_Replace_Data",
                                 "III", "linear physical page_size",
                                 "page_size",
                                 "This hap is triggered when a TLB entry is "
                                 "replaced by another. The parameters relate "
                                 "to the old entry, and the insertion of the "
                                 "new entry will trigger a fill hap. Page "
                                 "size encoding: 0==4k, 1==2M, 2==4M, 3==1G.", 0);
        x86_hap_tlb_invalidate[Sim_DI_Instruction] =
                SIM_hap_add_type("TLB_Invalidate_Instruction",
                                 "III", "linear physical page_size",
                                 "page_size",
                                 "Triggered when a TLB entry is invalidated. "
                                 "The invalidation can be caused by an INVLPG "
                                 "instruction, a write to CR3, or by changes "
                                 "to paging bits in CR0 and CR4. Page size "
                                 "encoding: 0==4k, 1==2M, 2==4M, 3==1G.", 0);
        x86_hap_tlb_invalidate[Sim_DI_Data] =
                SIM_hap_add_type("TLB_Invalidate_Data",
                                 "III", "linear physical page_size",
                                 "page_size",
                                 "Triggered when a TLB entry is invalidated. "
                                 "The invalidation can be caused by an INVLPG "
                                 "instruction, a write to CR3, or by changes "
                                 "to paging bits in CR0 and CR4. Page size "
                                 "encoding: 0==4k, 1==2M, 2==4M, 3==1G.", 0);
        x86_hap_tlb_miss[Sim_DI_Instruction] =
                SIM_hap_add_type("TLB_Miss_Instruction",
                                 "I", "linear_address",
                                 "linear_address",
                                 "Triggered when an ITLB miss occurs.", 0);
        x86_hap_tlb_miss[Sim_DI_Data] =
                SIM_hap_add_type("TLB_Miss_Data",
                                 "I", "linear_address",
                                 "linear_address",
                                 "Triggered when a DTLB miss occurs.", 0);
}
