// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2022 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef SIMICS_TYPE_FIELD_TYPE_H
#define SIMICS_TYPE_FIELD_TYPE_H

#include <tuple>

#include "simics/type/common-types.h"

namespace simics {
/*
 * Type alias represents a type containing field information
 *
 * It is a tuple consists of following members:
 *
 * 1. A name of the field. The name should follow
 *    the Simics naming rules. To indicate an array, similar to a C array,
 *    specify the number of fields between a pair of square brackets,
 *    e.g., f[8]. By default the stride of the array is the size of the
 *    field, but other values can be chosen as follows, f[8 stride 4].
 * 2. A human-readable description of the field
 * 3. An address offset of the field relative to its enclosing register
 * 4. An nonzero number of bits of the field
 */
using field_t = std::tuple<Name, Description, Offset, BitWidth>;
}  // namespace simics

#endif
