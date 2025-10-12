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

#include <simics/attribute-type-string.h>

#include <gtest/gtest.h>

#include <map>
#include <string>

TEST(TestAttributeTypeString, TestAttrSimple) {
    EXPECT_EQ(simics::attr_type_str<bool>(), "b");
    EXPECT_EQ(simics::attr_type_str<char>(), "i");
    EXPECT_EQ(simics::attr_type_str<long int>(),  // NOLINT(runtime/int)
              "i");
    EXPECT_EQ(simics::attr_type_str<double>(), "f");
    EXPECT_EQ(simics::attr_type_str<simics::ConfObjectRef>(), "[os]|o|n");
    EXPECT_EQ(simics::attr_type_str<std::string>(), "s");
    EXPECT_EQ(simics::attr_type_str<attr_value_t>(), "a");
}

TEST(TestAttributeTypeString, TestAttrContainer) {
    EXPECT_EQ((simics::attr_type_str<std::pair<int, float>>()), "[if]");
    EXPECT_EQ(simics::attr_type_str<std::set<short>>(),  // NOLINT(runtime/int)
              "[i*]");
    EXPECT_EQ(simics::attr_type_str<std::vector<uint8>>(), "d");
    EXPECT_EQ((simics::attr_type_str<std::map<double, bool>>()), "[[fb]*]");
    EXPECT_EQ((simics::attr_type_str<std::array<char, 4>>()), "[i{4}]");
    EXPECT_EQ((simics::attr_type_str<std::tuple<int, float, bool>>()), "[ifb]");
}

