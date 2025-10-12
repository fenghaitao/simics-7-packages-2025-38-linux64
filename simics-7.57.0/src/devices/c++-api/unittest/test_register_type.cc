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

#include <simics/type/register-type.h>

#include <gtest/gtest.h>

TEST(TestRegisterType, TestRegisterType) {
    simics::register_t r_explicit {"register0",
            "a register with explicit type",
            simics::Offset(10), simics::ByteSize(4), simics::InitValue(2),
            {simics::field_t("f0", "", simics::Offset(1),
             simics::BitWidth(2))}};
    auto[name, desc, offset, size, init_val, fields] = r_explicit;
    EXPECT_EQ(name, "register0");
    EXPECT_EQ(desc, "a register with explicit type");
    EXPECT_EQ(offset, 10);
    EXPECT_EQ(size, 4);
    EXPECT_EQ(init_val, 2);
    EXPECT_EQ(fields.size(), 1);

    simics::register_t r_implicit {"register1",
            "a register with implicit conversion", 20, 8, 4,
            {{"f0", "", 1, 2}, {"f1", "", 3, 4}}};
    std::tie(name, desc, offset, size, init_val, fields) = r_implicit;
    EXPECT_EQ(name, "register1");
    EXPECT_EQ(desc, "a register with implicit conversion");
    EXPECT_EQ(offset, 20);
    EXPECT_EQ(size, 8);
    EXPECT_EQ(init_val, 4);
    EXPECT_EQ(fields.size(), 2);
}

