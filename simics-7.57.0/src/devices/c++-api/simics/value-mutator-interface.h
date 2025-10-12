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

#ifndef SIMICS_VALUE_MUTATOR_INTERFACE_H
#define SIMICS_VALUE_MUTATOR_INTERFACE_H

#include <cstdint>

namespace simics {

// mutate value of a register/field
class ValueMutatorInterface {
  public:
    virtual ~ValueMutatorInterface() = default;

    // change value of a register or field, without side-effects. For
    // inspection and checkpointing.
    virtual void set(uint64_t value) = 0;

    // change value of a register or field, with side-effects. For
    // IO operation.
    virtual void write(uint64_t value, uint64_t enabled_bits) = 0;
};

}  // namespace simics

#endif
