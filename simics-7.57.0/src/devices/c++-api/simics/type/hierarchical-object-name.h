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

#ifndef SIMICS_TYPE_HIERARCHICAL_OBJECT_NAME_H
#define SIMICS_TYPE_HIERARCHICAL_OBJECT_NAME_H

#ifdef __GNUC__
#include <cctype>  // isalpha
#endif
#include <cstddef>
#include <map>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>  // pair
#include <vector>

namespace simics {
namespace detail {

/**
 * @brief Represents name of a bank/register/field
 *
 * The name should be aligned with the hierarchical object name format:
 * 
 * - The name must not be empty. An exception is thrown if the name is empty.
 * - The name must begin with an alphabetic character.
 * - The base name (without array notation) must consist only of alphanumeric
 *   characters and underscores ('_').
 * - The array notation is enclosed in square brackets ('[' and ']').
 */
class HierarchicalObjectName : public std::string_view {
  public:
    HierarchicalObjectName() = delete;
    constexpr HierarchicalObjectName(
            const HierarchicalObjectName& other) noexcept = default;
    constexpr HierarchicalObjectName(const_pointer s, size_type count)
        : std::string_view(s, count) {
        validate_name(*this);
    }
    constexpr HierarchicalObjectName(
            const_pointer s)  // NOLINT(runtime/explicit)
        : std::string_view(s) {
        validate_name(*this);
    }

    /**
     * Validates the format of a name, ensuring it adheres to specific rules.
     *
     * This constexpr function checks the validity of a name by enforcing the
     * following constraints:
     * - The name must not be empty. An exception is thrown if the name is
     *   empty.
     * - The name must begin with an alphabetic character. If the first
     *   character is not alphabetic, an exception is thrown with a descriptive
     *   error message.
     * - The base name must consist only of alphanumeric characters and
     *   underscores ('_'). Any other character will result in an exception
     *   being thrown, indicating the invalid character.
     */
    static constexpr void validate_name(std::string_view name) {
#ifdef __GNUC__
        using std::isalpha;
        using std::isalnum;
#endif
        if (name.empty()) {
            throw std::invalid_argument("Empty name is not allowed");
        }
        if (!isalpha(name.front())) {
            throw std::invalid_argument(
                std::string("Name (") + name.data() \
                + ") does not begin with an alphabetic character");
        }

        // Validate base_name
        for (const auto &c : name.substr(0, name.find('['))) {
            if (c != '_' && !isalnum(c)) {
                throw std::invalid_argument(
                        std::string("Character (") + c \
                        + ") is not allowed to use in a name");
            }
        }
    }

    /// @return The base name without array information
    constexpr std::string_view base_name() const {
        return substr(0, find('['));
    }

    /// @return The array information without base name
    constexpr std::string_view array_str() const {
        auto pos = find('[');
        if (pos != npos) {
            return substr(pos);
        }
        return {};
    }

    /**
     * Generates a mapping of array names to their corresponding memory
     * offsets.
     *
     * This function calculates the offsets for array elements based on
     * their names and dimensions, using the specified width for the
     * innermost dimension's stride. It returns a map where each key is a
     * string representing the name of an array element, and each value is the
     * calculated offset for that element.
     *
     * @param width The width used as the stride for the innermost dimension.
     * @return A map where each key is a string representing an array element's
     *         name, and each value is the calculated offset for that element.
     */
    std::map<std::string, size_t> arrayNamesToOffsets(size_t width) const {
        if (width == 0) {
            throw std::invalid_argument("Invalid width 0");
        }

        if (array_str().empty()) {
            return {};
        }

        auto sizes_and_strides = arraySizesAndStrides();
        // Update strides for all dimensions
        for (auto it = sizes_and_strides.rbegin();
             it != sizes_and_strides.rend(); ++it) {
            if (it->second != 0) {
                continue;
            }
            if (it == sizes_and_strides.rbegin()) {
                // The innermost dimension, use width as the stride
                it->second = width;
            } else {
                // Use the sum of distances of inner dimension elements
                it->second = (it - 1)->first * (it - 1)->second;
            }
        }

        std::map<std::string, size_t> names_to_offsets;
        std::vector<size_t> indices(sizes_and_strides.size(), 0);
        generateNamesToOffsets(sizes_and_strides, 0, &indices,
                               &names_to_offsets);
        return names_to_offsets;
    }

    /**
     * Parses a string representation of array dimensions to extract sizes and
     * strides.
     *
     * This function processes a string obtained from `array_str()` to
     * determine the sizes and strides of array dimensions, returning them as a
     * vector of pairs. Each pair consists of a size and a stride for a
     * dimension.
     *
     * @return A vector of pairs, where each pair contains the size and stride
     *         of a dimension.
     * @throws std::logic_error if the input string is malformed or contains
     *         invalid dimensions.
     */
    std::vector<std::pair<size_t, size_t>> arraySizesAndStrides() const {
        auto s = array_str();
        if (s.empty()) {
            return {};
        }

        std::size_t content_pos = npos;
        std::vector<std::pair<size_t, size_t>> dims_;
        for (size_t i = 0; i < s.size(); ++i) {
            auto c = s[i];
            if (c == '[') {
                if (content_pos != npos) {
                    throw std::logic_error("Name has unbalanced brackets");
                }
                content_pos = i + 1;
            } else if (c == ']') {
                if (content_pos == npos) {
                    throw std::logic_error("Name has unbalanced brackets");
                }
                if (content_pos == i) {
                    throw std::logic_error("Name has nothing in brackets");
                }
                const auto &[size, stride] = sizeAndStride(
                        s.substr(content_pos, i - content_pos));
                if (size == 0) {
                    throw std::logic_error("Dimension size is 0");
                }
                dims_.push_back({size, stride});
                content_pos = npos;
            }
        }

        if (content_pos != npos) {
            throw std::logic_error("Name has unbalanced brackets");
        }

        return dims_;
    }

  private:
#ifndef __GNUC__
    // Microsoft Visual Studio 2022 treat these functions as non-constexpr and
    // generates C3615 error
    static constexpr bool isalpha(value_type c) {
        return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z');
    }

    static constexpr bool isalnum(value_type c) {
        return isalpha(c) || (c >= '0' && c <= '9');
    }
#endif

    /**
     * Parses a string to extract size and stride values.
     *
     * This function takes a string view `s` and attempts to parse it to
     * extract two numeric values: size and stride. The expected format of
     * the string is either "<size> stride <stride>" or simply "<size>".
     *
     * @param s The input string view containing size and optionally stride.
     * @return A pair of size and stride values. If stride is not specified,
     *         it defaults to 0.
     * @throws std::invalid_argument if the input string is malformed or
     *         contains non-digit characters.
     */
    std::pair<size_t, size_t> sizeAndStride(std::string_view s) const {
        auto stride_pos = s.find(" stride ");
        size_t size;
        size_t stride = 0;

        try {
            if (stride_pos != npos) {
                size = std::stoi(s.substr(0, stride_pos).data());
                stride = std::stoi(s.substr(stride_pos + 8).data());
            } else {
                if (s.find_first_not_of("0123456789") != npos) {
                    throw std::invalid_argument("non-digit character");
                }
                size = std::stoi(s.data());
            }
        } catch (const std::exception &e) {
            throw std::invalid_argument(
                    std::string("Array contents are malformed: ") + e.what());
        }

        return {size, stride};
    }

    /**
     * Generates a mapping of names to offsets based on multidimensional
     * indices.
     *
     * This function recursively traverses a set of dimensions described by
     * `dims_info`, generating names and corresponding offsets for each
     * combination of indices.
     * The names are constructed in a format similar to array indexing, e.g.,
     * "base_name[0][1]".
     *
     * @param dims_info A vector of pairs, where each pair contains the size
     *                  and stride of a dimension. The size indicates the
     *                  number of indices in the dimension, and the stride is
     *                  used to calculate offsets.
     * @param current_dim The current dimension being processed. Initially set
     *                    to 0 and incremented with each recursive call.
     * @param indices A pointer to a vector that holds the current indices for
     *                each dimension. This vector is updated recursively to
     *                reflect the current position.
     * @param names_to_offsets A pointer to a map that stores the generated
     *                         names and their corresponding offsets. The map
     *                         is populated as the recursion reaches the
     *                         innermost dimension.
     */
    void generateNamesToOffsets(const std::vector<std::pair<size_t, size_t>>
                                &dims_info,
                                size_t current_dim,
                                std::vector<size_t> *indices,
                                std::map<std::string, size_t>
                                *names_to_offsets) const {
        if (current_dim == dims_info.size()) {
            // We have reached the innermost dimension, so generate the name
            // and offset and add it to the vector
            std::string name {base_name()};
            size_t offset = 0;
            for (size_t i = 0; i < indices->size(); i++) {
                name += "[" + std::to_string((*indices)[i]) + "]";
                offset += (*indices)[i] * dims_info[i].second;
            }
            (*names_to_offsets)[name] = offset;
        } else {
            // Iterate over each index of the current dimension and recurse
            for (size_t i = 0; i < dims_info[current_dim].first; i++) {
                (*indices)[current_dim] = i;
                generateNamesToOffsets(dims_info, current_dim + 1,
                                       indices, names_to_offsets);
            }
        }
    }
};

}  // namespace detail
}  // namespace simics

#endif
