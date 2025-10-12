/*
  x86_tlb.h

  © 2010 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef X86_TLB_H
#define X86_TLB_H

#include <simics/device-api.h>
#include <simics/arch/x86.h>
#if defined(__cplusplus)
extern "C" {
#endif

#define TLB_WAYS 2 /* instruction or data */

extern hap_type_t x86_hap_tlb_invalidate[TLB_WAYS];
extern hap_type_t x86_hap_tlb_replace[TLB_WAYS];
extern hap_type_t x86_hap_tlb_fill[TLB_WAYS];
extern hap_type_t x86_hap_tlb_miss[TLB_WAYS];

typedef struct x86_tlb_impl x86_tlb_impl_t;

typedef struct x86_tlb
{
        conf_object_t obj;
        conf_object_t          *cpu;

        x86_tlb_impl_t         *imp;

        /* A value to be returned from lookup, only valid until the next
           call. */
        x86_tlb_entry_v3_t     retval_v3;
} x86_tlb_t;

bool tlb_entry_from_attr(x86_tlb_entry_t *e, attr_value_t *a);
attr_value_t attr_from_tlb_entry(x86_tlb_entry_t *entry);
int size_k_to_page_code(int page_size_k);
data_or_instr_t select_from_access(access_t access);

#if defined(__cplusplus)
}
#endif
#endif // X86_TLB_H
