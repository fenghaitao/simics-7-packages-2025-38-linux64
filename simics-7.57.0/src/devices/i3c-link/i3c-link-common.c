/*
  © 2017 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include "simics/devs/liblink.h"

void init_i3c_link();
void init_i3c_cable(void );

void
init_local()
{
        SIMLINK_init_library();
        init_i3c_link();
        init_i3c_cable();
}
