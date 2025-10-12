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

#include <simics/type/field-type.h>

#include <gtest/gtest.h>

TEST(TestFieldType, TestFieldType) {
    simics::field_t f_explicit {
        simics::Name("field0"),
        simics::Description("a field with explicit type"),
        simics::Offset(10), simics::BitWidth(4)};
    auto[name, desc, offset, width] = f_explicit;
    EXPECT_EQ(name, "field0");
    EXPECT_EQ(desc, "a field with explicit type");
    EXPECT_EQ(offset, 10);
    EXPECT_EQ(width, 4);

    simics::field_t f_implicit {"field1", "a field with implicit conversion",
                                20, 8};
    std::tie(name, desc, offset, width) = f_implicit;
    EXPECT_EQ(name, "field1");
    EXPECT_EQ(desc, "a field with implicit conversion");
    EXPECT_EQ(offset, 20);
    EXPECT_EQ(width, 8);
}

