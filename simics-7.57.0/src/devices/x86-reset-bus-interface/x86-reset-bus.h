/*
  © 2010 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef X86_RESET_BUS_H
#define X86_RESET_BUS_H

#include <simics/pywrap.h>
#include <simics/base/conf-object.h>

#if defined(__cplusplus)
extern "C" {
#endif

SIM_INTERFACE(x86_reset_bus) {
        void (*set_a20_line)(conf_object_t *obj, int value);
        int (*get_a20_line)(conf_object_t *obj);
        void (*reset_all)(conf_object_t *obj);
        void (*assert_reset)(conf_object_t *obj, int type);
        void (*disable_cpus)(conf_object_t *obj);
        void (*enable_cpu)(conf_object_t *obj, int value);
};

#define X86_RESET_BUS_INTERFACE "x86_reset_bus"

#if defined(__cplusplus)
}
#endif
#endif /* X86_RESET_BUS_H */
