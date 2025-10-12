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

#ifndef SIMICS_FIELD_H
#define SIMICS_FIELD_H

#include <cstddef>
#include <cstdint>
#include <string>

#include "simics/hierarchical-object.h"
#include "simics/field-interface.h"

namespace simics {

class MappableConfObject;
class RegisterInterface;

/**
 * @brief Base class to represent a Simics field
 *
 * Field with default behavior which allows access to any bit, without any
 * side-effects.
 */
class Field : public HierarchicalObject,
              public FieldInterface {
  public:
    // Construct from hierarchical name
    // @param name begins with the bank name, e.g, "bankA.registerB.fieldC"
    Field(MappableConfObject *dev_obj, const std::string &name);

    // No duplication
    Field(const Field&) = delete;
    Field& operator=(const Field&) = delete;

    Field(Field &&rhs);
    Field& operator=(Field&& rhs);

    virtual ~Field() = default;

    // FieldInterface
    std::string_view name() const override;
    const std::string &description() const override;
    unsigned number_of_bits() const override;
    void init(Description desc, const bits_type &bits,
              int8_t offset) override;
    RegisterInterface *parent() const override;

    uint64_t get() const override;

    void set(uint64_t value) override;

    uint64_t read(uint64_t enabled_bits) override;

    void write(uint64_t value, uint64_t enabled_bits) override;

    size_t offset() const;

    // Set the bits for this field. They are references to the bits
    // in the corresponding register
    void set_bits(const bits_type &bits);

  protected:
    /// @deprecated Used previously for construct from RegisterField but
    /// not needed now
    Field(RegisterInterface *parent, std::string_view field_name);

  private:
    /// Associate the hierarchical name with the current FieldInterface
    void set_iface();

    // The bits are represented by the byte pointer and bits mask see @bits_type
    // The first bit corresponds to the least significant digit of
    // the value and the last bit corresponds to the most significant digit
    bits_type bits_;
    // The number of total bits of the field
    std::uint8_t number_of_bits_ {0};
    // The offset of the first bit in containing register
    std::int8_t offset_ {-1};

    // The parent interface
    RegisterInterface *parent_ {nullptr};
};

}  // namespace simics

#endif
