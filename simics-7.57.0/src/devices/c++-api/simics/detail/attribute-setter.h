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

#ifndef SIMICS_DETAIL_ATTRIBUTE_SETTER_H
#define SIMICS_DETAIL_ATTRIBUTE_SETTER_H

#include <simics/base/log.h>

#include <utility>  // move

#include "simics/attribute-traits.h"  // attr_to_std
#include "simics/conf-object.h"  // from_obj

namespace simics {
namespace detail {

template <typename T> struct attr_setter_helper;
template <typename T, typename O> struct attr_setter_helper_dual;

/*
 * Returns a functor of type set_attr_t serving as a wrapper for a given
 * pointer to a class member/method.
 *
 * The macro uses simics::attr_setter_helper template, which implements
 * wrapper functions for member.
 *
 * Wrapper uses simics::attr_to_std to convert attr_value_t into a standard
 * C++ type value. If conversion fails, wrapper catches exception and returns
 * proper value of type set_error_t.
 */
#define _S_SINGLE(func_ptr) \
    simics::detail::attr_setter_helper<decltype(&func_ptr)>::\
    template f<&func_ptr>
#define _S_DUAL(cls, m) \
    simics::detail::attr_setter_helper_dual<decltype(&cls::m), cls>::\
    template f<&cls::m>

inline set_error_t handle_exception(const std::exception &e) {
    SIM_attribute_error(e.what());
    if (dynamic_cast<const SetInterfaceNotFound *>(&e)) {
        return Sim_Set_Interface_Not_Found;
    } else if (dynamic_cast<const SetIllegalType *>(&e)) {
        return Sim_Set_Illegal_Type;
    } else if (dynamic_cast<const SetNotWritable *>(&e)) {
        return Sim_Set_Not_Writable;
    } else {
        return Sim_Set_Illegal_Value;
    }
}

// For class member function pointer
template <typename O, typename T>
struct attr_setter_helper<void (O::*)(T)> {
    // Always fail. Use two arguments version instead
    static_assert(sizeof(T) == -1,
                  "Pass class member pointer as two arguments to the MACRO:"
                  " cls and member");
};

template <typename O, typename T>
struct attr_setter_helper<void (O::*)(T&)> {
    // Always fail. Use two arguments version instead
    static_assert(sizeof(T) == -1,
                  "Pass class member pointer as two arguments to the MACRO:"
                  " cls and member");
};

template <typename O, typename T, typename C>
struct attr_setter_helper_dual<void (O::*)(T), C> {
    static_assert(std::is_base_of<O, C>::value, "C must be derived from O");
    template <void (O::*F)(T)>
    static set_error_t f(conf_object_t *obj, attr_value_t *val) {
        O *o = static_cast<O*>(from_obj<C>(obj));
        try {
            (o->*F)(attr_to_std<std::remove_cv_t<T>>(*val));
        } catch (const std::exception &e) {
            return handle_exception(e);
        }
        return Sim_Set_Ok;
    }
};

template <typename O, typename T, typename C>
struct attr_setter_helper_dual<void (O::*)(T&), C> {
    template <void (O::*F)(T&)>
    static set_error_t f(conf_object_t *obj, attr_value_t *val) {
        C *o = from_obj<C>(obj);
        try {
            T tval = attr_to_std<T>(*val);
            (o->*F)(tval);
        } catch (const std::exception &e) {
            return handle_exception(e);
        }
        return Sim_Set_Ok;
    }
};

// For class member variable pointer
template <typename O, typename T>
struct attr_setter_helper<T O::*> {
    // Always fail. Use two arguments version instead
    static_assert(sizeof(T) == -1,
                  "Pass class member pointer as two arguments to the MACRO:"
                  " cls and member");
};

template <typename O, typename T, typename C>
struct attr_setter_helper_dual<T O::*, C> {
    // If T is derived from ConnectBase, use set instead of =
    template <T O::*R, typename T1 = T> static
    typename std::enable_if<std::is_base_of<ConnectBase, T1>::value,
                            set_error_t>::type
    f(conf_object_t *obj, attr_value_t *val) {
        C *o = from_obj<C>(obj);
        if ((o->*R).set(attr_to_std<ConfObjectRef>(*val)) == false) {
            return Sim_Set_Interface_Not_Found;
        }
        return Sim_Set_Ok;
    }

    // If T is a std::array and the value_type is derived from ConnectBase,
    // assign the new value use set for each member
    template <T O::*R, typename T1 = T> static
    typename std::enable_if<is_array_of_connectbase<T1>::value,
                            set_error_t>::type
    f(conf_object_t *obj, attr_value_t *val) {
        C *o = from_obj<C>(obj);
        auto it = (o->*R).begin();
        for (unsigned i = 0; it != (o->*R).end(); ++i, ++it) {
            if (it->set(attr_to_std<ConfObjectRef>(
                                SIM_attr_list_item(*val, i))) == false) {
                return Sim_Set_Interface_Not_Found;
            }
        }
        return Sim_Set_Ok;
    }

    // If T is a variable length container and the value_type is derived
    // from ConnectBase, construct a new T
    template <T O::*R, typename T1 = T> static
    typename std::enable_if<is_container_of_connectbase<T1>::value,
                            set_error_t>::type
    f(conf_object_t *obj, attr_value_t *val) {
        C *o = from_obj<C>(obj);
        T new_t(SIM_attr_list_size(*val), typename T::value_type(obj));
        auto it = new_t.begin();
        for (unsigned i = 0; it != new_t.end(); ++i, ++it) {
            if (it->set(attr_to_std<ConfObjectRef>(
                                SIM_attr_list_item(*val, i))) == false) {
                return Sim_Set_Interface_Not_Found;
            }
        }
        o->*R = std::move(new_t);
        return Sim_Set_Ok;
    }

    // For all other types
    template <T O::*R, typename T1 = T> static
    typename std::enable_if<!is_container_of_connectbase<T1>::value
                            && !is_array_of_connectbase<T1>::value
                            && !std::is_base_of<ConnectBase, T1>::value,
                            set_error_t>::type
    f(conf_object_t *obj, attr_value_t *val) {
        C *o = from_obj<C>(obj);
        try {
            o->*R = attr_to_std<T>(*val);
        } catch (const std::exception &e) {
            return handle_exception(e);
        }
        return Sim_Set_Ok;
    }
};

// For normal functions take an object reference
template <typename O, typename T>
struct attr_setter_helper<void (*)(O&, T&)> {
    template <void (*F)(O&, T&)>
    static set_error_t f(conf_object_t *obj, attr_value_t *val) {
        O *o = from_obj<O>(obj);
        try {
            F(*o, attr_to_std<std::remove_cv_t<T>>(*val));
        } catch (const std::exception &e) {
            return handle_exception(e);
        }
        return Sim_Set_Ok;
    }
};

// For normal functions take an object value
template <typename O, typename T>
struct attr_setter_helper<void (*)(O&, T)> {
    template <void (*F)(O&, T)>
    static set_error_t f(conf_object_t *obj, attr_value_t *val) {
        O *o = from_obj<O>(obj);
        try {
            F(*o, attr_to_std<std::remove_cv_t<T>>(*val));
        } catch (const std::exception &e) {
            return handle_exception(e);
        }
        return Sim_Set_Ok;
    }
};

template <typename O, typename T>
struct attr_setter_helper<T& (*)(O&)> {
    template <T& (*F)(O&)>
    static set_error_t f(conf_object_t *obj, attr_value_t *val) {
        O *o = from_obj<O>(obj);
        try {
            F(*o) = attr_to_std<T>(*val);
        } catch (const std::exception &e) {
            return handle_exception(e);
        }
        return Sim_Set_Ok;
    }
};

}  // namespace detail
}  // namespace simics

#endif
