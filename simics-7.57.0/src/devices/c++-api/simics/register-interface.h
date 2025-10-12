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

#ifndef SIMICS_REGISTER_INTERFACE_H
#define SIMICS_REGISTER_INTERFACE_H

#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

#include "simics/conf-object.h"
#include "simics/type/common-types.h"
#include "simics/type/field-type.h"
#include "simics/type/register-type.h"
#include "simics/value-accessor-interface.h"
#include "simics/value-mutator-interface.h"

namespace simics {

class MappableConfObject;
class BankInterface;

class RegisterInterface : public ValueAccessorInterface,
                          public ValueMutatorInterface {
  public:
    virtual ~RegisterInterface() = default;

    /**
     * @brief Get the name of the register without level delimiters.
     *
     * @return A string view representing the register name only.
     */
    virtual std::string_view name() const = 0;

    /**
     * @brief Get the device object.
     *
     * @return A pointer to the MappableConfObject.
     */
    virtual MappableConfObject *dev_obj() const = 0;

    /**
     * @brief Get the description of the register.
     *
     * @return A reference to the string containing the register description.
     */
    virtual const std::string &description() const = 0;

    /**
     * @brief Get the full name of the register including bank name.
     *
     * @return A string view representing the full register name.
     */
    virtual const std::string &hierarchical_name() const = 0;

    /**
     * @brief Get the bank object.
     *
     * @return A ConfObjectRef to the bank object.
     */
    virtual ConfObjectRef bank_obj_ref() const = 0;

    /// @return the register size in bytes
    virtual unsigned number_of_bytes() const = 0;

    /**
     * @brief Initialize the register with a description, size in bytes and an initial
     *        value. Typically called after the register is instantiated.
     */
    virtual void init(Description desc, unsigned number_of_bytes,
                      uint64_t init_val) = 0;

    /**
     * @brief Reset to the initial value
     */
    virtual void reset() = 0;

    /// @return if the register is read-only
    virtual bool is_read_only() const = 0;

    /// @return if the register is mapped with an offset on the bank
    virtual bool is_mapped() const = 0;

    /**
     * @brief Parse the field information
     * 
     * Add the field or field array into the resource map. The field reuses
     * the memory allocated for the enclosing register.
     * offset 0 is always the least significant bit regardless of bit order
     * e.g.  2 bytes value 0b10100111
     *                       |      |
     *                  offset:7  offset:0  => width = 8
     */
    virtual void parse_field(const field_t &f) = 0;

    /**
     * @brief Add a field to the register
     */
    virtual void add_field(std::string_view field_name, std::string_view desc,
                           Offset offset, BitWidth width) = 0;

    /// @return information of fields in the register
    virtual std::vector<field_t> fields_info() const = 0;

    /// @return the parent bank interface
    virtual BankInterface *parent() const = 0;

    /**
     * @brief Set the byte address of the register
     */
    virtual void set_byte_pointers(
            const register_memory_t &byte_pointers) = 0;
};

}  // namespace simics

#endif
