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

#ifndef SIMICS_TYPE_COMMON_TYPES_H
#define SIMICS_TYPE_COMMON_TYPES_H

#include <fmt/fmt/format.h>

#include <cstddef>  // size_t
#include <string_view>

#include "simics/type/hierarchical-object-name.h"

namespace simics {
namespace detail {

/// Literal type that extends size_t type
class ConstSizeT {
  public:
    constexpr ConstSizeT(size_t value = 0)  // NOLINT(runtime/explicit)
        : value_(value) {}
    constexpr operator size_t () const {return value_;}

  private:
    size_t value_;
};

}  // namespace detail

/// Type used to name a resource
using Name = detail::HierarchicalObjectName;

/// Type used to describe a resource
using Description = std::string_view;

/// Type used for memory address offset
using Offset = detail::ConstSizeT;

/// Type used for the number/width of bit
using BitWidth = detail::ConstSizeT;

/// Type used for initial value
using InitValue = detail::ConstSizeT;

/// Type used for the number/size of byte
/// TODO(xiuliang): add valid value checker?
using ByteSize = detail::ConstSizeT;

/// Type used for the stride of register/field array
using Stride = detail::ConstSizeT;
}  // namespace simics

// Define the hash specialization for ConstSizeT
namespace std {
template <>
struct hash<simics::detail::ConstSizeT> {
    size_t operator()(const simics::detail::ConstSizeT &obj) const {
        return hash<size_t>{}(size_t{obj});
    }
};
}  // namespace std

// Define the formatter specialization for ConstSizeT
namespace fmt {
template <>
struct formatter<simics::detail::ConstSizeT> : formatter<size_t> {
    template <typename FormatContext>
    auto format(const simics::detail::ConstSizeT& val,
                FormatContext& ctx) {  // NOLINT(runtime/references)
        return formatter<size_t>::format(static_cast<size_t>(val), ctx);
    }
};
}  // namespace fmt

#endif
