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

#ifndef SIMICS_DETAIL_ATTRIBUTE_GETTER_H
#define SIMICS_DETAIL_ATTRIBUTE_GETTER_H

#include "simics/attribute-traits.h"  // std_to_attr
#include "simics/conf-object.h"  // from_obj

namespace simics {
namespace detail {

template <typename T> struct attr_getter_helper;
template <typename T, typename O> struct attr_getter_helper_dual;

/*
 * Returns a functor of type attr_value_t serving as a wrapper for a given
 * pointer to a class member/method or a function takes a class as parameter.
 *
 * The macro uses simics::attr_getter_helper template, which implements
 * wrapper functions for member functions with different signatures.
 *
 * Wrapper for these signatures uses simics::std_to_attr to convert a standard
 * C++ type value into resulting attr_value_t. The conversion is not expected
 * to fail.
 */
#define _G_SINGLE(func_ptr) \
    simics::detail::attr_getter_helper<decltype(&func_ptr)>::\
    template f<&func_ptr>
#define _G_DUAL(cls, m) \
    simics::detail::attr_getter_helper_dual<decltype(&cls::m), cls>::\
    template f<&cls::m>

// For class member function pointer
template <typename O, typename T>
struct attr_getter_helper<T (O::*)()> {
    // Always fail. Use two arguments version instead
    static_assert(sizeof(T) == -1,
                  "Pass class member pointer as two arguments to the MACRO:"
                  " cls and member");
};

template <typename O, typename T>
struct attr_getter_helper<T (O::*)() const> {
    // Always fail. Use two arguments version instead
    static_assert(sizeof(T) == -1,
                  "Pass class member pointer as two arguments to the MACRO:"
                  " cls and member");
};

// When C differs than O, it means the getter is registered in the base
// class O, while the attribute is registered with derived class C
template <typename T, typename O, typename C>
struct attr_getter_helper_dual<T (O::*)(), C> {
    static_assert(std::is_base_of<O, C>::value,
                  "Type C should be same as or derived from type O");

    template <T (O::*F)()>
    static attr_value_t f(conf_object_t *obj) {
        return std_to_attr((from_obj<C>(obj)->*F)());
    }
};

template <typename T, typename O, typename C>
struct attr_getter_helper_dual<T (O::*)() const, C> {
    static_assert(std::is_base_of<O, C>::value,
                  "Type C should be same as or derived from type O");

    template <T (O::*F)() const>
    static attr_value_t f(conf_object_t *obj) {
        return std_to_attr((from_obj<C>(obj)->*F)());
    }
};

// For class member variable pointer
template <typename T, typename O>
struct attr_getter_helper<T O::*> {
    // Always fail. Use two arguments version instead
    static_assert(sizeof(T) == -1,
                  "Pass class member pointer as two arguments to the MACRO:"
                  " cls and member");
};

template <typename T, typename O, typename C>
struct attr_getter_helper_dual<T O::*, C> {
    static_assert(std::is_base_of<O, C>::value,
                  "Type C should be same as or derived from type O");

    template <T O::*R>
    static attr_value_t f(conf_object_t *obj) {
        return std_to_attr(from_obj<C>(obj)->*R);
    }
};

// For normal functions take an object reference
template <typename O, typename T>
struct attr_getter_helper<T& (*)(O&)> {
    template <T& (*F)(O&)>
    static attr_value_t f(conf_object_t *obj) {
        return std_to_attr(F(*from_obj<O>(obj)));
    }
};

template <typename O, typename T>
struct attr_getter_helper<T (*)(O&)> {
    template <T (*F)(O&)>
    static attr_value_t f(conf_object_t *obj) {
        return std_to_attr(F(*from_obj<O>(obj)));
    }
};

}  // namespace detail
}  // namespace simics

#endif
