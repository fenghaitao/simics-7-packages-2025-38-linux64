/*
  © 2015 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include "radix-tree.h"
#include "x86_tlb.h"
#include <simics/processor/stc.h>

/* We use a radix tree of the same structure as the x86 page tables,
   with 4 table levels:

             level 4
   root -> +---------+      level 3
           |       -----> +---------+      level 2
           +---------+    |       -----> +---------+      level 1
           :         :    +---------+    |       -----> +---------+
           +---------+    | 1G page |    +---------+    | 4K page |
                          +---------+    | 2M page |    +---------+
                          :         :    +---------+    :         :
                          +---------+    :         :    +---------+
                                         +---------+

   Each table has 512 entries.
   4 MiB pages are represented as aligned pairs of 2 MiB pages with the
   4M flag set.

   Each pointer/entry, including the root pointer, is a 64-bit word:

    63               2 1 0
   +------------------+-+-+
   |         0        |0|0|  Empty entry.
   +------------------+-+-+
   
   +------------------+-+-+  Pointer to a lower-level table. If N=0, then
   | pointer (≠ NULL) |N|0|  all entries in that table have N=0.
   +------------------+-+-+
   
   +------------------+-+-+  Page entry (only in the 3 lowest levels).
   |     page entry   |N|1|  N is the inverse of the global flag.
   +------------------+-+-+                                                 */


#define ENTRY_BIT_PRESENT 1                  /* Page present bit. */
#define ENTRY_BIT_NG      2                  /* Non-global bit. */

/* In the following macros, T is the type of the entries on the next
   level. */

/* A pointer to an array[512] of T, or a page entry, or empty. */
#define ENTRY_T(T) struct entry_ ## T { uint64 w_ ## T; }

/* Whether an entry is empty. */
#define IS_NULL(T, e) ((e).w_ ## T == 0)

/* Whether an entry is a page. */
#define IS_PAGE(T, e) ((e).w_ ## T & ENTRY_BIT_PRESENT)

/* Whether an entry is a pointer to a subtable. */
#define IS_PTR(T, e) (!IS_NULL(T, e) && !IS_PAGE(T, e))

/* Get the pointer (to T). */
#define ENTRY_PTR(T, e) ((T *)((e).w_ ## T & ~(uint64)ENTRY_BIT_NG))

/* Get a page. */
#define ENTRY_TLB(T, e) ((tlbe_t){.bits = (e).w_ ## T})

/* Get the raw bits of an entry. */
#define ENTRY_BITS(T, e) ((e).w_ ## T)

/* Whether the bits of an entry has any of the mask bits set. */
#define ENTRY_TEST(T, e, mask) (ENTRY_BITS(T, e) & (mask))

/* Make an entry from raw bits. */
#define MK_ENTRY_BITS(T, bits) ((struct entry_ ## T){ .w_ ## T = (bits) })

/* Make a null entry. */
#define MK_ENTRY_NULL(T) MK_ENTRY_BITS(T, 0)

/* Make a pointer entry. */
#define MK_ENTRY_PTR(T, p, ng) MK_ENTRY_BITS(T, (uintptr_t)(p) | (ng) << 1)

/* Make a page entry. */
#define MK_ENTRY_PAGE(T, tlbe) MK_ENTRY_BITS(T, (tlbe).bits | 1)

/* Make an entry equal to e but with the N bit clear. */
#define MK_ENTRY_N_CLEAR(T, e)                                           \
        MK_ENTRY_BITS(T, ENTRY_BITS(T, e) & ~(uint64)ENTRY_BIT_NG)

/* "leaf" is not actually a type; an e1_t cannot hold a pointer. */
typedef ENTRY_T(leaf) e1_t;
typedef ENTRY_T(e1_t) e2_t;
typedef ENTRY_T(e2_t) e3_t;
typedef ENTRY_T(e3_t) e4_t;
typedef ENTRY_T(e4_t) root_t;

struct x86_tlb_impl {
        root_t root;

        /* A value to be returned from lookup, only valid until the next
           call. (This should be eliminated by changing the interface to
           x86_tlb.c.) */
        x86_tlb_entry_t retval;
};

typedef struct {
        uint64 bits;
} tlbe_t;

/* Bit field layout in the tlbe word:
                     bit    width  meaning */
#define TLBE_NG        1   //   1  non-global
#define TLBE_MTRR      2   //   3  MTRR type (x86_memory_type_t)
#define TLBE_PAT       5   //   3  PAT type (x86_memory_type_t)
#define TLBE_4M        8   //   1  1 if a 4 MiB page
#define TLBE_PHYSADDR 12   //  36  physical_address[47..12]
#define TLBE_USR_ACC  48   //   3  user access rights (access_t)
#define TLBE_SUP_ACC  51   //   3  supervisor access rights (access_t)

#define TLBE_PHYSADDR_MASK 0x0000fffffffff000

static bool
tlbe_global(tlbe_t tlbe) { return !((tlbe.bits >> TLBE_NG) & 1); }

static x86_memory_type_t
tlbe_mtrr(tlbe_t tlbe) { return (tlbe.bits >> TLBE_MTRR) & 7; }

static x86_memory_type_t
tlbe_pat(tlbe_t tlbe) { return (tlbe.bits >> TLBE_PAT) & 7; }

static bool
tlbe_4m(tlbe_t tlbe) { return (tlbe.bits >> TLBE_4M) & 1; }

static uint64
tlbe_phys_addr(tlbe_t tlbe) { return tlbe.bits & TLBE_PHYSADDR_MASK; }

static access_t
tlbe_user_access(tlbe_t tlbe) { return (tlbe.bits >> TLBE_USR_ACC) & 7; }

static access_t
tlbe_super_access(tlbe_t tlbe) { return (tlbe.bits >> TLBE_SUP_ACC) & 7; }

static bool
tlbe_executable(tlbe_t tlbe)
{
        return (tlbe_user_access(tlbe) | tlbe_super_access(tlbe))
               & Sim_Access_Execute;
}

static tlbe_t
make_tlbe(physical_address_t physaddr, bool global, bool page_4m,
          x86_memory_type_t mtrr, x86_memory_type_t pat,
          access_t user_access, access_t supervisor_access)
{
        return (tlbe_t){  !global << TLBE_NG
                        | page_4m << TLBE_4M
                        | mtrr << TLBE_MTRR
                        | pat << TLBE_PAT
                        | (physaddr & TLBE_PHYSADDR_MASK)
                        | (uint64)user_access << TLBE_USR_ACC
                        | (uint64)supervisor_access << TLBE_SUP_ACC };
}

static x86_tlb_impl_t *
make_impl()
{
        x86_tlb_impl_t *rt = MM_ZALLOC(1, x86_tlb_impl_t);
        return rt;
}

/* Deallocate an e1 table, and set its reference to empty.
   e2 must be a reference to an allocated table. */
static void
dealloc_e1(e2_t *e2)
{
        e1_t *e1 = ENTRY_PTR(e1_t, *e2);
        MM_FREE(e1);
        *e2 = MK_ENTRY_NULL(e1_t);
}

/* Deallocate an e2 table, and set its reference to empty.
   e3 must be a reference to an allocated table without references inside. */
static void
dealloc_e2(e3_t *e3)
{
        e2_t *e2 = ENTRY_PTR(e2_t, *e3);
        MM_FREE(e2);
        *e3 = MK_ENTRY_NULL(e2_t);
}

/* Deallocate an e3 table, and set its reference to empty.
   e4 must be a reference to an allocated table without references inside. */
static void
dealloc_e3(e4_t *e4)
{
        e3_t *e3 = ENTRY_PTR(e3_t, *e4);
        MM_FREE(e3);
        *e4 = MK_ENTRY_NULL(e3_t);
}

/* Deallocate an e4 table, and set its reference to empty.
   root must be a reference to an allocated table without references inside. */
static void
dealloc_e4(root_t *root)
{
        e4_t *e4 = ENTRY_PTR(e4_t, *root);
        MM_FREE(e4);
        *root = MK_ENTRY_NULL(e4_t);
}

/* Destroy an e2 entry, deallocating anything underneath. */
static void
destroy_e2(e2_t *e2)
{
        if (IS_PTR(e1_t, *e2))
                dealloc_e1(e2);
        *e2 = MK_ENTRY_NULL(e1_t);
}

/* Destroy an e3 entry, deallocating anything underneath. */
static void
destroy_e3(e3_t *e3)
{
        if (IS_PTR(e2_t, *e3)) {
                e2_t *e2 = ENTRY_PTR(e2_t, *e3);
                for (int i = 0; i < 512; i++)
                        destroy_e2(&e2[i]);
                dealloc_e2(e3);
        }
        *e3 = MK_ENTRY_NULL(e2_t);
}

/* Destroy an e4 entry, deallocating anything underneath. */
static void
destroy_e4(e4_t *e4)
{
        if (!IS_NULL(e3_t, *e4)) {
                e3_t *e3 = ENTRY_PTR(e3_t, *e4);
                for (int i = 0; i < 512; i++)
                        destroy_e3(&e3[i]);
                dealloc_e3(e4);
        }
}

/* Destroy a root entry, deallocating anything underneath. */
static void
destroy_root(x86_tlb_impl_t *rt)
{
        if (!IS_NULL(e4_t, rt->root)) {
                e4_t *e4 = ENTRY_PTR(e4_t, rt->root);
                for (int i = 0; i < 512; i++)
                        destroy_e4(&e4[i]);
                dealloc_e4(&rt->root);
        }
}

static void
destroy_impl(x86_tlb_impl_t *rt)
{
        destroy_root(rt);
        MM_FREE(rt);
}

void
rt_enter_mode(x86_tlb_t *tlb)
{
        tlb->imp = make_impl();
}

void
rt_leave_mode(x86_tlb_t *tlb)
{
        destroy_impl(tlb->imp);
        tlb->imp = NULL;
}

static void
flush_region(x86_tlb_t *tlb, tlbe_t tlbe, linear_address_t laddr, unsigned size)
{
        SIM_flush_D_STC_logical(tlb->cpu, laddr, size);
        if (tlbe_executable(tlbe))
                SIM_flush_I_STC_logical(tlb->cpu, laddr, size);
        int page_code = size_k_to_page_code(size >> 10);
        SIM_c_hap_occurred_always(
                x86_hap_tlb_invalidate[Sim_DI_Data],
                &tlb->obj, page_code,
                laddr, tlbe_phys_addr(tlbe), (uint64)page_code);
}

static void
remove_pages(x86_tlb_t *tlb, bool keep_global)
{
        x86_tlb_impl_t *rt = tlb->imp;
        
        /* Mask to determine whether an entry or a tagged pointer should
           be examined. */
        uint64 mask = keep_global ? 2 : (uint64)-1;

        if (!ENTRY_TEST(e4_t, rt->root, mask))
                return;
        e4_t *e4 = ENTRY_PTR(e4_t, rt->root);
        uint64 e4_bits = 0;
        for (int i = 0; i < 512; i++) {
                e4_t e4e = e4[i];
                uint64 e4_bits_before = e4_bits;
                e4_bits |= ENTRY_BITS(e3_t, e4e);
                if (!ENTRY_TEST(e3_t, e4e, mask))
                        continue;
                e3_t *e3 = ENTRY_PTR(e3_t, e4e);
                uint64 e3_bits = 0;
                for (int j = 0; j < 512; j++) {
                        e3_t e3e = e3[j];
                        uint64 e3_bits_before = e3_bits;
                        e3_bits |= ENTRY_BITS(e2_t, e3e);
                        if (!ENTRY_TEST(e2_t, e3e, mask))
                                continue;
                        if (IS_PAGE(e2_t, e3e)) {
                                flush_region(tlb, ENTRY_TLB(e2_t, e3e),
                                             (uint64)i << 39 | (uint64)j << 30,
                                             1 << 30);
                                e3[j] = MK_ENTRY_NULL(e2_t);
                                e3_bits = e3_bits_before;
                                continue;
                        }
                        e2_t *e2 = ENTRY_PTR(e2_t, e3e);
                        uint64 e2_bits = 0;
                        for (int k = 0; k < 512; k++) {
                                e2_t e2e = e2[k];
                                uint64 e2_bits_before = e2_bits;
                                e2_bits |= ENTRY_BITS(e1_t, e2e);
                                if (!ENTRY_TEST(e1_t, e2e, mask))
                                        continue;
                                e1_t *e1 = ENTRY_PTR(e1_t, e2e);
                                if (IS_PAGE(e1_t, e2e)) {
                                        bool page_4m =
                                                tlbe_4m(ENTRY_TLB(e1_t, e2e));
                                        unsigned size =
                                                page_4m ? 1 << 22 : 1 << 21;
                                        if (!(page_4m && (k & 1)))
                                                flush_region(
                                                        tlb,
                                                        ENTRY_TLB(e1_t, e2e),
                                                        (uint64)i << 39
                                                        | (uint64)j << 30
                                                        | k << 21,
                                                        size);
                                        e2[k] = MK_ENTRY_NULL(e1_t);
                                        e2_bits = e2_bits_before;
                                        continue;
                                }
                                uint64 e1_bits = 0;
                                for (int m = 0; m < 512; m++) {
                                        e1_t e1e = e1[m];
                                        if (IS_PAGE(leaf, e1e)
                                            && ENTRY_TEST(leaf, e1e, mask)) {
                                                flush_region(
                                                        tlb,
                                                        ENTRY_TLB(leaf, e1e),
                                                        (uint64)i << 39
                                                        | (uint64)j << 30
                                                        | k << 21
                                                        | m << 12,
                                                        1 << 12);
                                                e1[m] = MK_ENTRY_NULL(leaf);
                                        }
                                        e1_bits |= ENTRY_BITS(leaf, e1e);
                                }
                                if (e1_bits)
                                        e2[k] = MK_ENTRY_N_CLEAR(e1_t, e2[k]);
                                else
                                        dealloc_e1(&e2[k]);
                                e2_bits = e2_bits_before
                                          | ENTRY_BITS(e1_t, e2[k]);
                        }
                        if (e2_bits)
                                e3[j] = MK_ENTRY_N_CLEAR(e2_t, e3[j]);
                        else
                                dealloc_e2(&e3[j]);
                        e3_bits = e3_bits_before | ENTRY_BITS(e2_t, e3[j]);
                }
                if (e3_bits)
                        e4[i] = MK_ENTRY_N_CLEAR(e3_t, e4[i]);
                else
                        dealloc_e3(&e4[i]);
                e4_bits = e4_bits_before | ENTRY_BITS(e3_t, e4[i]);
        }
        if (e4_bits)
                rt->root = MK_ENTRY_N_CLEAR(e4_t, rt->root);
        else
                dealloc_e4(&rt->root);
}

void
rt_flush_all(x86_tlb_t *tlb, int keep_global_entries)
{
        x86_tlb_impl_t *rt = tlb->imp;
        if (keep_global_entries
            || SIM_hap_is_active_obj(x86_hap_tlb_invalidate[Sim_DI_Instruction],
                                     &tlb->obj)
            || SIM_hap_is_active_obj(x86_hap_tlb_invalidate[Sim_DI_Data],
                                     &tlb->obj)) {
                remove_pages(tlb, keep_global_entries);
        } else {
                destroy_root(rt);
                SIM_STC_flush_cache(tlb->cpu);
        }
}

typedef struct {
        unsigned size;            /* Size of page; 0 if no page was present. */
        bool exec;                /* Page had execute permission. */
} rm_page_t;

/* Remove a page at laddr; return information about a page that was
   replaced, if any. */
static rm_page_t
remove_page(x86_tlb_impl_t *rt, linear_address_t laddr)
{
        e4_t *e4 = ENTRY_PTR(e4_t, rt->root);
        if (!e4)
                return (rm_page_t){0, false};
        
        unsigned e4_idx = (laddr >> 39) & 511;
        e3_t *e3 = ENTRY_PTR(e3_t, e4[e4_idx]);
        if (!e3)
                return (rm_page_t){0, false};

        unsigned e3_idx = (laddr >> 30) & 511;
        e3_t e3e = e3[e3_idx];
        if (IS_PAGE(e2_t, e3e)) {
                bool exec = tlbe_executable(ENTRY_TLB(e2_t, e3e));
                e3[e3_idx] = MK_ENTRY_NULL(e2_t);
                return (rm_page_t){1 << 30, exec};
        }
        e2_t *e2 = ENTRY_PTR(e2_t, e3e);
        if (!e2)
                return (rm_page_t){0, false};

        unsigned e2_idx = (laddr >> 21) & 511;
        e2_t e2e = e2[e2_idx];
        if (IS_PAGE(e1_t, e2e)) {
                bool exec = tlbe_executable(ENTRY_TLB(e1_t, e2e));
                bool page_4m = tlbe_4m(ENTRY_TLB(e1_t, e2e));
                e2[e2_idx] = MK_ENTRY_NULL(e1_t);
                if (page_4m)
                        e2[e2_idx ^ 1] = MK_ENTRY_NULL(e1_t);
                return (rm_page_t){page_4m ? 1 << 22 : 1 << 21, exec};
        }
        e1_t *e1 = ENTRY_PTR(e1_t, e2e);
        if (!e1)
                return (rm_page_t){0, false};

        unsigned e1_idx = (laddr >> 12) & 511;
        e1_t e1e = e1[e1_idx];
        if (IS_PAGE(leaf, e1e)) {
                bool exec = tlbe_executable(ENTRY_TLB(leaf, e1e));
                e1[e1_idx] = MK_ENTRY_NULL(leaf);
                return (rm_page_t){1 << 12, exec};
        }
        return (rm_page_t){0, false};
}

void
rt_flush_page(x86_tlb_t *tlb, linear_address_t laddr)
{
        x86_tlb_impl_t *rt = tlb->imp;
        rm_page_t r = remove_page(rt, laddr);
        if (r.size) {
                linear_address_t start = laddr & ~(uint64)(r.size - 1);
                SIM_flush_D_STC_logical(tlb->cpu, start, r.size);
                if (r.exec)
                        SIM_flush_I_STC_logical(tlb->cpu, start, r.size);
        }
}

/* Set *rv to the tlbe in tlbe, using the given linear address and page size.
   Returns rv (as a minor optimisation). */
static x86_tlb_entry_t *
tlbe_to_retval(x86_tlb_entry_t *rv,
               tlbe_t tlbe, uint64 laddr, unsigned pagesize)
{
        rv->linear_page_start = laddr;
        /* Physical address needs adjustment in case it's a 4 MiB page. */
        rv->physical_page_start =
                tlbe_phys_addr(tlbe) & ~(uint64)(pagesize - 1);
        rv->attrs.global_page = tlbe_global(tlbe);
        rv->attrs.supervisor_access = tlbe_super_access(tlbe);
        rv->attrs.user_access = tlbe_user_access(tlbe);
        rv->attrs.pat_type = tlbe_pat(tlbe);
        rv->attrs.mtrr_type = tlbe_mtrr(tlbe);
        rv->attrs.page_size_k = pagesize >> 10;
        return rv;
}

x86_tlb_entry_t *
rt_lookup(x86_tlb_t *tlb, processor_mode_t mode,
          access_t access, linear_address_t laddr,
          linear_address_t *offset)
{
        x86_tlb_impl_t *rt = tlb->imp;
        e4_t *e4 = ENTRY_PTR(e4_t, rt->root);
        if (!e4)
                return NULL;
        
        unsigned e4_idx = (laddr >> 39) & 511;
        e3_t *e3 = ENTRY_PTR(e3_t, e4[e4_idx]);
        if (!e3)
                return NULL;

        unsigned e3_idx = (laddr >> 30) & 511;
        e3_t e3e = e3[e3_idx];
        if (IS_PAGE(e2_t, e3e)) {
                *offset = laddr & ((1 << 30) - 1);
                return tlbe_to_retval(&rt->retval, ENTRY_TLB(e2_t, e3e),
                                      laddr - *offset, 1 << 30);
        }
        e2_t *e2 = ENTRY_PTR(e2_t, e3e);
        if (!e2)
                return NULL;

        unsigned e2_idx = (laddr >> 21) & 511;
        e2_t e2e = e2[e2_idx];
        if (IS_PAGE(e1_t, e2e)) {
                unsigned size = tlbe_4m(ENTRY_TLB(e1_t, e2e))
                                ? 1 << 22 : 1 << 21;
                *offset = laddr & (size - 1);
                return tlbe_to_retval(&rt->retval, ENTRY_TLB(e1_t, e2e),
                                      laddr - *offset, size);
        }
        e1_t *e1 = ENTRY_PTR(e1_t, e2e);
        if (!e1)
                return NULL;

        unsigned e1_idx = (laddr >> 12) & 511;
        e1_t e1e = e1[e1_idx];
        if (IS_PAGE(leaf, e1e)) {
                *offset = laddr & ((1 << 12) - 1);
                return tlbe_to_retval(&rt->retval, ENTRY_TLB(leaf, e1e),
                                      laddr - *offset, 1 << 12);
        }
        return NULL;
}

/* Add an entry. Return true if it might have replaced a previous entry,
   false if not. */
static bool
add_entry(x86_tlb_impl_t *rt, x86_tlb_entry_t *e)
{
        uint64 laddr = e->linear_page_start;
        unsigned size = e->attrs.page_size_k << 10;

        bool replaced = false;
        bool nonglobal = !e->attrs.global_page;

        e4_t *e4 = ENTRY_PTR(e4_t, rt->root);
        if (!e4) {
                e4 = MM_ZALLOC(512, e4_t);
                rt->root = MK_ENTRY_PTR(e4_t, e4, nonglobal);
        } else if (nonglobal)
                rt->root = MK_ENTRY_PTR(e4_t, e4, true);
        
        unsigned e4_idx = (laddr >> 39) & 511;
        e3_t *e3 = ENTRY_PTR(e3_t, e4[e4_idx]);
        if (!e3) {
                e3 = MM_ZALLOC(512, e3_t);
                e4[e4_idx] = MK_ENTRY_PTR(e3_t, e3, nonglobal);
        } else if (nonglobal)
                e4[e4_idx] = MK_ENTRY_PTR(e3_t, e3, true);

        unsigned e3_idx = (laddr >> 30) & 511;
        e3_t e3e = e3[e3_idx];
        if (size == 1 << 30) {
                if (!IS_NULL(e2_t, e3e)) {
                        replaced = true;
                        destroy_e3(&e3[e3_idx]);
                }
                e3[e3_idx] = MK_ENTRY_PAGE(e2_t, make_tlbe(
                        e->physical_page_start,
                        e->attrs.global_page, false,
                        e->attrs.mtrr_type, e->attrs.pat_type,
                        e->attrs.user_access, e->attrs.supervisor_access));
                return replaced;
        }
        e2_t *e2 = ENTRY_PTR(e2_t, e3e);
        if (!e2 || IS_PAGE(e2_t, e3e)) {
                if (IS_PAGE(e2_t, e3e))
                        replaced = true;
                e2 = MM_ZALLOC(512, e2_t);
                e3[e3_idx] = MK_ENTRY_PTR(e2_t, e2, nonglobal);
        } else if (nonglobal)
                e3[e3_idx] = MK_ENTRY_PTR(e2_t, e2, true);

        unsigned e2_idx = (laddr >> 21) & 511;
        e2_t e2e = e2[e2_idx];
        if (size & (1 << 21 | 1 << 22)) {
                bool page_4m = (size == 1 << 22);
                if (!IS_NULL(e1_t, e2e)) {
                        replaced = true;
                        destroy_e2(&e2[e2_idx]);
                }
                e2[e2_idx] = MK_ENTRY_PAGE(e1_t, make_tlbe(
                        e->physical_page_start,
                        e->attrs.global_page, page_4m,
                        e->attrs.mtrr_type, e->attrs.pat_type,
                        e->attrs.user_access, e->attrs.supervisor_access));
                if (page_4m) {
                        /* Put another 2 MiB page just after the first. */
                        e2_t e2e_2 = e2[e2_idx + 1];
                        if (!IS_NULL(e1_t, e2e_2)) {
                                replaced = true;
                                destroy_e2(&e2[e2_idx + 1]);
                        }
                        e2[e2_idx + 1] = MK_ENTRY_PAGE(e1_t, make_tlbe(
                             e->physical_page_start + (1 << 21),
                             e->attrs.global_page, true,
                             e->attrs.mtrr_type, e->attrs.pat_type,
                             e->attrs.user_access, e->attrs.supervisor_access));
                }
                return replaced;
        }
        e1_t *e1 = ENTRY_PTR(e1_t, e2[e2_idx]);
        if (!e1 || IS_PAGE(e1_t, e2e)) {
                if (IS_PAGE(e1_t, e2e)) {
                        /* Setting a small page where we had a 4 MiB page
                           removes both the 2 MiB entries. */
                        e2[e2_idx ^ 1] = MK_ENTRY_NULL(e1_t);
                        replaced = true;
                }
                e1 = MM_ZALLOC(512, e1_t);
                e2[e2_idx] = MK_ENTRY_PTR(e1_t, e1, nonglobal);
        } else if (nonglobal)
                e2[e2_idx] = MK_ENTRY_PTR(e1_t, e1, true);

        unsigned e1_idx = (laddr >> 12) & 511;
        e1_t e1e = e1[e1_idx];
        if (IS_PAGE(leaf, e1e))
                replaced = true;
        e1[e1_idx] = MK_ENTRY_PAGE(leaf, make_tlbe(
                e->physical_page_start,
                e->attrs.global_page, false,
                e->attrs.mtrr_type, e->attrs.pat_type,
                e->attrs.user_access, e->attrs.supervisor_access));
        return replaced;
}

void
rt_add(x86_tlb_t *tlb, x86_tlb_entry_t *e)
{
        if (add_entry(tlb->imp, e)) {
                /* Apparently we are responsible for invalidating the
                   STC for entries that were evicted, so do that. */
                SIM_flush_D_STC_logical(
                        tlb->cpu, e->linear_page_start,
                        e->attrs.page_size_k << 10);
                SIM_flush_I_STC_logical(
                        tlb->cpu, e->linear_page_start,
                        e->attrs.page_size_k << 10);
        }

        /* This is even more baroque. */
        data_or_instr_t tlb_select = 
                select_from_access(e->attrs.supervisor_access
                                   | e->attrs.user_access);
        int page_code = size_k_to_page_code(e->attrs.page_size_k);
        SIM_c_hap_occurred_always(
                x86_hap_tlb_fill[tlb_select],
                &tlb->obj, page_code,
                e->linear_page_start,
                e->physical_page_start,
                (int64)page_code);
}

set_error_t
rt_attr_set(x86_tlb_t *tlb, attr_value_t *val)
{
        x86_tlb_impl_t *rt = tlb->imp;
        destroy_root(rt);
        for (int i = 0; i < SIM_attr_list_size(*val); i++) {
                attr_value_t a = SIM_attr_list_item(*val, i);
                x86_tlb_entry_t e;
                if (!tlb_entry_from_attr(&e, &a))
                        return Sim_Set_Illegal_Value;
                add_entry(rt, &e);
        }
        return Sim_Set_Ok;

}

static attr_value_t
tlbe_to_attr(tlbe_t tlbe, uint64 laddr, unsigned pagesize)
{
        x86_tlb_entry_t e;
        tlbe_to_retval(&e, tlbe, laddr, pagesize);
        return attr_from_tlb_entry(&e);
}

typedef VECT(attr_value_t) attr_vect_t;

static attr_vect_t
tlbes_to_attrs(x86_tlb_impl_t *rt)
{
        attr_vect_t v = VNULL;
        e4_t *e4 = ENTRY_PTR(e4_t, rt->root);
        if (!e4)
                return v;
        for (int i = 0; i < 512; i++) {
                e3_t *e3 = ENTRY_PTR(e3_t, e4[i]);
                if (!e3)
                        continue;
                for (int j = 0; j < 512; j++) {
                        e3_t e3e = e3[j];
                        if (IS_PAGE(e2_t, e3e)) {
                                attr_value_t a = tlbe_to_attr(
                                        ENTRY_TLB(e2_t, e3e),
                                        (uint64)i << 39 | (uint64)j << 30,
                                        1 << 30);
                                VADD(v, a);
                                continue;
                        }
                        e2_t *e2 = ENTRY_PTR(e2_t, e3e);
                        if (!e2)
                                continue;
                        for (int k = 0; k < 512; k++) {
                                e2_t e2e = e2[k];
                                if (IS_PAGE(e1_t, e2e)) {
                                        unsigned size = 1 << 21;
                                        if (tlbe_4m(ENTRY_TLB(e1_t, e2e))) {
                                                /* 4 MiB pages are represented
                                                   as pairs of 2 MiB pages;
                                                   skip the odd one. */
                                                if (k & 1)
                                                        continue;
                                                size = 1 << 22;
                                        }
                                        attr_value_t a = tlbe_to_attr(
                                                ENTRY_TLB(e1_t, e2e),
                                                (uint64)i << 39
                                                | (uint64)j << 30
                                                | k << 21,
                                                size);
                                        VADD(v, a);
                                        continue;
                                }
                                e1_t *e1 = ENTRY_PTR(e1_t, e2e);
                                if (!e1)
                                        continue;
                                for (int m = 0; m < 512; m++) {
                                        e1_t e1e = e1[m];
                                        if (!IS_PAGE(leaf, e1e))
                                                continue;
                                        attr_value_t a = tlbe_to_attr(
                                                ENTRY_TLB(leaf, e1e),
                                                (uint64)i << 39
                                                | (uint64)j << 30
                                                | k << 21
                                                | m << 12,
                                                1 << 12);
                                        VADD(v, a);
                                }
                        }
                }
        }
        return v;
}

attr_value_t
rt_attr_get(x86_tlb_t *tlb)
{
        x86_tlb_impl_t *rt = tlb->imp;
        attr_vect_t v = tlbes_to_attrs(rt);
        attr_value_t ret = SIM_alloc_attr_list(VLEN(v));
        for (int i = 0; i < VLEN(v); i++)
                SIM_attr_list_set_item(&ret, i, VGET(v, i));
        VFREE(v);
        return ret;
}
