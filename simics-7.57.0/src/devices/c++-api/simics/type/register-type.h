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

#ifndef SIMICS_TYPE_REGISTER_TYPE_H
#define SIMICS_TYPE_REGISTER_TYPE_H

#include <cstdint>
#include <tuple>
#include <vector>

#include "simics/type/common-types.h"
#include "simics/type/field-type.h"

namespace simics {
/*
 * Type alias represents a type containing register information
 *
 * It is a tuple consists of the following members:
 *
 * 1. A name of the register. The name should follow
 *    the Simics naming rules. To indicate an array, similar to a C array,
 *    specify the number of registers between a pair of square brackets,
 *    e.g., r[8]. By default the stride of the array is the size of the
 *    register, but other values can be chosen as follows, r[8 stride 4].
 * 2. A human-readable description of the register
 * 3. An address offset of the register relative to its enclosing bank
 * 4. An nonzero number of 8-bit bytes of the register
 * 5. An initial value of the register
 * 6. Optional fields information. An empty vector means no fields for
 *    the register.
 */
using register_t = std::tuple<Name, Description, Offset, ByteSize,
                              InitValue, std::vector<field_t>>;

/*
 * Type alias represents a type for register memory
 *
 * It's a vector consisting of byte pointers
 */
using register_memory_t = std::vector<uint8_t *>;

}  // namespace simics

#endif
