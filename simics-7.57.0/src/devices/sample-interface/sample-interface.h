/*
  sample-interface.h - sample new interface type definition

  © 2010 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

/* This module is an example of defining a new interface type. See the
   "Defining a New Interface Type" section of the
   "Simics Model Builder User's Guide" for further documentation.

   The corresponding DML definition can be found in
   sample-interface.dml */

#ifndef SAMPLE_INTERFACE_H
#define SAMPLE_INTERFACE_H

#include <simics/device-api.h>
#include <simics/pywrap.h>

//:: pre sample_interface_c_header {{
#if defined(__cplusplus)
extern "C" {
#endif

/* This defines a new interface type. Its corresponding C data type
   will be called "sample_interface_t". */
SIM_INTERFACE(sample) {
    void (*simple_method)(conf_object_t *obj, int arg);
    void (*object_method)(conf_object_t *obj, conf_object_t *arg);
};

/* Use a #define like this whenever you need to use the name of the
   interface type; the C compiler will then catch any typos at
   compile-time. */
#define SAMPLE_INTERFACE "sample"

#if defined(__cplusplus)
}
#endif
// }}

#endif /* ! SAMPLE_INTERFACE_H */
