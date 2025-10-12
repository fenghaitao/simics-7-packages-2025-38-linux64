// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2021 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef SIMICS_PORT_H
#define SIMICS_PORT_H

#include <stdexcept>
#include <string>

#include "simics/conf-object.h"
#include "simics/utility.h"  // array_index

namespace simics {

/**
 * @brief Extends ConfObject to add utilities to a Simics port object
 * 
 * A class inherited the ConfObject class can be registered as a port object.
 * A port object is a child object of a parent object, which is created
 * automatically together with its parent object. This class provides utilities
 * to access the parent object and the index of the port object array.
 *
 * @tparam TParent The parent class of the port object
 * TParent is the template class typename for Port, typically representing the
 * C++ class of the port's parent. A complete definition of TParent is
 * necessary, so it is advisable to define the port class after the TParent
 * class or as an inner class within TParent to ensure proper access to its
 * private members. If the port class does not need to access the parent's
 * class members, you can use ConfObject as TParent to eliminate dependencies
 * on the parent C++ class. Or simply use ConfObject as the parent class.
 */
template <typename TParent>
class Port : public ConfObject {
  public:
    using ParentType = TParent;

    explicit Port(const ConfObjectRef &obj)
        : ConfObject(obj) {
        if (obj.object() == nullptr) {
            throw std::invalid_argument(
                "ConfObjectRef passed to Port constructor is null");
        }

        parent_ = from_obj<ParentType>(parent_conf_obj());
        name_ = obj.name().substr(
            strlen(SIM_object_name(parent_conf_obj())) + 1);
        index_ = array_index(name_);
    }
    virtual ~Port() = default;

    /// @return a pointer to the C++ object associated with
    ///         the Simics parent object
    ParentType *parent() const {
        return parent_;
    }

    /// @return the name of the port only
    const std::string &name() const {
        return name_;
    }

    /// @return the index of port object array
    /// Returns -1 if the port object is not an array or has invalid index
    int index() const {
        return index_;
    }

  private:
    /// @return the Simics parent configuration object
    conf_object_t *parent_conf_obj() {
        auto p = SIM_port_object_parent(obj());
        if (p == nullptr) {
            throw std::runtime_error {
                "The object " + obj().name() + " is not a port object"
            };
        }
        return p;
    }

    /// Pointer to the parent object
    TParent *parent_ {nullptr};
    /// The name of the port only without the parent object name
    std::string name_ {""};
    /// The index if an array like name is provided, otherwise -1
    int index_ {-1};
};

}  // namespace simics

#endif
