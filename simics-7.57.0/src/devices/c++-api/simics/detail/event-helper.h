// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2023 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef SIMICS_DETAIL_EVENT_HELPER_H
#define SIMICS_DETAIL_EVENT_HELPER_H

#include <simics/base/event.h>  // event_class_t

#include "simics/conf-object.h"  // from_obj

namespace simics {
namespace detail {

template <typename T, typename O> struct event_helper;

#define EVENT_HELPER(cls, m, f) \
    simics::detail::event_helper<decltype(&cls::m), cls>::template f<&cls::m>

#define EVENT_CALLBACK(cls, m) \
    simics::detail::event_helper<decltype(&cls::m), cls>::event_class_ptr(), \
    EVENT_HELPER(cls, m, callback)

#define EVENT_CLS_VAR(cls, m) \
    EVENT_CALLBACK(cls, m), EVENT_HELPER(cls, m, destroy), \
    EVENT_HELPER(cls, m, get_value), EVENT_HELPER(cls, m, set_value), \
    EVENT_HELPER(cls, m, describe)

template <typename T, typename O, typename C>
struct event_helper<T O::*, C> {
    template <T O::*R>
    static void callback(conf_object_t *obj, void *data) {
        (simics::from_obj<C>(obj)->*R).callback(data);
    }

    template <T O::*R>
    static void destroy(conf_object_t *obj, void *data) {
        (simics::from_obj<C>(obj)->*R).destroy(data);
    }

    template <T O::*R>
    static attr_value_t get_value(conf_object_t *obj, void *data) {
        return (simics::from_obj<C>(obj)->*R).get_value(data);
    }

    template <T O::*R>
    static void *set_value(conf_object_t *obj, attr_value_t value) {
        return (simics::from_obj<C>(obj)->*R).set_value(value);
    }

    template <T O::*R>
    static char *describe(conf_object_t *obj, void *data) {
        return (simics::from_obj<C>(obj)->*R).describe(data);
    }

    // SFINAE: return &T::event_cls if available, otherwise nullptr
    template <typename U>
    static auto event_class_ptr_impl(int) -> decltype(&U::event_cls) {
        return &U::event_cls;
    }
    template <typename U>
    static event_class_t **event_class_ptr_impl(...) {
        return nullptr;
    }
    static event_class_t **event_class_ptr() {
        return event_class_ptr_impl<T>(0);
    }
};

}  // namespace detail
}  // namespace simics

#endif
