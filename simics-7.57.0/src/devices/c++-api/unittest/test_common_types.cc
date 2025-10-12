// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2025 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include <gtest/gtest.h>
#include <fmt/fmt/format.h>

#include <string>

#include "simics/type/common-types.h"

TEST(CommonTypesTest, ConstSizeTBasic) {
    simics::detail::ConstSizeT a = 42;
    size_t b = a;
    EXPECT_EQ(b, 42u);

    simics::detail::ConstSizeT c;
    EXPECT_EQ(static_cast<size_t>(c), 0u);

    simics::detail::ConstSizeT d(123);
    EXPECT_EQ(static_cast<size_t>(d), 123u);
}

TEST(CommonTypesTest, ConstSizeTIsFormattable) {
    simics::detail::ConstSizeT v = 99;
    std::string s = fmt::format("Value is {}", v);
    EXPECT_EQ(s, "Value is 99");
}

TEST(CommonTypesTest, TypeAliases) {
    simics::Name name("reg0");
    simics::Description desc = "desc";
    simics::Offset offset = 5;
    simics::BitWidth width = 8;
    simics::InitValue init = 0x42;
    simics::ByteSize bytes = 4;
    simics::Stride stride = 2;

    EXPECT_EQ(static_cast<size_t>(offset), 5u);
    EXPECT_EQ(static_cast<size_t>(width), 8u);
    EXPECT_EQ(static_cast<size_t>(init), 0x42u);
    EXPECT_EQ(static_cast<size_t>(bytes), 4u);
    EXPECT_EQ(static_cast<size_t>(stride), 2u);
    EXPECT_EQ(std::string(name), "reg0");
    EXPECT_EQ(desc, "desc");
}

