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

#ifndef SIMICS_REGISTER_H
#define SIMICS_REGISTER_H

#include <cstddef>
#include <cstdint>
#include <limits>
#include <map>
#include <memory>
#include <ostream>
#include <string>
#include <string_view>
#include <vector>

#include "simics/field-interface.h"
#include "simics/hierarchical-object.h"
#include "simics/register-interface.h"
#include "simics/type/common-types.h"  // Description
#include "simics/type/field-type.h"  // field_t
#include "simics/type/register-type.h"  // register_memory_t

namespace simics {

class BankInterface;
class MappableConfObject;

/**
 * @brief Base class to represent a Simics register
 *
 * Register with default behavior which allows access to any bit, without any
 * side-effects.
 */
class Register : public RegisterInterface,
                 public HierarchicalObject {
  public:
    /// @param dev_obj is the device object which contains the register
    /// @param hierarchical_name begins with the bank name,
    ///                          e.g, "bankA.registerB"
    Register(MappableConfObject *dev_obj,
             const std::string &hierarchical_name);

    // No duplication
    Register(const Register&) = delete;
    Register& operator=(const Register&) = delete;

    Register(Register &&rhs);
    Register& operator=(Register&& rhs);

    virtual ~Register() = default;

    friend std::ostream& operator<< (std::ostream& stream,
                                     const Register& reg);

    /// Utility function to get the offset of the register,
    /// returns size_t(-1) when register is not mapped
    static std::size_t offset(const RegisterInterface *reg_iface);

    std::string_view name() const override;

    const std::string &hierarchical_name() const override;

    const std::string &description() const override;

    MappableConfObject *dev_obj() const override;

    ConfObjectRef bank_obj_ref() const override;

    unsigned number_of_bytes() const override;

    void init(Description desc, unsigned number_of_bytes,
              uint64_t init_val) override;

    void reset() override;

    bool is_read_only() const override;

    bool is_mapped() const override;

    void set_byte_pointers(const register_memory_t &byte_pointers) override;

    uint64_t get() const override;

    void set(uint64_t value) override;

    uint64_t read(uint64_t enabled_bits) override;

    void write(uint64_t value, uint64_t enabled_bits) override;

    /*
     * Parse the field information, add the field or field array into
     * the resource map
     */
    void parse_field(const field_t &f) override;

    std::vector<field_t> fields_info() const override;

    BankInterface *parent() const override;

  protected:
    /// @deprecated Used previously for construct from BankRegister but
    /// not needed now
    Register(BankInterface *parent, std::string_view reg_name);

    // Add a single field into the resource map
    void add_field(std::string_view field_name, Description desc,
                   Offset offset, BitWidth width) override;

    // Set the initial value of the register
    void set_init_value(uint64_t init_val);

  private:
    static void add_register_as_simics_attribute(
            const RegisterInterface *iface);

    static attr_value_t get_reg_array(size_t indices, size_t dim_index,
                                      const MappableConfObject *obj,
                                      const std::string &base_name);

    static attr_value_t get_reg(conf_object_t *obj, void *data);

    static set_error_t set_reg_array(size_t indices, size_t dim_index,
                                     MappableConfObject *obj,
                                     const std::string &base_name,
                                     attr_value_t *val);

    static set_error_t set_reg(conf_object_t *obj, attr_value_t *val,
                               void *data);

    // Check the number_of_bytes from init method is valid
    void check_number_of_bytes(unsigned number_of_bytes);

    // Return if the input range overlaps with the existing field range
    bool has_range_overlap(size_t lsb, size_t msb) const;

    uint64_t read_from_byte_pointers() const;

    /// Associate the hierarchical name with the current RegisterInterface
    void set_iface();

    // The initial value after the register is created
    uint64_t init_val_ {0};
    // Used to mask the valid bytes when reading/writing the register
    uint64_t byte_mask_ {(std::numeric_limits<uint64_t>::max)()};
    // first bit of the byte corresponds to the least significant digit
    // of the number and the last bit corresponds to the most significant digit
    // i.e. Little-endian byte & bit order
    register_memory_t byte_pointers_;
    // The fields mapped on the register. Ordered by the lsb.
    std::map<size_t, FieldInterface *> fields_;
    // The parent interface
    BankInterface *parent_ {nullptr};
    // @internal: tracks the allocated fields
    std::vector<std::unique_ptr<FieldInterface>> allocated_fields_;
};

}  // namespace simics

#endif
