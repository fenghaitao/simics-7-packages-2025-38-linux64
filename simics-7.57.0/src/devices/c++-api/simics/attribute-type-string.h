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

#ifndef SIMICS_ATTRIBUTE_TYPE_STRING_H
#define SIMICS_ATTRIBUTE_TYPE_STRING_H

#include <array>
#include <deque>
#include <list>
#include <map>
#include <set>
#include <string>
#include <typeindex>
#include <typeinfo>
#include <tuple>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

#include "simics/conf-object.h"

namespace simics {
namespace detail {

const std::unordered_map<std::type_index, const std::string> type_strs {
    {std::type_index(typeid(bool)), "b"},
    {std::type_index(typeid(char)), "i"},
    {std::type_index(typeid(signed char)), "i"},
    {std::type_index(typeid(unsigned char)), "i"},
    {std::type_index(typeid(short)), "i"},  // NOLINT(runtime/int)
    {std::type_index(typeid(unsigned short)), "i"},  // NOLINT(runtime/int)
    {std::type_index(typeid(int)), "i"},
    {std::type_index(typeid(unsigned int)), "i"},
    {std::type_index(typeid(long int)), "i"},  // NOLINT(runtime/int)
    {std::type_index(typeid(unsigned long int)), "i"},  // NOLINT(runtime/int)
    {std::type_index(typeid(long long int)), "i"},  // NOLINT(runtime/int)
    {std::type_index(typeid(unsigned long long int)),  // NOLINT(runtime/int)
     "i"},
    {std::type_index(typeid(float)), "f"},
    {std::type_index(typeid(double)), "f"},
    {std::type_index(typeid(simics::ConfObjectRef)), "[os]|o|n"},
    {std::type_index(typeid(std::string)), "s"},
    {std::type_index(typeid(const char *)), "s|n"},
    {std::type_index(typeid(attr_value_t)), "a"},
};

template <typename T>
struct attr_type_str_helper {
    static std::string f() { return type_strs.at(std::type_index(typeid(T))); }
};

}  // namespace detail

template <typename T>
inline std::string attr_type_str() {
    static_assert(!std::is_member_pointer<T>::value,
                  "Use Foo::bar instead of &Foo::bar");
    static_assert(!std::is_function<T>::value,
                  "Function type is not supported");
    return detail::attr_type_str_helper<T>::f();
}

namespace detail {

template <typename X, typename Y>
struct attr_type_str_helper<std::pair<X, Y>> {
    static std::string f() {
        return std::string("[") + attr_type_str<X>() + attr_type_str<Y>() + "]";
    }
};

template <typename X, typename Y>
struct attr_type_str_helper<std::map<X, Y>> {
    static std::string f() {
        return std::string("[") + attr_type_str<std::pair<X, Y>>() + "*]";
    }
};

template <typename T, std::size_t N>
struct attr_type_str_helper<std::array<T, N>> {
    static std::string f() {
        return std::string("[") + attr_type_str<T>() + "{" \
            + std::to_string(N) + "}]";
    }
};

template <typename... Args>
struct attr_type_str_helper<std::tuple<Args...>> {
    static std::string f() {
        return "[" + type_str() + "]";
    }

  private:
    // Function to get the concatenated type string
    static std::string type_str() {
        return concat_types<Args...>();
    }

    // Helper function to concatenate type strings
    template <typename First, typename Second, typename ...Rest>
    static std::string concat_types() {
        return attr_type_str<First>() + concat_types<Second, Rest...>();
    }

    template <typename Last>
    static std::string concat_types() {
        return attr_type_str<Last>();
    }
};

template <typename T>
struct attr_list_type_str_helper {
    static std::string f() {
        return std::string("[") + attr_type_str<typename T::value_type>() + \
            "*]";
    }
};

#define _ATTR_LIST_TYPE_STR_HELPER(type)   \
    template <typename T>                  \
    struct attr_type_str_helper<type<T>> : \
        attr_list_type_str_helper<type<T>> {};

_ATTR_LIST_TYPE_STR_HELPER(std::deque)
_ATTR_LIST_TYPE_STR_HELPER(std::list)
_ATTR_LIST_TYPE_STR_HELPER(std::set)
_ATTR_LIST_TYPE_STR_HELPER(std::unordered_set)
_ATTR_LIST_TYPE_STR_HELPER(std::vector)
#undef _ATTR_LIST_TYPE_STR_HELPER

// Special handling for Simics data type
template <>
struct attr_type_str_helper< std::vector<uint8> > {
    static std::string f() {
        return "d";
    }
};

}  // namespace detail
}  // namespace simics

#endif
