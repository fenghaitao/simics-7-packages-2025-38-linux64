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

#ifndef SIMICS_ATTRIBUTE_H
#define SIMICS_ATTRIBUTE_H

#include <simics/base/conf-object.h>  // attr_attr_t

#include <string>
#include <type_traits>  // add_pointer_t

#include "simics/attribute-type-string.h"
#include "simics/detail/attribute-getter.h"
#include "simics/detail/attribute-setter.h"

/**
 * MACRO take either 1 or 2 arguments
 */
#define GET_MACRO(_1, _2, NAME, ...) NAME

/**
 * __VA_ARGS__ is treated as single parameter in MSVC, use this as a workaround
 */
#define IMPL(str) str

/**
 * MACROs convert the get/set function or variable access to function
 * attr_getter and attr_setter
 */
#define ATTR_GETTER(...) \
    IMPL(GET_MACRO(__VA_ARGS__, _G_DUAL, _G_SINGLE)(__VA_ARGS__))
#define ATTR_SETTER(...) \
    IMPL(GET_MACRO(__VA_ARGS__, _S_DUAL, _S_SINGLE)(__VA_ARGS__))
#define ATTR_CLS_VAR(CLASS, VAR)                                    \
    simics::AttributeAccessor<CLASS, decltype(&CLASS::VAR), &CLASS::VAR>()
/// Get the Simics attribute string from a variable's C++ type
#define ATTR_TYPE_STR(VAR) simics::attr_type_str<decltype(VAR)>()

namespace simics {

using attr_getter = std::add_pointer_t<attr_value_t(conf_object_t *)>;
using attr_setter = std::add_pointer_t<set_error_t(conf_object_t *,
                                                   attr_value_t *)>;

/**
 * A container of get and set callbacks for a class member variable
 */
template <typename CLASS, typename MEMBER, MEMBER m>
struct AttributeAccessor {
    static_assert(std::is_member_object_pointer<MEMBER>::value,
                  "type MEMBER is not a member object pointer type");

    AttributeAccessor()
        : getter(detail::attr_getter_helper_dual<
                 MEMBER, CLASS>::template f<m>),
          setter(detail::attr_setter_helper_dual<
                 MEMBER, CLASS>::template f<m>) {}

    attr_getter getter;
    attr_setter setter;
};

/**
 * Represents a Simics attribute
 *
 */
class Attribute {
  public:
    /**
     *
     * @see SIM_register_attribute
     * @param name the attribute name
     * @param type the attribute type string, see SIM_register_attribute
     * @param desc the attribute description
     * @param getter a callback to get the current value of the attribute
     * @param setter a callback to set the current value of the attribute
     * @param attr one of Sim_Attr_Required, Sim_Attr_Optional or
     *             Sim_Attr_Pseudo
     */
    Attribute(const std::string &name, const std::string &type,
              const std::string &desc, attr_getter getter, attr_setter setter,
              attr_attr_t attr)
        : name_(name), type_(type), desc_(desc), getter_(getter),
          setter_(setter), attr_(attr) {}

    Attribute(const std::string &name, const std::string &type,
              const std::string &desc, attr_getter getter, attr_setter setter)
        : Attribute(name, type, desc, getter, setter,
                    (getter && setter) ? Sim_Attr_Optional : Sim_Attr_Pseudo) {}

    /**
     * @param ref an AttributeAccessor class instance
     */
    template <typename CLASS, typename MEMBER, MEMBER m>
    Attribute(const std::string &name, const std::string &type,
              const std::string &desc, AttributeAccessor<CLASS, MEMBER, m> ref,
              attr_attr_t attr = Sim_Attr_Optional)
        : Attribute(name, type, desc, ref.getter, ref.setter, attr) {}

    virtual ~Attribute() = default;
    // destructor definition implicit deprecate move, force it here
    Attribute(Attribute&&) = default;

    virtual const std::string &name() const {
        return name_;
    }

    virtual const std::string &type() const {
        return type_;
    }

    virtual const std::string &desc() const {
        return desc_;
    }

    virtual attr_getter getter() const {
        return getter_;
    }

    virtual attr_setter setter() const {
        return setter_;
    }

    virtual attr_attr_t attr() const {
        return attr_;
    }

  private:
    std::string name_;
    std::string type_;
    std::string desc_;
    attr_getter getter_;
    attr_setter setter_;
    attr_attr_t attr_;
};

/**
 * Represents a Simics class attribute
 */
class ClassAttribute {
  public:
    using cls_attr_getter = std::add_pointer_t<attr_value_t(conf_class_t *)>;
    using cls_attr_setter = std::add_pointer_t<set_error_t(conf_class_t *,
                                                           attr_value_t *)>;
      /**
     *
     * @see SIM_register_class_attribute
     * @param name the attribute name
     * @param type the attribute type string, see SIM_register_class_attribute
     * @param desc the attribute description
     * @param getter a callback to get the current value of the attribute
     * @param setter a callback to set the current value of the attribute
     * @param attr one of Sim_Attr_Pseudo or Sim_Attr_Session
     */
    ClassAttribute(const std::string &name, const std::string &type,
                   const std::string &desc, cls_attr_getter getter,
                   cls_attr_setter setter, attr_attr_t attr)
        : name_(name), type_(type), desc_(desc), getter_(getter),
          setter_(setter), attr_(attr) {}

    virtual const std::string &name() const {
        return name_;
    }

    virtual const std::string &type() const {
        return type_;
    }

    virtual const std::string &desc() const {
        return desc_;
    }

    virtual cls_attr_getter getter() const {
        return getter_;
    }

    virtual cls_attr_setter setter() const {
        return setter_;
    }

    virtual attr_attr_t attr() const {
        return attr_;
    }

  private:
    std::string name_;
    std::string type_;
    std::string desc_;
    cls_attr_getter getter_;
    cls_attr_setter setter_;
    attr_attr_t attr_;
};

}  // namespace simics

#endif
