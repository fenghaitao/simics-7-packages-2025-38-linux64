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

#ifndef SIMICS_ATTRIBUTE_TRAITS_H
#define SIMICS_ATTRIBUTE_TRAITS_H

#include <simics/base/attr-value.h>  // SIM_attr_list_item

#include <array>
#include <deque>
#include <limits>  // numeric_limits
#include <list>
#include <map>
#include <set>
#include <string>
#include <type_traits>  // is_enum, underlying_type_t, remove_cv_t
#include <tuple>
#include <utility>  // pair, index_sequence
#include <vector>

#include "simics/conf-object.h"
#include "simics/connect.h"  // ConnectBase

namespace simics {

/// The maximum supported size for a Simics attribute dictionary/list/data
/// is 2**32-1 bytes
inline void checkSizeOverflowSimicsAttribute(size_t size) {
    if (size > (std::numeric_limits<unsigned>::max)()) {
        throw detail::SetIllegalValue {
            "Size exceeds maximum supported size for a Simics attribute"
        };
    }
}

namespace detail {

template <typename T>
struct attr_from_std_helper {
    static_assert(!std::is_same<T, T>::value,
                  "Specialization of attr_to_std<T> & std_to_attr<T> for "
                  "type T is required.");
    static attr_value_t f(const T &src);
};

template <typename T>
struct attr_to_std_helper {
    static_assert(!std::is_same<T, T>::value,
                  "Specialization of attr_to_std<T> & std_to_attr<T> for "
                  "type T is required.");
    static T f(const attr_value_t &src);
};

// ConfObjectRef, needed by std_to_attr<T> when T is derived from ConnectBase
template <>
struct attr_from_std_helper<ConfObjectRef> {
    static attr_value_t f(const ConfObjectRef &src) {
        if (src) {
            if (src.port_name().empty()) {
                return SIM_make_attr_object(src);
            } else {
                attr_value_t ret = SIM_alloc_attr_list(2);
                SIM_attr_list_set_item(&ret, 0, SIM_make_attr_object(src));
                attr_value_t string = SIM_make_attr_string(
                        src.port_name().c_str());
                SIM_attr_list_set_item(&ret, 1, string);
                return ret;
            }
        } else {
            return SIM_make_attr_nil();
        }
    }
};

template <>
struct attr_to_std_helper<ConfObjectRef> {
    static ConfObjectRef f(const attr_value_t &src) {
        if (SIM_attr_is_list(src)) {
            if (SIM_attr_list_size(src) != 2) {
                throw SetIllegalType {
                    "Expected Simics list type with exactly 2 members"
                };
            }

            auto item = SIM_attr_list_item(src, 0);
            if (!SIM_attr_is_object(item)) {
                throw SetIllegalType {
                    "The first item should be Simics object type"
                };
            }
            ConfObjectRef r = SIM_attr_object(item);

            item = SIM_attr_list_item(src, 1);
            if (!SIM_attr_is_string(item)) {
                throw SetIllegalType {
                    "The second item should be Simics string type"
                };
            }
            r.set_port_name(SIM_attr_string(item));
            return r;
        } else {
            if (!SIM_attr_is_object(src) && !SIM_attr_is_nil(src)) {
                throw SetIllegalType {
                    "Expected Simics object or NIL type"
                };
            }
            return SIM_attr_object_or_nil(src);
        }
    }
};

template <typename T>
struct derived_from_connectbase_and_constructible_from_confobjectref {
  public:
    static constexpr bool value = std::is_base_of<ConnectBase, T>::value
        && std::is_constructible<T, const ConfObjectRef &>::value;
};

// Check if T is a variable length container type, and the value_type
// is derived from ConnectBase
template <typename T>
struct is_container_of_connectbase : std::false_type {};

template <typename T, typename Alloc>
struct is_container_of_connectbase<std::vector<T, Alloc>>
    : derived_from_connectbase_and_constructible_from_confobjectref<T> {};

template <typename T, typename Alloc>
struct is_container_of_connectbase<std::list<T, Alloc>>
    : derived_from_connectbase_and_constructible_from_confobjectref<T> {};

template <typename T, typename Alloc>
struct is_container_of_connectbase<std::deque<T, Alloc>>
    : derived_from_connectbase_and_constructible_from_confobjectref<T> {};

// Check if T is a std::array of fixed length, and the value_type
// is derived from ConnectBase
template <typename T>
struct is_array_of_connectbase : std::false_type {};

template <typename T, std::size_t N>
struct is_array_of_connectbase<std::array<T, N>>
    : std::is_base_of<ConnectBase, T> {};
}  // namespace detail

/**
 * Function transforms C++ enum type T to Simics attr_value_t
 **/
template <typename T> inline
typename std::enable_if<std::is_enum<T>::value, attr_value_t>::type
std_to_attr(const T &src) {
    return detail::attr_from_std_helper<std::underlying_type_t<T>>::f(
            static_cast<std::underlying_type_t<T>>(src));
}

/**
 * Function transforms C++ ConnectBase type T to Simics attr_value_t
 **/
template <typename T> inline
typename std::enable_if<std::is_base_of<ConnectBase, T>::value,
                        attr_value_t>::type
std_to_attr(const T &src) {
    return detail::attr_from_std_helper<ConfObjectRef>::f(src.get());
}

/**
 * Function transforms C++ pointer type T to Simics attr_value_t
 **/
template <typename T> inline
typename std::enable_if<std::is_pointer<T>::value, attr_value_t>::type
std_to_attr(const T &src) {
    // const char * is copied to a string attribute
    static_assert(std::is_same<T, const char *>::value,
                  "Pointer type is not allowed due to not checkpointable");
    return detail::attr_from_std_helper<T>::f(src);
}

/**
 * Function transforms C++ standard type T to Simics attr_value_t
 **/
template <typename T> inline
typename std::enable_if<!std::is_enum<T>::value
                        && !std::is_base_of<ConnectBase, T>::value
                        && !std::is_pointer<T>::value,
                        attr_value_t>::type
std_to_attr(const T &src) {
    return detail::attr_from_std_helper<T>::f(src);
}

/**
 * Function transforms Simics attr_value_t to C++ enum type
 **/
template <typename T> inline
typename std::enable_if<std::is_enum<T>::value, T>::type
attr_to_std(attr_value_t src) {
    return static_cast<T>(
            detail::attr_to_std_helper<std::underlying_type_t<T>>::f(src));
}

/**
 * Function transforms Simics attr_value_t to C++ ConnectBase derived type
 **/
template <typename T> inline
typename std::enable_if<std::is_base_of<ConnectBase, T>::value, T>::type
attr_to_std(attr_value_t src) {
    T c;
    if (!c.set(detail::attr_to_std_helper<ConfObjectRef>::f(src))) {
        throw std::runtime_error {
                "Unable to set to an illegal object"
        };
    }
    return c;
}

/**
 * Function transforms Simics attr_value_t to C++ pointer
 **/
template <typename T> inline
typename std::enable_if<std::is_pointer<T>::value, T>::type
attr_to_std(attr_value_t src) {
    // const char * is copied from a string attribute
    static_assert(std::is_same<T, const char *>::value,
                  "Pointer type is not allowed due to not checkpointable");
    return detail::attr_to_std_helper<std::remove_cv_t<T>>::f(src);
}

/**
 * Function transforms Simics attr_value_t to C++ standard type
 **/
template <typename T> inline
typename std::enable_if<!std::is_enum<T>::value
                        && !std::is_base_of<ConnectBase, T>::value
                        && !std::is_pointer<T>::value, T>::type
attr_to_std(attr_value_t src) {
    return detail::attr_to_std_helper<std::remove_cv_t<T>>::f(src);
}

namespace detail {

// Integral
#define _STD2ATTR_INT_HELPER(type)               \
    template <>                                  \
    struct attr_from_std_helper<type> {          \
        static attr_value_t f(const type &src) { \
            return SIM_make_attr_int64(src);     \
        }                                        \
    };
#define _STD2ATTR_UINT_HELPER(type)              \
    template <>                                  \
    struct attr_from_std_helper<type> {          \
        static attr_value_t f(const type &src) { \
            return SIM_make_attr_uint64(src);    \
        }                                        \
    };
_STD2ATTR_INT_HELPER(char)
_STD2ATTR_INT_HELPER(signed char)
_STD2ATTR_UINT_HELPER(unsigned char)
_STD2ATTR_INT_HELPER(short)  // NOLINT(runtime/int)
_STD2ATTR_UINT_HELPER(unsigned short)  // NOLINT(runtime/int)
_STD2ATTR_INT_HELPER(int)
_STD2ATTR_UINT_HELPER(unsigned int)
_STD2ATTR_INT_HELPER(long int)  // NOLINT(runtime/int)
_STD2ATTR_UINT_HELPER(unsigned long int)  // NOLINT(runtime/int)
_STD2ATTR_INT_HELPER(long long int)  // NOLINT(runtime/int)
_STD2ATTR_UINT_HELPER(unsigned long long int)  // NOLINT(runtime/int)
#undef _STD2ATTR_INT_HELPER
#undef _STD2ATTR_UINT_HELPER

#define _ATTR2STD_INT_HELPER(type)                                \
    template <>                                                   \
    struct attr_to_std_helper<type> {                             \
        static type f(const attr_value_t &src) {                  \
            if (!SIM_attr_is_integer(src)) {                      \
                throw SetIllegalType {                            \
                    "Expected Simics integer type"                \
                        };                                        \
            }                                                     \
            intmax_t i = SIM_attr_integer(src);                   \
            if (sizeof(type) != 8                                 \
                && (i > (std::numeric_limits<type>::max)()        \
                    || i < (std::numeric_limits<type>::min)())) { \
                throw SetIllegalValue {                           \
                    "Value does not fit in type"                  \
                        };                                        \
            }                                                     \
            return (type) i;                                      \
        }                                                         \
    };

#define _ATTR2STD_UINT_HELPER(type)                             \
    template <>                                                 \
    struct attr_to_std_helper<type> {                           \
        static type f(const attr_value_t &src) {                \
            if (!SIM_attr_is_integer(src)) {                    \
                throw SetIllegalType {                          \
                    "Expected Simics integer type"              \
                };                                              \
            }                                                   \
            uintmax_t i = static_cast<uintmax_t>(               \
                SIM_attr_integer(src));                         \
            if (sizeof(type) != 8                               \
                && i > (std::numeric_limits<type>::max)()) {    \
                throw SetIllegalValue {                         \
                    "Value does not fit in type"                \
                };                                              \
            }                                                   \
            return (type) i;                                    \
        }                                                       \
    };
_ATTR2STD_INT_HELPER(char)
_ATTR2STD_INT_HELPER(signed char)
_ATTR2STD_UINT_HELPER(unsigned char)
_ATTR2STD_INT_HELPER(short)  // NOLINT(runtime/int)
_ATTR2STD_UINT_HELPER(unsigned short)  // NOLINT(runtime/int)
_ATTR2STD_INT_HELPER(int)
_ATTR2STD_UINT_HELPER(unsigned int)
_ATTR2STD_INT_HELPER(long int)  // NOLINT(runtime/int)
_ATTR2STD_UINT_HELPER(unsigned long int)  // NOLINT(runtime/int)
_ATTR2STD_INT_HELPER(long long int)  // NOLINT(runtime/int)
_ATTR2STD_UINT_HELPER(unsigned long long int)  // NOLINT(runtime/int)
#undef _ATTR2STD_INT_HELPER
#undef _ATTR2STD_UINT_HELPER


// Float
#define _STD2ATTR_FLOAT_HELPER(type)             \
    template <>                                  \
    struct attr_from_std_helper<type> {          \
        static attr_value_t f(const type &src) { \
            return SIM_make_attr_floating(src);  \
        }                                        \
    };
_STD2ATTR_FLOAT_HELPER(float)
_STD2ATTR_FLOAT_HELPER(double)
#undef _STD2ATTR_FLOAT_HELPER

#define _ATTR2STD_FLOAT_HELPER(type)                \
    template <>                                     \
    struct attr_to_std_helper<type> {               \
        static type f(const attr_value_t &src) {    \
            if (!SIM_attr_is_floating(src)) {       \
                throw SetIllegalType {              \
                    "Expected Simics floating type" \
                };                                  \
            }                                       \
            return (type) SIM_attr_floating(src);   \
        }                                           \
    };
_ATTR2STD_FLOAT_HELPER(float)
_ATTR2STD_FLOAT_HELPER(double)
#undef _ATTR2STD_FLOAT_HELPER


// std::string
template <>
struct attr_from_std_helper<std::string> {
    static attr_value_t f(const std::string &src) {
        return SIM_make_attr_string(src.c_str());
    }
};

template <>
struct attr_to_std_helper<std::string> {
    static std::string f(const attr_value_t &src) {
        if (!SIM_attr_is_string(src)) {
            throw SetIllegalType {
                "Expected Simics string type"
            };
        }
        return SIM_attr_string(src);
    }
};

template <>
struct attr_from_std_helper<const char*> {
    static attr_value_t f(const char *src) {
        return SIM_make_attr_string(src);
    }
};

template <>
struct attr_to_std_helper<const char*> {
    static const char *f(const attr_value_t &src) {
        if (SIM_attr_is_nil(src)) {
            return nullptr;
        } else {
            if (!SIM_attr_is_string(src)) {
                throw SetIllegalType {
                    "Expected Simics string type"
                };
            }
            return SIM_attr_string(src);
        }
    }
};


// bool
template <>
struct attr_from_std_helper<bool> {
    static attr_value_t f(const bool &src) {
        return SIM_make_attr_boolean(src);
    }
};

template <>
struct attr_to_std_helper<bool> {
    static bool f(const attr_value_t &src) {
        if (!SIM_attr_is_boolean(src)) {
            throw SetIllegalType {
                "Expected Simics boolean type"
            };
        }
        return SIM_attr_boolean(src);
    }
};


// attr_value_t
template <>
struct attr_from_std_helper<attr_value_t> {
    static attr_value_t f(const attr_value_t &src) {
        return src;
    }
};

template <>
struct attr_to_std_helper<attr_value_t> {
    static attr_value_t f(const attr_value_t &src) {
        return src;
    }
};


// Container
template <typename C, typename T = typename C::value_type>
attr_value_t from_container(const C &src) {
    const auto size = src.size();
    checkSizeOverflowSimicsAttribute(size);
    const unsigned size_uint = static_cast<unsigned>(size);
    attr_value_t dst = SIM_alloc_attr_list(size_uint);
    auto it = src.cbegin();
    for (unsigned i = 0; i < size_uint; ++i, ++it) {
        SIM_attr_list_set_item(&dst, i, std_to_attr(*it));
    }
    return dst;
}

template <typename V, std::size_t N>
struct attr_from_std_helper<std::array<V, N>> {
    static attr_value_t f(const std::array<V, N> &src) {
        return from_container<std::array<V, N>>(src);
    }
};

template <typename V, std::size_t N>
struct attr_from_std_helper<V[N]> {
    static attr_value_t f(const V (&src)[N]) {
        std::array<V, N> std_arr;
        for (std::size_t i = 0; i < N; ++i) {
            std_arr[i] = src[i];
        }
        return from_container<std::array<V, N>>(std_arr);
    }
};

template <std::size_t N>
struct attr_from_std_helper<char[N]> {
    static attr_value_t f(const char (&src)[N]) {
        return SIM_make_attr_string(src);
    }
};

template <typename V>
struct attr_from_std_helper<std::vector<V>> {
    static attr_value_t f(const std::vector<V> &src) {
        return from_container<std::vector<V>>(src);
    }
};

template <typename V>
struct attr_from_std_helper<std::list<V>> {
    static attr_value_t f(const std::list<V> &src) {
        return from_container<std::list<V>>(src);
    }
};

template <typename V>
struct attr_from_std_helper<std::deque<V>> {
    static attr_value_t f(const std::deque<V> &src) {
        return from_container<std::deque<V>>(src);
    }
};

template <typename V>
struct attr_from_std_helper<std::set<V>> {
    static attr_value_t f(const std::set<V> &src) {
        return from_container<std::set<V>>(src);
    }
};

template <typename X, typename Y>
struct attr_from_std_helper<std::pair<X, Y>> {
    static attr_value_t f(const std::pair<X, Y>& src) {
        attr_value_t dst = SIM_alloc_attr_list(2);
        SIM_attr_list_set_item(&dst, 0, std_to_attr(src.first));
        SIM_attr_list_set_item(&dst, 1, std_to_attr(src.second));
        return dst;
    }
};

template <typename X, typename Y>
struct attr_from_std_helper<std::map<X, Y>> {
    static attr_value_t f(const std::map<X, Y>& src) {
        const auto size = src.size();
        checkSizeOverflowSimicsAttribute(size);
        attr_value_t dst = SIM_alloc_attr_list(static_cast<unsigned>(size));
        unsigned index = 0;
        for (const auto &p : src) {
            SIM_attr_list_set_item(&dst, index++,
                                   std_to_attr(std::forward_as_tuple(
                                                       p.first, p.second)));
        }
        return dst;
    }
};

template <typename... Args>
struct attr_from_std_helper<std::tuple<Args...>> {
    static attr_value_t f(const std::tuple<Args...> &src) {
        attr_value_t dst = SIM_alloc_attr_list(sizeof...(Args));
        set_items(&dst, src, 0, std::index_sequence_for<Args...>());
        return dst;
    }

  private:
    // Recursive template function to set items in the attribute list
    template<std::size_t Index, std::size_t... Is>
    static void set_items(attr_value_t *dst, const std::tuple<Args...> &src,
                          std::size_t current_index,
                          std::index_sequence<Index, Is...>) {
        SIM_attr_list_set_item(dst, Index, std_to_attr(std::get<Index>(src)));
        set_items(dst, src, current_index + 1, std::index_sequence<Is...>());
    }

    // Base case for recursion
    static void set_items(attr_value_t *, const std::tuple<Args...> &,
                          std::size_t, std::index_sequence<>) {}
};

template <typename C, typename T = typename C::value_type>
C to_container(const attr_value_t &src) {
    if (!SIM_attr_is_list(src)) {
        throw SetIllegalType {
            "Expected Simics list type"
        };
    }
    const unsigned size = SIM_attr_list_size(src);
    std::vector<T> v;
    for (unsigned i = 0; i < size; ++i) {
        v.push_back(attr_to_std<T>(SIM_attr_list_item(src, i)));
    }
    return {v.begin(), v.end()};
}

template <typename V>
struct attr_to_std_helper<std::vector<V>> {
    static std::vector<V> f(const attr_value_t &src) {
        return to_container<std::vector<V>>(src);
    }
};

template <typename V>
struct attr_to_std_helper<std::list<V>> {
    static std::list<V> f(const attr_value_t &src) {
        return to_container<std::list<V>>(src);
    }
};

template <typename V>
struct attr_to_std_helper<std::deque<V>> {
    static std::deque<V> f(const attr_value_t &src) {
        return to_container<std::deque<V>>(src);
    }
};

template <typename V>
struct attr_to_std_helper<std::set<V>> {
    static std::set<V> f(const attr_value_t &src) {
        return to_container<std::set<V>>(src);
    }
};

template <typename V, std::size_t N>
struct attr_to_std_helper<std::array<V, N>> {
    static std::array<V, N> f(const attr_value_t &src) {
        if (!SIM_attr_is_list(src)) {
            throw SetIllegalType {
                "Expected Simics list type"
            };
        }
        const unsigned size = SIM_attr_list_size(src);
        if (size != N) {
            throw SetIllegalType {
                "Size mismatch for std::array"
            };
        }
        std::array<V, N> result;
        for (unsigned i = 0; i < size; ++i) {
            result[i] = attr_to_std<V>(SIM_attr_list_item(src, i));
        }
        return result;
    }
};

template <typename X, typename Y>
struct attr_to_std_helper<std::pair<X, Y>> {
    static std::pair<X, Y> f(const attr_value_t& src) {
        if (!SIM_attr_is_list(src) || SIM_attr_list_size(src) != 2) {
            throw SetIllegalType {
                "Expected Simics list type with exactly two members"
            };
        }
        return {attr_to_std<X>(SIM_attr_list_item(src, 0)),
                attr_to_std<Y>(SIM_attr_list_item(src, 1))};
    }
};

template <typename X, typename Y>
struct attr_to_std_helper<std::map<X, Y>> {
    static std::map<X, Y> f(const attr_value_t& src) {
        if (!SIM_attr_is_list(src)) {
            throw SetIllegalType {
                "Expected Simics list type"
            };
        }
        std::map<X, Y> ret;
        for (unsigned i = 0; i < SIM_attr_list_size(src); ++i) {
            ret.emplace(attr_to_std<std::pair<X, Y>>(
                                SIM_attr_list_item(src, i)));
        }
        return ret;
    }
};

template <typename... Args>
struct attr_to_std_helper<std::tuple<Args...>> {
    static std::tuple<Args...> f(const attr_value_t &src) {
        if (!SIM_attr_is_list(src)
            || SIM_attr_list_size(src) != sizeof...(Args)) {
            throw SetIllegalType{
                "Expected Simics list type with exactly " + \
                std::to_string(sizeof...(Args)) + " members"
            };
        }

        return convert_tuple(src, std::index_sequence_for<Args...>());
    }

  private:
    // Helper function to convert items in the attribute list to a tuple
    template<std::size_t... Is>
    static std::tuple<Args...> convert_tuple(const attr_value_t &src,
                                             std::index_sequence<Is...>) {
        return std::make_tuple(convert_item<Args>(src, Is)...);
    }

    template<typename T>
    static T convert_item(const attr_value_t &src, std::size_t index) {
        return attr_to_std<T>(SIM_attr_list_item(src, index));
    }
};

// Use this type for Simics "data" type
using data_attribute = std::vector<uint8>;

template <>
struct attr_from_std_helper<data_attribute> {
    static attr_value_t f(const data_attribute& src) {
        const auto size = src.size();
        checkSizeOverflowSimicsAttribute(size);
        return SIM_make_attr_data(size, src.data());
    }
};

template <>
struct attr_to_std_helper<data_attribute> {
    static data_attribute f(const attr_value_t& src) {
        if (!SIM_attr_is_data(src)) {
            throw SetIllegalType {
                "Expected Simics data type"
            };
        }
        size_t size = SIM_attr_data_size(src);
        const uint8 *data = SIM_attr_data(src);
        return data_attribute(data, data + size);
    }
};

}  // namespace detail
}  // namespace simics

#endif
