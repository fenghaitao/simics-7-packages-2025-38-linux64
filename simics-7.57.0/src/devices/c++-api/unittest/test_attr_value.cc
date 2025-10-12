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

#include <gtest/gtest.h>
#include <utility>

#include "simics/attr-value.h"

#include "mock/stubs.h"

using simics::AttrValue;

class AttrValueTest : public ::testing::Test {
  protected:
    void SetUp() override {
        // Reset the stub counters
        sim_attr_free_cnt_ = Stubs::instance_.sim_attr_free_cnt_;
    }

    void TearDown() override {
        // Clean up if necessary
        Stubs::instance_.sim_attr_free_cnt_ = 0;
    }

    size_t sim_attr_free_cnt_ { 0 };
};

TEST_F(AttrValueTest, ConstructorFromAttr) {
    AttrValue attr_value(SIM_make_attr_string("test"));
    EXPECT_EQ(static_cast<attr_value_t>(attr_value).private_kind,
              Sim_Val_String);
}

TEST_F(AttrValueTest, MoveConstructor) {
    AttrValue attr_value(SIM_make_attr_string("test"));
    AttrValue attr_value_move(std::move(attr_value));

    EXPECT_EQ(static_cast<attr_value_t>(attr_value).private_kind,
              Sim_Val_Invalid);
    EXPECT_EQ(static_cast<attr_value_t>(attr_value_move).private_kind,
              Sim_Val_String);
}

TEST_F(AttrValueTest, MoveAssignment) {
    AttrValue attr_value(SIM_make_attr_string("test"));
    AttrValue attr_value_move(SIM_make_attr_boolean(true));
    attr_value_move = std::move(attr_value);

    EXPECT_EQ(static_cast<attr_value_t>(attr_value).private_kind,
              Sim_Val_Invalid);
    EXPECT_EQ(static_cast<attr_value_t>(attr_value_move).private_kind,
              Sim_Val_String);
}

TEST_F(AttrValueTest, AssignmentFromAttrValueT) {
    AttrValue attr_value(SIM_make_attr_boolean(true));
    attr_value = SIM_make_attr_string("test");

    EXPECT_EQ(static_cast<attr_value_t>(attr_value).private_kind,
              Sim_Val_String);
}

TEST_F(AttrValueTest, Destructor) {
    {
        AttrValue attr_value(SIM_make_attr_string("test"));
        EXPECT_EQ(static_cast<attr_value_t>(attr_value).private_kind,
                  Sim_Val_String);
    }

    EXPECT_EQ(Stubs::instance_.sim_attr_free_cnt_, sim_attr_free_cnt_ + 1);
}

AttrValue get_AttrValue() {
    return AttrValue(SIM_make_attr_string("test"));
}

// Performance related test to ensure that NRVO optimizations are applied
TEST_F(AttrValueTest, NamedReturnValueOptimization) {
    {
        AttrValue attr_value = get_AttrValue();
        EXPECT_EQ(static_cast<attr_value_t>(attr_value).private_kind,
                  Sim_Val_String);
    }

    // only one dtor is called since named return value optimization (NRVO)
    // From MSVC 2015, NRVO is by default enabled thus only one dtor is called
    EXPECT_EQ(Stubs::instance_.sim_attr_free_cnt_, sim_attr_free_cnt_ + 1);
}
