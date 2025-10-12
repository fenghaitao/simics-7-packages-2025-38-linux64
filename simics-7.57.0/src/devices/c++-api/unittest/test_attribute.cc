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

#include <simics/attribute.h>

#include <gtest/gtest.h>

class TestObject : public simics::ConfObject {
  public:
    explicit TestObject(conf_object_t *obj = nullptr)
        : simics::ConfObject(obj) {
    }

    int a_int { 0 };
};

// Test that subclass also works; i.e. that we can use static_cast and there is
// no need for dynamic_cast in ATTR_CLS_VAR macro
class TestDerived : public TestObject {
  public:
    using TestObject::TestObject;
};

TEST(TestAttribute, TestAttributeAccessorCTOR) {
    auto a = simics::AttributeAccessor<TestObject,
                                       int TestObject::*,
                                       &TestObject::a_int>();
    EXPECT_NE(a.getter, nullptr);
    EXPECT_NE(a.setter, nullptr);
}

TEST(TestAttribute, TestAttributeCTOR) {
    auto a1 = simics::Attribute("name", "type", "desc",
                                nullptr, nullptr, Sim_Attr_Optional);
    EXPECT_EQ(a1.name(), "name");
    EXPECT_EQ(a1.type(), "type");
    EXPECT_EQ(a1.desc(), "desc");
    EXPECT_EQ(a1.getter(), nullptr);
    EXPECT_EQ(a1.setter(), nullptr);
    EXPECT_EQ(a1.attr(), Sim_Attr_Optional);

    auto a2 = simics::Attribute("name", "type", "desc", nullptr, nullptr);
    EXPECT_EQ(a2.attr(), Sim_Attr_Pseudo);

    auto a3 = simics::Attribute("name", "type", "desc",
                                (simics::attr_getter)0x1,
                                (simics::attr_setter)0x2);
    EXPECT_EQ(a3.attr(), Sim_Attr_Optional);

    auto a4 = simics::Attribute("name", "type", "desc",
                                (simics::attr_getter)0x1, nullptr);
    EXPECT_EQ(a4.attr(), Sim_Attr_Pseudo);

    auto a5 = simics::Attribute("name", "type", "desc", nullptr,
                                (simics::attr_setter)0x2);
    EXPECT_EQ(a5.attr(), Sim_Attr_Pseudo);

    auto a6 = simics::Attribute("name", "type", "desc",
                                simics::AttributeAccessor<TestObject,
                                int TestObject::*, &TestObject::a_int>());
    EXPECT_EQ(a6.attr(), Sim_Attr_Optional);
    EXPECT_NE(a6.getter(), nullptr);
    EXPECT_NE(a6.setter(), nullptr);

    auto a7 = simics::Attribute("name", "type", "desc",
                                ATTR_CLS_VAR(TestObject, a_int));
    EXPECT_NE(a7.getter(), nullptr);
    EXPECT_NE(a7.setter(), nullptr);

    auto a8 = simics::Attribute("name", ATTR_TYPE_STR(TestObject::a_int),
                                "desc", nullptr, nullptr);
    EXPECT_EQ(a8.type(), "i");

    auto a9 = simics::Attribute("name", "type", "desc",
                                ATTR_CLS_VAR(TestDerived, a_int));
    EXPECT_NE(a9.getter(), nullptr);
    EXPECT_NE(a9.setter(), nullptr);

    auto a10 = simics::Attribute("name", ATTR_TYPE_STR(TestDerived::a_int),
                                 "desc", nullptr, nullptr);
    EXPECT_EQ(a10.type(), "i");
}

TEST(TestAttribute, ClassAttribute) {
    auto a1 = simics::ClassAttribute("name", "type", "desc",
                                     nullptr, nullptr, Sim_Attr_Pseudo);
    EXPECT_EQ(a1.name(), "name");
    EXPECT_EQ(a1.type(), "type");
    EXPECT_EQ(a1.desc(), "desc");
    EXPECT_EQ(a1.getter(), nullptr);
    EXPECT_EQ(a1.setter(), nullptr);
    EXPECT_EQ(a1.attr(), Sim_Attr_Pseudo);
}
