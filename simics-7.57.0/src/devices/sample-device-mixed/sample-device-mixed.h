/*
  sample-device-mixed.h - sample code for a mixed DML/C Simics device

  © 2010 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef SAMPLE_DEVICE_MIXED_H
#define SAMPLE_DEVICE_MIXED_H

#include <simics/device-api.h>

#ifdef __cplusplus
extern "C" {
#endif

    SIM_INTERFACE(myinterface) {
        void (*one)(conf_object_t *obj);
        void (*two)(conf_object_t *obj, uint32 count);
    };

    uint64 calculate_value_in_c(uint64 v);
    void call_out_to_c(conf_object_t *obj);

    // Wrapper for overloaded function
    uint64 calculate_value_in_cc_int(uint64 v);
    uint64 calculate_value_in_cc_float(float v);

    // Wrapper for class member function
    lang_void *create_myclass();
    void free_myclass(lang_void *c);
    void myclass_foo(lang_void *c, conf_object_t *obj);

#ifdef __cplusplus
}
#endif

#endif
