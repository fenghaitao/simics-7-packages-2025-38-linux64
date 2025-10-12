// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2024 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include "simics/utility.h"

#include <algorithm>  // count
#include <functional>  // hash
#include <string>
#if __cplusplus >= 201703L || (defined(_MSVC_LANG) && _MSVC_LANG >= 201703L)
#include <string_view>
#endif
#include <utility>  // pair
#include <vector>

namespace simics {

int array_index(const std::string &name) {
    const size_t left_bracket = name.rfind("[");
    const size_t right_bracket = name.rfind("]");

    // Validate bracket positions and ensure they are correctly formatted
    if (left_bracket == std::string::npos
        || right_bracket == std::string::npos
        || right_bracket <= left_bracket + 1
        || right_bracket != name.size() - 1) {
        return -1;
    }

    // Multi-dimensional arrays are not supported
    if (std::count(name.begin(), name.end(), '[') > 1
        || std::count(name.begin(), name.end(), ']') > 1) {
        return -1;
    }

    std::string index_str = name.substr(left_bracket + 1,
                                        right_bracket - left_bracket - 1);

    int index = -1;
    try {
        index = std::stoi(index_str, nullptr, 0);
    } catch (const std::invalid_argument&) {
        // Conversion failed (invalid number)
        return -1;
    } catch (const std::out_of_range&) {
        // Conversion failed (out of range)
        return -1;
    }

    // Return -1 for negative indices
    return (index < 0) ? -1 : index;
}

static std::vector<std::string> expand_names_one_dimension(
        const std::string &name, const char delimiter) {
    assert(name.find(delimiter) == std::string::npos);

    int idx = simics::array_index(name);
    if (idx < 1) {
        return {name};
    }

    auto prefix = name.substr(0, name.rfind("[") + 1);
    std::vector<std::string> ret;
    for (auto i = 0; i < idx; ++i) {
        ret.push_back(prefix + std::to_string(i) + "]");
    }
    return ret;
}

std::vector<std::string> expand_names(const std::string &name,
                                      const char delimiter) {
    if (name.find(delimiter) == std::string::npos) {
        return expand_names_one_dimension(name, delimiter);
    }

    std::vector<std::string> expanded_names;
    std::string::size_type pos;
    std::string unprocessed_parts = name;
    do {
        pos = unprocessed_parts.find(delimiter);
        std::string next_part = unprocessed_parts.substr(0, pos);
        if (expanded_names.empty()) {
            expanded_names = expand_names_one_dimension(next_part, delimiter);
        } else {
            auto names_copy = expanded_names;
            expanded_names.clear();
            for (const auto &prefix : names_copy) {
                for (const auto &suffix : expand_names_one_dimension(
                             next_part, delimiter)) {
                    expanded_names.push_back(prefix + delimiter + suffix);
                }
            }
        }
        unprocessed_parts = unprocessed_parts.substr(pos + 1);
    } while (pos != std::string::npos);
    return expanded_names;
}

std::pair<size_t, size_t> overlap_range(size_t r1_start,
                                        size_t r1_end,
                                        size_t r2_start,
                                        size_t r2_end) {
    auto o_start = std::max(r1_start, r2_start);
    auto o_end = std::min(r1_end, r2_end);

    // Check if there is an overlap
    if (o_start < o_end) {
        return {o_start, o_end};
    } else {
        // No overlap
        return {0, 0};
    }
}

size_t hash_str(const char *name) {
    return std::hash<std::string>{}(std::string(name));
}
#if __cplusplus >= 201703L || (defined(_MSVC_LANG) && _MSVC_LANG >= 201703L)
size_t hash_str(std::string_view name) {
    return std::hash<std::string_view>{}(name);
}
#endif
}  // namespace simics

