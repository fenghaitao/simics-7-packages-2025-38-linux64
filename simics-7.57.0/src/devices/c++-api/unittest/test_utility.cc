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

#include <simics/utility.h>

#include <gtest/gtest.h>

#include <string>
#include <tuple>
#include <vector>

TEST(TestUtility, TestArrayIndex) {
    // Not a valid array style
    EXPECT_EQ(simics::array_index("no_brackets"), -1);
    EXPECT_EQ(simics::array_index("unpair_brackets["), -1);
    EXPECT_EQ(simics::array_index("unpair_brackets]"), -1);
    EXPECT_EQ(simics::array_index("inversed_brackets]["), -1);
    EXPECT_EQ(simics::array_index("brackets_[3]_not_at_end"), -1);
    EXPECT_EQ(simics::array_index("double_brackets[[3]]"), -1);
    EXPECT_EQ(simics::array_index("other_brackets(3)"), -1);
    EXPECT_EQ(simics::array_index("other_brackets{3}"), -1);
    EXPECT_EQ(simics::array_index("multi_dimensional_array[2][3]"), -1);

    EXPECT_EQ(simics::array_index("invalid_brackets[0]"), 0);
    EXPECT_EQ(simics::array_index("invalid_brackets[03]"), 3);
    EXPECT_EQ(simics::array_index("invalid_brackets[0x30]"), 48);

    // INT_MAX + 1 is too large for int
    EXPECT_EQ(simics::array_index("valid_brackets[2147483648]"), -1);
}

TEST(TestUtility, TestExpandNames) {
    // No array indicator
    auto ret = simics::expand_names("no_array");
    std::vector<std::string> expect {"no_array"};
    EXPECT_EQ(ret, expect);

    // Invalid array syntax
    ret = simics::expand_names("invalid_array{3]");
    expect[0] = "invalid_array{3]";
    EXPECT_EQ(ret, expect);

    ret = simics::expand_names("invalid_array[0]");
    expect[0] = "invalid_array[0]";
    EXPECT_EQ(ret, expect);

    // Valid array syntax
    ret = simics::expand_names("valid_array[3]");
    expect = {"valid_array[0]", "valid_array[1]", "valid_array[2]"};
    EXPECT_EQ(ret, expect);

    // Multi-dimensional array is not supported
    ret = simics::expand_names("multi_array[3][4]");
    expect = {"multi_array[3][4]"};
    EXPECT_EQ(ret, expect);

    // Multi-level hierarchical name is supported
    ret = simics::expand_names("first[3].second");
    expect = {"first[0].second", "first[1].second", "first[2].second"};
    EXPECT_EQ(ret, expect);

    ret = simics::expand_names("first[3].second[2]");
    expect = {"first[0].second[0]", "first[0].second[1]", "first[1].second[0]",
              "first[1].second[1]", "first[2].second[0]", "first[2].second[1]"};
    EXPECT_EQ(ret, expect);

    ret = simics::expand_names("first[3].second.third[2]");
    expect = {"first[0].second.third[0]", "first[0].second.third[1]",
              "first[1].second.third[0]", "first[1].second.third[1]",
              "first[2].second.third[0]", "first[2].second.third[1]"};
    EXPECT_EQ(ret, expect);

    ret = simics::expand_names("first[3].second[2].third[2]");
    expect = {"first[0].second[0].third[0]", "first[0].second[0].third[1]",
              "first[0].second[1].third[0]", "first[0].second[1].third[1]",
              "first[1].second[0].third[0]", "first[1].second[0].third[1]",
              "first[1].second[1].third[0]", "first[1].second[1].third[1]",
              "first[2].second[0].third[0]", "first[2].second[0].third[1]",
              "first[2].second[1].third[0]", "first[2].second[1].third[1]"};
    EXPECT_EQ(ret, expect);
}

TEST(TestUtility, TestOverlapRange) {
    size_t overlap_start = 0, overlap_end = 0;

    // empty input range
    std::tie(overlap_start, overlap_end) = simics::overlap_range(0, 0, 0, 0);
    EXPECT_EQ(overlap_start, 0);
    EXPECT_EQ(overlap_end, 0);

    // No overlap
    std::tie(overlap_start, overlap_end) = simics::overlap_range(6, 10, 10, 16);
    EXPECT_EQ(overlap_start, 0);
    EXPECT_EQ(overlap_end, 0);

    // One range contains in another
    std::tie(overlap_start, overlap_end) = simics::overlap_range(6, 16, 8, 10);
    EXPECT_EQ(overlap_start, 8);
    EXPECT_EQ(overlap_end, 10);

    // Same start offset
    std::tie(overlap_start, overlap_end) = simics::overlap_range(
            1, 1ULL<<63, 1, 10);
    EXPECT_EQ(overlap_start, 1);
    EXPECT_EQ(overlap_end, 10);

    // Same end offset
    std::tie(overlap_start, overlap_end) = simics::overlap_range(
            1, 16, 10, 16);
    EXPECT_EQ(overlap_start, 10);
    EXPECT_EQ(overlap_end, 16);

    // Very large offset
    std::tie(overlap_start, overlap_end) = simics::overlap_range(
            0x1000000000000000,
            0xf000000000000000,
            0x2000000000000000,
            0xffffffffffffffff);
    EXPECT_EQ(overlap_start, 0x2000000000000000);
    EXPECT_EQ(overlap_end, 0xf000000000000000);
}

TEST(TestUtility, TestHashStr) {
    // Test that the hash is consistent for the same string
    std::string input1 = "test_string";
    size_t hash1 = simics::hash_str(input1);
    size_t hash2 = simics::hash_str(input1);
    EXPECT_EQ(hash1, hash2);

    // Test that different strings produce different hashes
    std::string input2 = "different_string";
    size_t hash3 = simics::hash_str(input2);
    EXPECT_NE(hash1, hash3);

    // Test that the hash matches std::hash<std::string>
    size_t expected_hash1 = std::hash<std::string>{}(input1);
    size_t expected_hash2 = std::hash<std::string>{}(input2);
    EXPECT_EQ(hash1, expected_hash1);
    EXPECT_EQ(hash3, expected_hash2);

    // Test edge cases
    std::string empty_string = "";
    size_t empty_hash = simics::hash_str(empty_string);
    size_t expected_empty_hash = std::hash<std::string>{}(empty_string);
    EXPECT_EQ(empty_hash, expected_empty_hash);

    std::string special_chars = "!@#$%^&*()";
    size_t special_hash = simics::hash_str(special_chars);
    size_t expected_special_hash = std::hash<std::string>{}(special_chars);
    EXPECT_EQ(special_hash, expected_special_hash);
}
