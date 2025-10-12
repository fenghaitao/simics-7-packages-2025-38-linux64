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

#include <simics/hierarchical-object.h>

#include <gtest/gtest.h>

#include <string>
#include <utility>  // move

#include "mock/gtest_extensions.h"  // EXPECT_PRED_THROW
#include "mock/mock-object.h"
#include "mock/stubs.h"

namespace {
bool checkInvalidName(const std::exception &ex) {
    auto message = std::string(ex.what());
    EXPECT_EQ(message.substr(0, message.rfind(':')),
              "Cannot set with invalid name string");
    return true;
}

bool checkNoBankObj(const std::exception &ex) {
    EXPECT_STREQ(ex.what(), "Unable to initialize the HierarchicalObject 'b0'"
                 " instance. Register the BankPort 'bank.b0' for logging"
                 " purposes.");
    return true;
}

bool checkNullObj(const std::exception &ex) {
    EXPECT_STREQ(ex.what(),
                 "HierarchicalObject cannot be constructed"
                 " from a NULL dev_obj");
    return true;
}
}  // namespace

class MockMappableConfObject : public simics::MappableConfObject {
  public:
    using MappableConfObject::MappableConfObject;
};

class HierarchicalObjectTest : public ::testing::Test {
  protected:
    void SetUp() override {
        Stubs::instance_.sim_object_descendant_ret_ = mock_obj.obj().object();
        Stubs::instance_.sim_object_is_configured_ret_ = true;
        log_critical_count_ = Stubs::instance_.sim_log_critical_cnt_;
        log_error_count_ = Stubs::instance_.sim_log_error_cnt_;
    }

    void TearDown() override {
        Stubs::instance_.sim_object_descendant_ret_ = nullptr;
        Stubs::instance_.sim_object_is_configured_ret_ = false;
    }

    MockObject mock_obj {reinterpret_cast<conf_object_t *>(0xc0ffee), "dev"};
    simics::MappableConfObject map_obj {mock_obj.obj()};
    size_t log_critical_count_;
    size_t log_error_count_;
};

TEST_F(HierarchicalObjectTest, CTORError) {
    // Null obj will throw
    EXPECT_PRED_THROW(simics::HierarchicalObject obj(nullptr, "b0"),
                      std::invalid_argument, checkNullObj);

    // Empty name string will throw
    EXPECT_PRED_THROW(simics::HierarchicalObject obj(&map_obj, ""),
                      std::invalid_argument, checkInvalidName);

    Stubs::instance_.sim_object_descendant_ret_ = nullptr;
    // No bank/port object bank.b0 will throw
    EXPECT_PRED_THROW(simics::HierarchicalObject obj(&map_obj, "b0"),
                      std::invalid_argument, checkNoBankObj);

    // Invalid character in the name will throw
    EXPECT_PRED_THROW(simics::HierarchicalObject obj(&map_obj, "$b"),
                      std::invalid_argument, checkInvalidName);

    // Name cannot start with a number
    EXPECT_PRED_THROW(simics::HierarchicalObject obj(&map_obj, "8b"),
                      std::invalid_argument, checkInvalidName);

    // Cannot contain more than 3 levels
    EXPECT_PRED_THROW(simics::HierarchicalObject obj(&map_obj, "b.r.f.x"),
                      std::invalid_argument, checkInvalidName);

    // Cannot contain two consecutive separators
    EXPECT_PRED_THROW(simics::HierarchicalObject obj(&map_obj, "br..f"),
                      std::invalid_argument, checkInvalidName);

    // Cannot end with separator
    EXPECT_PRED_THROW(simics::HierarchicalObject obj(&map_obj, "br."),
                      std::invalid_argument, checkInvalidName);
}

namespace {
bool checkInvalidHierarchicalName(const std::exception &ex) {
    EXPECT_STREQ(ex.what(),
                 "Invalid hierarchical name string: a.b.c.d");
    return true;
}
}

TEST(TestHierarchicalObject, TestStaticMethods) {
    EXPECT_FALSE(simics::HierarchicalObject::is_valid_hierarchical_name(""));
    EXPECT_FALSE(simics::HierarchicalObject::is_valid_hierarchical_name("0b"));
    EXPECT_FALSE(simics::HierarchicalObject::is_valid_hierarchical_name("[b]"));
    EXPECT_FALSE(simics::HierarchicalObject::is_valid_hierarchical_name("_b"));
    EXPECT_FALSE(simics::HierarchicalObject::is_valid_hierarchical_name("b$"));
    EXPECT_FALSE(
        simics::HierarchicalObject::is_valid_hierarchical_name("b.r.f.x"));
    EXPECT_FALSE(
        simics::HierarchicalObject::is_valid_hierarchical_name("br..f"));
    EXPECT_FALSE(simics::HierarchicalObject::is_valid_hierarchical_name("br."));
    EXPECT_FALSE(simics::HierarchicalObject::is_valid_hierarchical_name(".b"));
    EXPECT_TRUE(simics::HierarchicalObject::is_valid_hierarchical_name("b"));
    EXPECT_TRUE(simics::HierarchicalObject::is_valid_hierarchical_name("b0"));
    EXPECT_TRUE(simics::HierarchicalObject::is_valid_hierarchical_name("b.r"));
    EXPECT_TRUE(
        simics::HierarchicalObject::is_valid_hierarchical_name("b.r.f"));
    EXPECT_TRUE(
        simics::HierarchicalObject::is_valid_hierarchical_name("b[0]"));
    EXPECT_TRUE(
        simics::HierarchicalObject::is_valid_hierarchical_name("b[0].r"));
    EXPECT_TRUE(
        simics::HierarchicalObject::is_valid_hierarchical_name("b[0].r.f"));
    EXPECT_TRUE(
        simics::HierarchicalObject::is_valid_hierarchical_name("b[0].r[1].f"));
    EXPECT_TRUE(
        simics::HierarchicalObject::is_valid_hierarchical_name(
            "b[0].r[1].f[2]"));
    EXPECT_FALSE(simics::HierarchicalObject::is_valid_hierarchical_name(
                 "a.b.c.d"));

    EXPECT_EQ(simics::HierarchicalObject::level_of_hierarchical_name("b"), 0);
    EXPECT_EQ(simics::HierarchicalObject::level_of_hierarchical_name("b.r"), 1);
    EXPECT_EQ(
        simics::HierarchicalObject::level_of_hierarchical_name("b.r.f"), 2);
    EXPECT_EQ(
        simics::HierarchicalObject::level_of_hierarchical_name("b[0]"), 0);
    EXPECT_EQ(
        simics::HierarchicalObject::level_of_hierarchical_name("b[0].r"), 1);
    EXPECT_EQ(
        simics::HierarchicalObject::level_of_hierarchical_name("b[0].r.f"), 2);
    EXPECT_EQ(
        simics::HierarchicalObject::level_of_hierarchical_name(
            "b[0].r[1].f"), 2);
    EXPECT_EQ(
        simics::HierarchicalObject::level_of_hierarchical_name(
            "b[0].r[1].f[2]"), 2);
    // Invalid hierarchical name will throw
    EXPECT_PRED_THROW(simics::HierarchicalObject::level_of_hierarchical_name(
                      "a.b.c.d"),
                      std::invalid_argument, checkInvalidHierarchicalName);
}

TEST_F(HierarchicalObjectTest, ClassMethods) {
    simics::HierarchicalObject obj {&map_obj, "b0"};

    EXPECT_EQ(obj.hierarchical_name(), "b0");
    EXPECT_EQ(obj.bank_name(), "b0");
    EXPECT_EQ(obj.bank_obj_ref(), mock_obj.obj());
    EXPECT_EQ(obj.parent_name(), "");

    MockMappableConfObject map_obj2 {mock_obj.obj()};
    simics::HierarchicalObject obj2 {&map_obj2, "b1"};
    auto *cc_obj = obj2.dev_ptr<MockMappableConfObject>();
    EXPECT_EQ(cc_obj, &map_obj2);

    // Test indices is allowed in the name
    simics::HierarchicalObject obj3 {&map_obj, "b[0]"};
    EXPECT_EQ(obj3.hierarchical_name(), "b[0]");
    EXPECT_EQ(obj3.name(), "b[0]");

    // Test multiple levels name
    simics::HierarchicalObject obj4 {&map_obj, "b0.r1.f4"};
    EXPECT_EQ(obj4.hierarchical_name(), "b0.r1.f4");
    EXPECT_EQ(obj4.name(), "f4");
    EXPECT_EQ(obj4.bank_name(), "b0");
    EXPECT_EQ(obj4.parent_name(), "b0.r1");

    simics::HierarchicalObject obj5 {&map_obj, "b0.r[1].f4"};
    EXPECT_EQ(obj5.hierarchical_name(), "b0.r[1].f4");
    EXPECT_EQ(obj5.name(), "f4");
}

TEST_F(HierarchicalObjectTest, TestDelete) {
    // This is OK since obj1 has the same life time with bank_obj
    simics::HierarchicalObject obj1 {&map_obj, "b0"};

    // This is not OK since obj2 is deleted before bank_obj
    {
        simics::HierarchicalObject obj2 {&map_obj, "b0"};
    }
    EXPECT_EQ(++log_critical_count_,
              Stubs::instance_.sim_log_critical_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_critical_,
              "Hierarchical object can't be deleted during the simulation");
}

TEST_F(HierarchicalObjectTest, TestLookUpBank) {
    // Lookup bank from this bank object
    simics::HierarchicalObject obj {&map_obj, "b0"};

    Stubs::instance_.sim_object_is_configured_ret_ = false;
    obj.lookup_bank("b0");
    EXPECT_EQ(++log_error_count_, Stubs::instance_.sim_log_error_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Look up bank should be called after finalize phase");

    Stubs::instance_.sim_object_is_configured_ret_ = true;
    obj.lookup_bank("0b");
    EXPECT_EQ(++log_error_count_, Stubs::instance_.sim_log_error_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Invalid bank name: 0b");

    obj.lookup_bank("b0.r1");
    EXPECT_EQ(++log_error_count_, Stubs::instance_.sim_log_error_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Invalid bank name: b0.r1");

    obj.lookup_bank("b0");
    EXPECT_EQ(++log_error_count_, Stubs::instance_.sim_log_error_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_, "Lookup bank failed: b0");

    auto *bank_obj = reinterpret_cast<simics::BankInterface *>(0xc0ffee);
    Stubs::instance_.sim_object_is_configured_ret_ = false;
    map_obj.set_iface<simics::BankInterface>("b0", bank_obj);
    Stubs::instance_.sim_object_is_configured_ret_ = true;
    EXPECT_EQ(obj.lookup_bank("b0"), bank_obj);

    // Lookup bank from another bank
    simics::HierarchicalObject obj2 {&map_obj, "b1"};
    EXPECT_EQ(obj2.lookup_bank("b0"), bank_obj);

    // Lookup bank from a register object
    simics::HierarchicalObject obj3 {&map_obj, "b0.r1"};
    EXPECT_EQ(obj3.lookup_bank("b0"), bank_obj);

    // Lookup bank from another register object
    simics::HierarchicalObject obj4 {&map_obj, "b1.r0"};
    EXPECT_EQ(obj4.lookup_bank("b0"), bank_obj);

    // Lookup bank from a field object
    simics::HierarchicalObject obj5 {&map_obj, "b0.r1.f2"};
    EXPECT_EQ(obj5.lookup_bank("b0"), bank_obj);
}

TEST_F(HierarchicalObjectTest, TestLookUpRegister) {
    // Lookup register from this bank object
    simics::HierarchicalObject obj {&map_obj, "b0"};

    Stubs::instance_.sim_object_is_configured_ret_ = false;
    obj.lookup_register("r1");
    EXPECT_EQ(++log_error_count_, Stubs::instance_.sim_log_error_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Look up register should be called after finalize phase");

    Stubs::instance_.sim_object_is_configured_ret_ = true;
    obj.lookup_register("0r");
    EXPECT_EQ(++log_error_count_, Stubs::instance_.sim_log_error_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Invalid register name: 0r");

    obj.lookup_register("b0.r1.f2");
    EXPECT_EQ(++log_error_count_, Stubs::instance_.sim_log_error_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Invalid register name: b0.r1.f2");

    obj.lookup_register("b0");
    EXPECT_EQ(++log_error_count_, Stubs::instance_.sim_log_error_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Lookup register failed: b0");

    obj.lookup_register("b0.r1");
    EXPECT_EQ(++log_error_count_, Stubs::instance_.sim_log_error_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_, "Lookup register failed: b0.r1");

    auto *register_obj = \
        reinterpret_cast<simics::RegisterInterface *>(0xc0ffee);
    Stubs::instance_.sim_object_is_configured_ret_ = false;
    map_obj.set_iface<simics::RegisterInterface>("b0.r1", register_obj);
    Stubs::instance_.sim_object_is_configured_ret_ = true;
    EXPECT_EQ(obj.lookup_register("b0.r1"), register_obj);

    // Lookup register from another bank
    simics::HierarchicalObject obj2 {&map_obj, "b1"};
    EXPECT_EQ(obj2.lookup_register("r1"), nullptr);
    EXPECT_EQ(obj2.lookup_register("b0.r1"), register_obj);

    // Lookup register from a register object
    simics::HierarchicalObject obj3 {&map_obj, "b0.r1"};
    EXPECT_EQ(obj3.lookup_register("r1"), register_obj);
    EXPECT_EQ(obj3.lookup_register("b0.r1"), register_obj);

    // Lookup register from another register object
    simics::HierarchicalObject obj4 {&map_obj, "b1.r0"};
    EXPECT_EQ(obj4.lookup_register("r1"), nullptr);
    EXPECT_EQ(obj4.lookup_register("b0.r1"), register_obj);

    // Lookup register from a field object
    simics::HierarchicalObject obj5 {&map_obj, "b0.r1.f2"};
    EXPECT_EQ(obj5.lookup_register("r1"), register_obj);
    EXPECT_EQ(obj5.lookup_register("b0.r1"), register_obj);

    // Lookup register from another field object
    simics::HierarchicalObject obj6 {&map_obj, "b1.r0.f3"};
    EXPECT_EQ(obj6.lookup_register("r1"), nullptr);
    EXPECT_EQ(obj6.lookup_register("b0.r1"), register_obj);
}

TEST_F(HierarchicalObjectTest, TestLookUpField) {
    // Lookup field from this bank object
    simics::HierarchicalObject obj {&map_obj, "b0"};

    Stubs::instance_.sim_object_is_configured_ret_ = false;
    obj.lookup_field("r1.f2");
    EXPECT_EQ(++log_error_count_, Stubs::instance_.sim_log_error_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Look up field should be called after finalize phase");

    Stubs::instance_.sim_object_is_configured_ret_ = true;
    obj.lookup_field("0r.f2");
    EXPECT_EQ(++log_error_count_, Stubs::instance_.sim_log_error_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Invalid field name: 0r.f2");

    obj.lookup_field("b0");
    EXPECT_EQ(++log_error_count_, Stubs::instance_.sim_log_error_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Unable to lookup a field with field name only in a bank");

    obj.lookup_field("b0.r1");
    EXPECT_EQ(++log_error_count_, Stubs::instance_.sim_log_error_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_, "Lookup field failed: b0.r1");

    obj.lookup_field("b0.r1.f2");
    EXPECT_EQ(++log_error_count_, Stubs::instance_.sim_log_error_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_, "Lookup field failed: b0.r1.f2");

    auto *field_obj = \
        reinterpret_cast<simics::FieldInterface *>(0xc0ffee);
    Stubs::instance_.sim_object_is_configured_ret_ = false;
    map_obj.set_iface<simics::FieldInterface>("b0.r1.f2", field_obj);
    Stubs::instance_.sim_object_is_configured_ret_ = true;
    EXPECT_EQ(obj.lookup_field("b0.r1.f2"), field_obj);

    // Lookup register from another bank
    simics::HierarchicalObject obj2 {&map_obj, "b1"};
    EXPECT_EQ(obj2.lookup_field("r1.f2"), nullptr);
    EXPECT_EQ(obj2.lookup_field("b0.r1.f2"), field_obj);

    // Lookup register from a register object
    simics::HierarchicalObject obj3 {&map_obj, "b0.r1"};
    EXPECT_EQ(obj3.lookup_field("f2"), field_obj);
    EXPECT_EQ(obj3.lookup_field("r1.f2"), field_obj);

    // Lookup register from another register object
    simics::HierarchicalObject obj4 {&map_obj, "b1.r0"};
    EXPECT_EQ(obj4.lookup_field("f2"), nullptr);
    EXPECT_EQ(obj4.lookup_field("b0.r1.f2"), field_obj);

    // Lookup register from a field object
    simics::HierarchicalObject obj5 {&map_obj, "b0.r1.f2"};
    EXPECT_EQ(obj5.lookup_field("f2"), field_obj);
    EXPECT_EQ(obj5.lookup_field("b0.r1.f2"), field_obj);

    // Lookup register from another field object
    simics::HierarchicalObject obj6 {&map_obj, "b1.r0.f3"};
    EXPECT_EQ(obj6.lookup_field("f2"), nullptr);
    EXPECT_EQ(obj6.lookup_field("b0.r1.f2"), field_obj);
}

TEST_F(HierarchicalObjectTest, TestHierarchicalObjectMoveSelfAssignment) {
    simics::HierarchicalObject obj {&map_obj, "b0"};
    auto orig_name = obj.hierarchical_name();
    auto orig_bank_obj_ref = obj.bank_obj_ref();

    // Move self-assignment
    obj = std::move(obj);

    // State should be unchanged
    EXPECT_EQ(obj.hierarchical_name(), orig_name);
    EXPECT_EQ(obj.bank_obj_ref(), orig_bank_obj_ref);
}
