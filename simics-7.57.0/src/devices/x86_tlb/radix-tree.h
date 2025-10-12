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

#ifndef RADIX_TREE_H
#define RADIX_TREE_H

#include <simics/base/types.h>
#include <simics/base/conf-object.h>
#include <simics/processor/types.h>
#include <simics/arch/x86.h>

#ifdef __cplusplus
extern "C" {
#endif

struct x86_tlb;
void rt_enter_mode(struct x86_tlb *tlb);
void rt_leave_mode(struct x86_tlb *tlb);
void rt_flush_all(struct x86_tlb *tlb, int keep_global_entries);
void rt_flush_page(struct x86_tlb *tlb, linear_address_t laddr);
x86_tlb_entry_t *rt_lookup(struct x86_tlb *tlb, processor_mode_t mode,
                           access_t access, linear_address_t laddr,
                           linear_address_t *offset);
void rt_add(struct x86_tlb *tlb, x86_tlb_entry_t *e);
set_error_t rt_attr_set(struct x86_tlb *tlb, attr_value_t *val);
attr_value_t rt_attr_get(struct x86_tlb *tlb);

#ifdef __cplusplus
}
#endif

#endif
