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

#include <simics/type/bank-type.h>

#include <gtest/gtest.h>

TEST(TestBankType, TestBankType) {
    simics::bank_t b_explicit {
        simics::Name("bank0"),
        simics::Description("a bank with explicit type"),
        {}};
    auto[name, desc, registers] = b_explicit;
    EXPECT_EQ(name, "bank0");
    EXPECT_EQ(desc, "a bank with explicit type");
    EXPECT_EQ(registers.size(), 0);

    simics::bank_t b_implicit {"bank1", "a bank with implicit conversion",
        {{"r", "", 0, 0, 0, {}}}};
    std::tie(name, desc, registers) = b_implicit;
    EXPECT_EQ(name, "bank1");
    EXPECT_EQ(desc, "a bank with implicit conversion");
    EXPECT_EQ(registers.size(), 1);
}
