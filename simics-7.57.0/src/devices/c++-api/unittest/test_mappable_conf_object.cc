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

#include <simics/mappable-conf-object.h>

#include <gtest/gtest.h>

#include <stdexcept>
#include <string>
#include "mock/gtest_extensions.h"  // EXPECT_PRED_THROW
#include "mock/stubs.h"

namespace {
bool checkNullIface(const std::exception &ex) {
    EXPECT_STREQ(ex.what(), "Cannot set with NULL interface");
    return true;
}

bool checkEmptyName(const std::exception &ex) {
    EXPECT_STREQ(ex.what(), "Cannot set with empty name string");
    return true;
}
}  // namespace

TEST(TestMappableConfObject, TestMapNameToInterfaceObject) {
    const char *test_str = "test_str";
    simics::MapNameToInterfaceObject<const char> obj;

    // Get from empty
    EXPECT_EQ(obj.get_iface("first"), nullptr);

    // Set with nullptr iface will throw
    EXPECT_PRED_THROW(obj.set_iface("first", nullptr),
                      std::invalid_argument, checkNullIface);

    // Set with empty string will throw
    EXPECT_PRED_THROW(obj.set_iface("", test_str),
                      std::invalid_argument, checkEmptyName);

    obj.set_iface("first", test_str);
    EXPECT_EQ(obj.get_iface("first"), test_str);

    obj.erase_iface("first");
    EXPECT_EQ(obj.get_iface("first"), nullptr);

    // Erase a non-exist name is a nop
    obj.erase_iface("first");

    // Copy-able
    simics::MapNameToInterfaceObject<const char> copied_obj = obj;
}

using simics::MappableConfObject;

class MappableConfObjectTest : public ::testing::Test {
  protected:
    simics::ConfObjectRef mock_conf_object_ref;
    MappableConfObject obj;

    MappableConfObjectTest() : obj(mock_conf_object_ref) {}

    void SetUp() override {
        log_error_cnt_ = Stubs::instance_.sim_log_error_cnt_;
        log_info_cnt_ = Stubs::instance_.sim_log_info_cnt_;
        Stubs::instance_.sim_object_is_configured_ret_ = false;
    }

    void TearDown() override {
        Stubs::instance_.sim_object_is_configured_obj_ = nullptr;
        Stubs::instance_.sim_object_is_configured_ret_ = false;
    }

    size_t log_error_cnt_ {0};
    size_t log_info_cnt_ {0};
};

TEST_F(MappableConfObjectTest, Constructor) {
    // CTOR with ConfObjectRef
    MappableConfObject obj(mock_conf_object_ref);
    EXPECT_EQ(obj.obj(), mock_conf_object_ref);
}

TEST_F(MappableConfObjectTest, ControlInterface) {
    auto b_iface = reinterpret_cast<simics::BankInterface *>(0xa);
    obj.set_iface("b0", b_iface);
    EXPECT_EQ(obj.get_iface<simics::BankInterface>("b0"), b_iface);
    obj.erase_iface<simics::BankInterface>("b0");
    EXPECT_EQ(obj.get_iface<simics::BankInterface>("b0"), nullptr);

    auto r_iface = reinterpret_cast<simics::RegisterInterface *>(0xb);
    obj.set_iface("r0", r_iface);
    EXPECT_EQ(obj.get_iface<simics::RegisterInterface>("r0"), r_iface);
    EXPECT_EQ(obj.get_iface(simics::hash_str("r0")), r_iface);
    obj.erase_iface<simics::RegisterInterface>("r1");
    EXPECT_EQ(obj.get_iface<simics::RegisterInterface>("r0"), r_iface);

    auto f_iface = reinterpret_cast<simics::FieldInterface *>(0xc);
    obj.set_iface("f0", f_iface);
    obj.set_iface("f1", f_iface);
    EXPECT_EQ(obj.get_iface<simics::FieldInterface>("f1"), f_iface);
    obj.erase_iface<simics::FieldInterface>("f1");
    EXPECT_EQ(obj.get_iface<simics::FieldInterface>("f0"), f_iface);

    EXPECT_EQ(obj.get_iface<simics::BankInterface>("f0"), nullptr);

    // Test error handling
    obj.set_iface<simics::BankInterface>("b0", nullptr);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, ++log_error_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Cannot set with NULL interface");
}

TEST_F(MappableConfObjectTest, Finalized) {
    auto b_iface = reinterpret_cast<simics::BankInterface *>(0xa);
    Stubs::instance_.sim_object_is_configured_ret_ = true;

    obj.set_iface("b0", b_iface);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, ++log_error_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
                      "Cannot set interface for b0 when ConfObject"
                      " has been finalized");
}

TEST_F(MappableConfObjectTest, WriteProtectIfaceMaps) {
    // Test custom behavior of iface_is_overwriteable
    simics::ConfObjectRef mock_obj(reinterpret_cast<conf_object_t *>(0xc0ffee));
    simics::MappableConfObject obj(mock_obj);

    // Test default overwriteable is true
    auto b_iface1 = reinterpret_cast<simics::BankInterface *>(0xa);
    obj.set_iface("b0", b_iface1);
    EXPECT_EQ(obj.get_iface<simics::BankInterface>("b0"), b_iface1);
    // No logs for the first set
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, log_info_cnt_);

    auto b_iface2 = reinterpret_cast<simics::BankInterface *>(0xb);
    obj.set_iface("b0", b_iface2);
    EXPECT_EQ(obj.get_iface<simics::BankInterface>("b0"), b_iface2);
    // logs when overridden
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, ++log_info_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
              "Interface for b0 overridden");

    // Test when write protected
    obj.write_protect_iface_maps(true);
    obj.set_iface("b0", b_iface1);
    EXPECT_EQ(obj.get_iface<simics::BankInterface>("b0"), b_iface2);
    // logs when cannot overridden
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, ++log_info_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
              "Interface for b0 ignored since iface_map is write protected");
}

TEST_F(MappableConfObjectTest, GetBankMemory) {
    auto *m0 = obj.get_bank_memory("name0");
    auto *m1 = obj.get_bank_memory("_name1");
    EXPECT_EQ(obj.get_bank_memory("name0"), m0);
    EXPECT_EQ(obj.get_bank_memory("_name1"), m1);

    std::string_view idx0 {"0"};
    EXPECT_EQ(obj.get_bank_memory(std::string("name") + idx0.data()), m0);
    std::string_view name1 {"name1"};
    EXPECT_EQ(obj.get_bank_memory(std::string("_") + name1.data()), m1);
}
