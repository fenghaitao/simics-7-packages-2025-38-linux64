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

#ifndef SIMICS_FIELD_INTERFACE_H
#define SIMICS_FIELD_INTERFACE_H

#include <cstdint>
#include <string>
#include <string_view>
#include <utility>  // pair
#include <vector>

#include "simics/type/common-types.h"  // Description
#include "simics/value-accessor-interface.h"
#include "simics/value-mutator-interface.h"

namespace simics {
// Byte pointer and bits mask
using bits_type = std::vector<std::pair<uint8_t *, uint8_t>>;
class RegisterInterface;

class FieldInterface : public ValueAccessorInterface,
                       public ValueMutatorInterface {
  public:
    virtual ~FieldInterface() = default;

    /**
     * @brief Get the name of the field without level delimiters.
     *
     * @return A string view representing the field name only.
     */
    virtual std::string_view name() const = 0;

    /**
     * @brief Get the description of the field.
     *
     * @return A reference to the string containing the field description.
     */
    virtual const std::string &description() const = 0;

    /// @return the number of bits for this field
    virtual unsigned number_of_bits() const = 0;

    /**
     * @brief Initialize the field with a description, size in bits and an offset.
     *        Typically called after the field is instantiated.
     * @param offset is the offset of the first bit in the containing register
     */
    virtual void init(Description desc, const bits_type &bits,
                      int8_t offset) = 0;

    /// @return the parent register interface
    virtual RegisterInterface *parent() const = 0;
};

}  // namespace simics

#endif
