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

#ifndef SIMICS_HIERARCHICAL_OBJECT_INTERFACE_H
#define SIMICS_HIERARCHICAL_OBJECT_INTERFACE_H

#include <string>
#include <string_view>

#include "simics/conf-object.h"
#include "simics/type/common-types.h"  // Description

namespace simics {

class MappableConfObject;
class FieldInterface;
class RegisterInterface;
class BankInterface;

/**
 * @brief Enum representing the hierarchy level of an object.
 *
 * The Level enum is used to indicate the hierarchy level of an object
 * within a bank register model.
 */
enum class Level {BANK = 0, REGISTER = 1, FIELD = 2};

/**
 * @brief Interface for hierarchical objects used in bank register modeling.
 *
 * The HierarchicalObjectInterface class provides an interface for objects
 * used in a bank register model. A register bank contains registers, and
 * each register can contain fields. This interface defines methods to
 * access the hierarchical name, description, and hierarchy level of the
 * object, as well as methods to access the associated device and bank
 * objects.
 */
class HierarchicalObjectInterface {
  public:
    /// @return the full name of the object starts with the bank name
    virtual const std::string &hierarchical_name() const = 0;
    /// @return the name of the object only
    virtual std::string_view name() const = 0;
    /// @return the description of the object
    virtual const std::string &description() const = 0;
    virtual void set_description(Description desc) = 0;
    /// @return the hierarchy level of the object
    virtual Level hierarchy_level() const = 0;
    /// @return the name of the bank where the hierarchical object starts with
    virtual std::string_view bank_name() const = 0;
    /// @return the device object holds the bank
    virtual MappableConfObject *dev_obj() const = 0;
    /// @return the bank ConfObjectRef that the hierarchical object
    /// associated with
    virtual ConfObjectRef bank_obj_ref() const = 0;
    /// @return the parent's hierarchical name
    virtual std::string_view parent_name() const = 0;
    /// @return the field interface according to a field name
    virtual FieldInterface *lookup_field(const std::string &name) const = 0;
    /// @return the register interface according to a register name
    virtual RegisterInterface *lookup_register(
            const std::string &name) const = 0;
    /// @return the bank interface according to a bank name
    virtual BankInterface *lookup_bank(const std::string &name) const = 0;
};

}  // namespace simics

#endif
