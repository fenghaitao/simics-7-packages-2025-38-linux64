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

#ifndef SIMICS_UTILITY_H
#define SIMICS_UTILITY_H

#include <cstddef>  // size_t
#include <string>
#if __cplusplus >= 201703L || (defined(_MSVC_LANG) && _MSVC_LANG >= 201703L)
#include <string_view>
#endif
#include <utility>  // pair
#include <vector>

#include "simics/detail/conf-object-util.h"

namespace simics {

#if defined SIMICS_6_API || defined SIMICS_7_API
/**
 * @deprecated Use simics::detail::get_interface instead.
 */
template <typename IFACE>
IFACE* get_interface(conf_object_t *obj) {
    return detail::get_interface<IFACE>(obj);
}
#endif

/**
 * This function looks for a pattern in the input string that resembles an
 * array index, specifically a substring enclosed in square brackets (e.g.,
 * "array[2]").
 * It supports only single-dimensional arrays and returns the index as an
 * integer.
 *
 * @param name The string representation of the array (e.g., "array[2]").
 * @return The extracted index if valid; -1 if the format is invalid or if
 *         the index is negative or multi-dimensional.
 */
int array_index(const std::string &name);

/**
 * If name contains an array indicator, i.e. port[N], return a list that
 * contains all expanded index names, i.e. port[0], port[1], ...
 * Otherwise a list with only the name is returned. Multi-dimensional arrays
 * are not supported. Multi-level names with level delimiter is
 * supported, i.e. a[N].b[M] is expanded to N * M names.
 */
std::vector<std::string> expand_names(const std::string &name,
                                      const char delimiter = '.');

/**
 * Given two ranges [r1_start, r1_end) and [r2_start, r2_end),
 * return the overlap range [o_start, o_end)
 */
std::pair<size_t, size_t> overlap_range(size_t r1_start,
                                        size_t r1_end,
                                        size_t r2_start,
                                        size_t r2_end);

/**
 * Hashes a string to a size_t value.
 */
size_t hash_str(const char *name);
#if __cplusplus >= 201703L || (defined(_MSVC_LANG) && _MSVC_LANG >= 201703L)
size_t hash_str(std::string_view name);
#endif
}  // namespace simics

#endif
