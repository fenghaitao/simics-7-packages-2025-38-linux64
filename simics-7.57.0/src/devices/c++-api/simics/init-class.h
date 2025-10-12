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

#ifndef SIMICS_INIT_CLASS_H
#define SIMICS_INIT_CLASS_H

#include <type_traits>

namespace simics {

class ConfClass;

namespace detail {

template<class ...Ts>
struct Voider {
    using type = void;
};

// General case when init_class is not declared in T
template<typename T, typename = void>
struct has_init_class : std::false_type {};
// Special case when init_class is declared in T
template<typename T>
struct has_init_class<T, typename Voider<decltype(T::init_class)>::type>
    : std::true_type {};

// When init_class is not declared in T
template <class T>
typename std::enable_if<!has_init_class<T>::value>::type
init_class(ConfClass *) {}
// When init_class is declared in T
template <class T>
typename std::enable_if<has_init_class<T>::value>::type
init_class(ConfClass *cls) {
    T::init_class(cls);
}

}  // namespace detail
}  // namespace simics

#endif
