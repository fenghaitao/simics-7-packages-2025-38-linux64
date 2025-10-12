/*
  © 2021 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

/*
----------------------------------------------------------------------------------

   The corresponding DML definition can be found in m_compute_control_interface.dml */

#ifndef M_COMPUTE_CONTROL_INTERFACE_H
#define M_COMPUTE_CONTROL_INTERFACE_H

#include <simics/device-api.h>
#include <simics/pywrap.h>

#ifdef __cplusplus
extern "C" {
#endif

/* This defines a new interface type. Its corresponding C data type will be
   called "m_compute_control_interface_t". */
SIM_INTERFACE(m_compute_control) {
    void (*start_operation)(conf_object_t *obj);
    void (*clear_done)(conf_object_t *obj);
};

/* Use a #define like this whenever you need to use the name of the interface
   type; the C compiler will then catch any typos at compile-time. */
#define M_COMPUTE_CONTROL_INTERFACE "m_compute_control"

#ifdef __cplusplus
}
#endif

#endif /* ! M_COMPUTE_CONTROL_INTERFACE_H */
