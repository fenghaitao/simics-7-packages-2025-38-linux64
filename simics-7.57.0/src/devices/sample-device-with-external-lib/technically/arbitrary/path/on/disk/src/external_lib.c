/* external_lib.c - Trivial example of external library code

  © 2022 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include "external_lib.h"

uint64_t external_helper_function(uint64_t val) {
    return ((val >> 32) & 0xffffffff) + ((val & 0xffffffff) << 32);
}
