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

#include <simics/register.h>

#include <gtest/gtest.h>
#include <simics/attr-value.h>
#include <simics/attribute-traits.h>
#include <simics/field-templates.h>

#include <initializer_list>
#include <limits>
#include <string>
#include <utility>
#include <vector>

#include "mock/gtest_extensions.h"  // EXPECT_PRED_THROW
#include "mock/mock-bank.h"
#include "mock/stubs.h"
#include "unittest/bank-object-fixture.h"

TEST_F(BankObjectFixture, TestRegisterCTOR) {
    EXPECT_FALSE(std::is_copy_constructible<simics::Register>::value);
    EXPECT_TRUE(std::is_move_constructible<simics::Register>::value);

    std::string reg_name {"b0.r1"};

    // Test Register(MappableConfObject *dev_obj,
    //               const std::string &hierarchical_name)
    // dev_obj cannot be nullptr
    EXPECT_PRED_THROW(simics::Register(nullptr, reg_name),
                      std::invalid_argument,
                      [](const std::exception &ex) {
                          EXPECT_STREQ(ex.what(),
                              "HierarchicalObject cannot be constructed "
                              "from a NULL dev_obj");
                      });

    // Empty name is not allowed
    EXPECT_PRED_THROW(simics::Register(&map_obj, ""),
                      std::invalid_argument,
                      [](const std::exception &ex) {
                          EXPECT_STREQ(ex.what(),
                              "Cannot set with invalid name string: ");
                      });

    // The name has incorrect hierarchy level
    EXPECT_PRED_THROW(simics::Register(&map_obj, "b1"),
                      std::invalid_argument,
                      [](const std::exception &ex) {
                          EXPECT_STREQ(ex.what(),
                              "Register name (b1) does not match the register "
                              "level (bankA.registerB)");
                      });

    auto r1 = simics::Register(&map_obj, reg_name);
    auto *iface = map_obj.get_iface<simics::RegisterInterface>(reg_name);
    EXPECT_EQ(iface, &r1);

    // Test move operator
    auto r1_move {std::move(r1)};
    EXPECT_EQ(r1_move.name(), "r1");
    iface = map_obj.get_iface<simics::RegisterInterface>("b0.r1");
    EXPECT_EQ(iface, &r1_move);

    r1 = std::move(r1_move);
    EXPECT_EQ(r1.name(), "r1");
    iface = map_obj.get_iface<simics::RegisterInterface>("b0.r1");
    EXPECT_EQ(iface, &r1);

    // The indices are allowed in the name
    auto r_array = simics::Register(&map_obj, "b0.r[6]");
    EXPECT_EQ(r_array.name(), "r[6]");
}

TEST_F(BankObjectFixture, TestRegisterSetBytePointers) {
    auto r = simics::Register(&map_obj, "b0.r6");
    auto log_error_count_before = Stubs::instance_.sim_log_error_cnt_;

    // Set to empty vector
    r.set_byte_pointers({});
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
              log_error_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "The supported register size is [1-8] bytes, but got 0");

    log_error_count_before = Stubs::instance_.sim_log_error_cnt_;
    // Set to size>8 vector
    r.set_byte_pointers({
            bytes_.data(), bytes_.data() + 1,
            bytes_.data() + 2, bytes_.data() + 3,
            bytes_.data() + 4, bytes_.data() + 5,
            bytes_.data() + 6, bytes_.data() + 7,
            bytes_.data() + 8});
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
              log_error_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "The supported register size is [1-8] bytes, but got 9");

    log_error_count_before = Stubs::instance_.sim_log_error_cnt_;
    // Duplicated items
    r.set_byte_pointers({bytes_.data(), bytes_.data()});
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
              log_error_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "The byte_pointers contains duplicate items");

    log_error_count_before = Stubs::instance_.sim_log_error_cnt_;
    // Cannot reset
    r.set_byte_pointers({bytes_.data()});
    r.set_byte_pointers({bytes_.data()});
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
              log_error_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Multiple calls to Register::set_byte_pointers() detected."
              " Make sure register name (b0.r6) is not duplicated within"
              " the same bank");
}

TEST_F(BankObjectFixture, TestRegisterInit) {
    Stubs::instance_.sim_register_attribute_with_user_data_names_.clear();
    auto r = simics::Register(&map_obj, "b0.r6");
    r.set_byte_pointers({pointers_[0]});
    auto log_error_count_before = Stubs::instance_.sim_log_error_cnt_;

    // Too large number of bytes
    r.init("", 16, 0);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "The supported register size is [1-8] bytes, but got 16");

    log_error_count_before = Stubs::instance_.sim_log_error_cnt_;
    // Too small number of bytes
    r.init("", 0, 0);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "The supported register size is [1-8] bytes, but got 0");

    r.init("", 1, 0);
    EXPECT_EQ(r.number_of_bytes(), 1);
    EXPECT_EQ(r.is_read_only(), false);
    EXPECT_EQ(r.is_mapped(), true);
}

TEST_F(BankObjectFixture, TestRegisterBeingRegisteredAsAttribute) {
    Stubs::instance_.sim_register_attribute_with_user_data_names_.clear();
    auto cnt_before =
        Stubs::instance_.sim_register_attribute_with_user_data_cnt_;
    auto r = simics::Register(&map_obj, "b0.r6");
    r.set_byte_pointers(pointers_);
    r.init("", 1, 0);

    EXPECT_EQ(Stubs::instance_.sim_register_attribute_with_user_data_cnt_,
              ++cnt_before);
    EXPECT_EQ(Stubs::instance_.sim_register_attribute_with_user_data_type_,
              "i");

    // Test get_attr
    // Empty register hash
    auto *get_attr = Stubs::instance_.last_get_attr_with_user_data_;
    simics::AttrValue attr1 {get_attr(bank_obj.obj(), nullptr)};
    EXPECT_EQ(SIM_attr_is_nil(attr1), true);

    // Empty register name
    simics::AttrValue attr2 {get_attr(bank_obj.obj(),
                             reinterpret_cast<void *>(simics::hash_str("")))};
    EXPECT_EQ(SIM_attr_is_nil(attr2), true);

    // Wrong register name
    simics::AttrValue attr3 {
        get_attr(bank_obj.obj(),
        reinterpret_cast<void *>(simics::hash_str("b0.r4")))};
    EXPECT_EQ(SIM_attr_is_nil(attr3), true);

    // Right register name
    simics::AttrValue attr4 {
        get_attr(bank_obj.obj(),
        reinterpret_cast<void *>(simics::hash_str("b0.r6")))};
    EXPECT_EQ(SIM_attr_is_integer(attr4), true);
    EXPECT_EQ(simics::attr_to_std<uint64_t>(attr4), r.get());

    r.set(0xdeadbeef);
    EXPECT_EQ(r.get(), 0xdeadbeef);
    // Check that the value is updated
    simics::AttrValue attr5 {
        get_attr(bank_obj.obj(),
        reinterpret_cast<void *>(simics::hash_str("b0.r6")))};
    EXPECT_EQ(simics::attr_to_std<uint64_t>(attr5), 0xdeadbeef);

    // Test set_attr
    // Empty register hash
    auto *set_attr = Stubs::instance_.last_set_attr_with_user_data_;
    auto set_ret1 = set_attr(bank_obj.obj(), nullptr, nullptr);
    EXPECT_EQ(set_ret1, Sim_Set_Interface_Not_Found);

    // Empty register name
    auto attr6 = SIM_make_attr_int64(0x12345678);
    auto set_ret2 = set_attr(
        bank_obj.obj(), &attr6,
        reinterpret_cast<void *>(simics::hash_str("")));
    EXPECT_EQ(set_ret2, Sim_Set_Interface_Not_Found);

    // Wrong register name
    auto set_ret3 = set_attr(
        bank_obj.obj(), &attr6,
        reinterpret_cast<void *>(simics::hash_str("b0.r4")));
    EXPECT_EQ(set_ret3, Sim_Set_Interface_Not_Found);

    // Right register name
    auto set_ret4 = set_attr(
        bank_obj.obj(), &attr6,
        reinterpret_cast<void *>(simics::hash_str("b0.r6")));
    EXPECT_EQ(set_ret4, Sim_Set_Ok);
    // Check that the value is updated
    EXPECT_EQ(r.get(), 0x12345678);
}

TEST_F(BankObjectFixture, TestRegisterArrayBeingRegisteredAsAttribute) {
    Stubs::instance_.sim_register_attribute_with_user_data_names_.clear();
    auto cnt_before =
        Stubs::instance_.sim_register_attribute_with_user_data_cnt_;

    // Set parent
    MockBank bank;
    bank.name_ = "b0";
    bank.dev_obj_ = &map_obj;
    map_obj.set_iface<simics::BankInterface>("b0", &bank);

    simics::register_memory_t pointers0_ {
        bytes_.data(), bytes_.data() + 1,
        bytes_.data() + 2, bytes_.data() + 3
    };
    auto r0 = simics::Register(&map_obj, "b0.r[0]");
    r0.set_byte_pointers(pointers0_);
    r0.init("", 4, 0);

    simics::register_memory_t pointers1_ {
        bytes_.data() + 4, bytes_.data() + 5,
        bytes_.data() + 6, bytes_.data() + 7
    };
    auto r1 = simics::Register(&map_obj, "b0.r[1]");
    r1.set_byte_pointers(pointers1_);
    r1.init("", 4, 0);

    EXPECT_EQ(Stubs::instance_.sim_register_attribute_with_user_data_cnt_,
              ++cnt_before);
    EXPECT_EQ(Stubs::instance_.sim_register_attribute_with_user_data_type_,
              "[i+]");

    auto *get_attr = Stubs::instance_.last_get_attr_with_user_data_;
    auto *set_attr = Stubs::instance_.last_set_attr_with_user_data_;
    simics::AttrValue attr {
        get_attr(bank_obj.obj(),
                 reinterpret_cast<void *>(simics::hash_str("b0.r[0]")))};
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    simics::AttrValue attr0 {SIM_attr_list_item(attr, 0)};
    EXPECT_EQ(SIM_attr_is_integer(attr0), true);
    EXPECT_EQ(simics::attr_to_std<uint64_t>(attr0), r0.get());

    attr = simics::std_to_attr<>(std::vector<uint64_t>{0x1234, 0x5678});
    attr_value_t attr_list = static_cast<attr_value_t>(attr);
    set_attr(bank_obj.obj(), &attr_list,
             reinterpret_cast<void *>(simics::hash_str("b0.r[0]")));
    EXPECT_EQ(r0.get(), 0x1234);
    EXPECT_EQ(r1.get(), 0x5678);
}

TEST_F(BankObjectFixture, TestRegisterMultiArrayBeingRegisteredAsAttribute) {
    Stubs::instance_.sim_register_attribute_with_user_data_names_.clear();
    auto cnt_before =
        Stubs::instance_.sim_register_attribute_with_user_data_cnt_;

    // Set parent
    MockBank bank;
    bank.name_ = "b0";
    bank.dev_obj_ = &map_obj;
    map_obj.set_iface<simics::BankInterface>("b0", &bank);

    simics::register_memory_t pointers00_ {
        bytes_.data(), bytes_.data() + 1,
    };
    simics::register_memory_t pointers01_ {
        bytes_.data() + 2, bytes_.data() + 3,
    };
    simics::register_memory_t pointers10_ {
        bytes_.data() + 4, bytes_.data() + 5,
    };
    simics::register_memory_t pointers11_ {
        bytes_.data() + 6, bytes_.data() + 7,
    };

    auto r00 = simics::Register(&map_obj, "b0.r[0][0]");
    r00.set_byte_pointers(pointers00_);
    r00.init("", 2, 0);

    auto r01 = simics::Register(&map_obj, "b0.r[0][1]");
    r01.set_byte_pointers(pointers01_);
    r01.init("", 2, 0);

    auto r10 = simics::Register(&map_obj, "b0.r[1][0]");
    r10.set_byte_pointers(pointers10_);
    r10.init("", 2, 0);

    auto r11 = simics::Register(&map_obj, "b0.r[1][1]");
    r11.set_byte_pointers(pointers11_);
    r11.init("", 2, 0);

    EXPECT_EQ(Stubs::instance_.sim_register_attribute_with_user_data_cnt_,
              ++cnt_before);
    EXPECT_EQ(Stubs::instance_.sim_register_attribute_with_user_data_type_,
              "[[i+]+]");

    auto *get_attr = Stubs::instance_.last_get_attr_with_user_data_;
    auto *set_attr = Stubs::instance_.last_set_attr_with_user_data_;
    simics::AttrValue attr {
        get_attr(bank_obj.obj(),
                 reinterpret_cast<void *>(simics::hash_str("b0.r[0][0]")))};
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    EXPECT_EQ(simics::attr_to_std<uint64_t>(
        SIM_attr_list_item(SIM_attr_list_item(attr, 0), 0)),
                           r00.get());

    std::vector<std::vector<uint64_t>> set_values {
        {0x1234, 0x5678}, {0x9abc, 0xdef0}
    };
    attr = simics::std_to_attr<>(set_values);
    attr_value_t attrlist = static_cast<attr_value_t>(attr);
    set_attr(bank_obj.obj(), &attrlist,
             reinterpret_cast<void *>(simics::hash_str("b0.r[0][0]")));
    EXPECT_EQ(r00.get(), 0x1234);
    EXPECT_EQ(r01.get(), 0x5678);
    EXPECT_EQ(r10.get(), 0x9abc);
    EXPECT_EQ(r11.get(), 0xdef0);
}

TEST_F(BankObjectFixture, TestRegisterOffset) {
    size_t no_offset = std::numeric_limits<std::size_t>::max();
    auto log_error_count_before = Stubs::instance_.sim_log_error_cnt_;

    // Nullptr reg_iface
    auto offset = simics::Register::offset(nullptr);
    EXPECT_EQ(offset, no_offset);
    // No log error expected since no log object to log on
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
              log_error_count_before);

    auto r = simics::Register(&map_obj, "b0.r6");
    // Register without parent set
    offset = simics::Register::offset(&r);
    EXPECT_EQ(offset, no_offset);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
              ++log_error_count_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Register has no parent, unable to find offset");

    // Set parent
    MockBank bank;
    bank.name_ = "b0";
    bank.dev_obj_ = &map_obj;
    map_obj.set_iface<simics::BankInterface>("b0", &bank);
    r.set_byte_pointers(pointers_);
    r.init("", 8, 0);

    offset = simics::Register::offset(&r);
    EXPECT_EQ(offset, no_offset);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
              ++log_error_count_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Register (r6) not found in parent bank (b0)");

    // Add r6 to b0
    bank.add_register("r6", std::string(""), 0xdead,
                      8, 0x89abcdef, std::vector<simics::field_t>());
    map_obj.set_iface<simics::RegisterInterface>("b0.r6", &r);

    offset = simics::Register::offset(&r);
    EXPECT_EQ(offset, 0xdead);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
              log_error_count_before);
}

class RegisterTestAddField : public simics::Register {
  public:
    using simics::Register::Register;
    using simics::Register::add_field;   // Make add_field public
};

TEST_F(BankObjectFixture, TestRegisterAddField) {
    auto r = RegisterTestAddField(&map_obj, "b0.r6");
    r.set_byte_pointers(pointers_);
    auto log_error_count_before = Stubs::instance_.sim_log_error_cnt_;

    // Add field with empty name
    r.add_field("", "", 1, 1);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, ++log_error_count_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Cannot add a field with empty name");

    // Invalid field bit: width = 0
    r.add_field("f1", "", 1, 0);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, ++log_error_count_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Cannot add a field with invalid width (0)");

    // Invalid field bit: width > 64
    r.add_field("f1", "", 1, 100);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, ++log_error_count_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Cannot add a field with invalid width (100)");

    // Invalid field bit: offset + width > 64
    r.add_field("f1", "", 10, 60);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, ++log_error_count_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Cannot add a field with invalid offset (10)");

    auto log_info_count_before = Stubs::instance_.sim_log_info_cnt_;
    // Valid field
    r.add_field("f1", "", 0, 32);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, log_error_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
              log_info_count_before + 2);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
              "Created default field b0.r6.f1");

    // Overlap field
    r.add_field("f2", "", 24, 24);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, ++log_error_count_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Cannot add field(f2): offset overlapped with existing fields "
              "on the register");
}

TEST_F(BankObjectFixture, TestRegisterParseField) {
    auto r = simics::Register(&map_obj, "b0.r6");
    r.set_byte_pointers(pointers_);

    auto log_error_count_before = Stubs::instance_.sim_log_error_cnt_;
    auto log_info_count_before = Stubs::instance_.sim_log_info_cnt_;
    // Valid field
    r.parse_field({"f1", "", 0, 32});
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, log_error_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
              log_info_count_before + 2);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
              "Created default field b0.r6.f1");

    log_error_count_before = Stubs::instance_.sim_log_error_cnt_;
    // Change field f1 is not allowed
    r.parse_field({"f1", "", 32, 32});
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, ++log_error_count_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Duplicated field name(f1) on same register");

    // Field array
    log_error_count_before = Stubs::instance_.sim_log_error_cnt_;
    log_info_count_before = Stubs::instance_.sim_log_info_cnt_;
    r.parse_field({"f_array[3 stride 4]", "test field array", 32, 2});
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before + 3 * 2);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
              "Created default field b0.r6.f_array[2]");

    // Multi-array
    r = simics::Register(&map_obj, "b0.r7");
    reset_register_memory();
    r.set_byte_pointers(pointers_);
    log_error_count_before = Stubs::instance_.sim_log_error_cnt_;
    log_info_count_before = Stubs::instance_.sim_log_info_cnt_;
    r.parse_field({"f_multi[3 stride 16][2][2 stride 2]",
                   "test multi array", 0, 1});
    auto fs = r.fields_info();
    for (int i = 0; i < 3; ++i) {
        for (int j = 0; j < 2; ++j) {
            for (int k = 0; k < 2; ++k) {
                const auto &[name, desc, offset, width] = fs[i * 4 + j * 2 + k];
                EXPECT_EQ(name,
                          "f_multi[" + std::to_string(i) + "]["
                          + std::to_string(j) + "]["
                          + std::to_string(k) + "]");
                EXPECT_EQ(desc, "test multi array");
                EXPECT_EQ(offset, i * 16 + j * 4 + k * 2);
                EXPECT_EQ(width, 1);
            }
        }
    }

    set_configured();
    r = simics::Register(&map_obj, "b0.r8");
    reset_register_memory();
    r.set_byte_pointers(pointers_);
    log_error_count_before = Stubs::instance_.sim_log_error_cnt_;
    r.parse_field({"f1", "", 0, 16});
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      ++log_error_count_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
                      "Cannot add fields for register (b0.r8) when device has"
                      " finalized");
}

TEST_F(BankObjectFixture, TestRegisterValue) {
    auto r1 = simics::Register(&map_obj, "b0.r1");
    r1.set_byte_pointers(pointers_);
    EXPECT_EQ(r1.number_of_bytes(), 8);

    auto log_info_count_before = Stubs::instance_.sim_log_info_cnt_;

    // Test set and get
    EXPECT_EQ(r1.get(), 0);
    r1.set(0xdeadbeef);
    EXPECT_EQ(r1.get(), 0xdeadbeef);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before);

    // Verify read with different value of enabled_bits
    EXPECT_EQ(r1.read(0), 0);
    EXPECT_EQ(r1.read(0xffff0000), 0xdead0000);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
                      "Partial read from register r1: bytes 2-3 -> 0xdead0000");
    EXPECT_EQ(r1.read(0x0000ffff), 0x0000beef);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before + 2);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
                      "Partial read from register r1: bytes 0-1 -> 0xbeef");
    EXPECT_EQ(r1.read(0x00ffff00), 0x00adbe00);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before + 3);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
                      "Partial read from register r1: bytes 1-2 -> 0xadbe00");
    EXPECT_EQ(r1.read(0x00ffff0000000000), 0);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before + 4);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
                      "Partial read from register r1: bytes 5-6 -> 0x0");
    // Non-byte aligned enable_bytes
    EXPECT_EQ(r1.read(0x00fff800), 0x00adb800);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before + 5);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
                      "Partial read from register r1: bits 11-23 -> 0xadb800");
    EXPECT_EQ(r1.read(0x001ff000), 0x000db000);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before + 6);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
                      "Partial read from register r1: bits 12-20 -> 0xdb000");

    auto log_error_count_before = Stubs::instance_.sim_log_error_cnt_;

    // Malformed enable_bytes
    EXPECT_EQ(r1.read(0x00202300), 0);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
                      "enabled_bits(0x202300) is malformed: does not contain"
                      " consecutive ones");

    log_info_count_before = Stubs::instance_.sim_log_info_cnt_;

    // Verify write with different value of enabled_bits
    auto write_value = 0x123456789abcdef;
    r1.write(write_value, 0);
    EXPECT_EQ(r1.get(), 0xdeadbeef);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before);
    r1.write(write_value, 0xffff0000);
    EXPECT_EQ(r1.get(), 0x89abbeef);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
                      "Partial write to register r1: bytes 2-3 <- 0x89ab0000");

    r1.set(0xdeadbeef);
    r1.write(write_value, 0x0000ffff);
    EXPECT_EQ(r1.get(), 0xdeadcdef);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before + 2);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
                      "Partial write to register r1: bytes 0-1 <- 0xcdef");

    r1.set(0xdeadbeef);
    r1.write(write_value, 0x00ffff00);
    EXPECT_EQ(r1.get(), 0xdeabcdef);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before + 3);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
                      "Partial write to register r1: bytes 1-2 <- 0xabcd00");

    r1.set(0xdeadbeef);
    r1.write(write_value, 0x00ffff0000000000);
    EXPECT_EQ(r1.get(), 0x234500deadbeef);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before + 4);
    EXPECT_EQ(
            Stubs::instance_.SIM_log_info_,
            "Partial write to register r1: bytes 5-6 <- 0x23450000000000");

    // Non-byte aligned enable_bytes
    r1.set(0xdeadbeef);
    r1.write(write_value, 0x00fff800);
    EXPECT_EQ(r1.get(), 0xdeabceef);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before + 5);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
                      "Partial write to register r1: bits 11-23 <- 0xabc800");

    r1.set(0xdeadbeef);
    r1.write(write_value, 0x001ff000);
    EXPECT_EQ(r1.get(), 0xdeabceef);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before + 6);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
                      "Partial write to register r1: bits 12-20 <- 0xbc000");

    r1.write(write_value, 0xffffffffffffffff);
    EXPECT_EQ(r1.get(), write_value);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before + 7);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
                      "Write to register r1 <- 0x123456789abcdef");

    log_error_count_before = Stubs::instance_.sim_log_error_cnt_;
    r1.set(0xdeadbeef);

    // Malformed enable_bytes
    r1.write(write_value, 0x00202300);
    EXPECT_EQ(r1.get(), 0xdeadbeef);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
                      "enabled_bits(0x202300) is malformed: does not contain"
                      " consecutive ones");

    // Verify register with fields
    r1.set(0xdeadbeef);
    auto f2 = simics::ReadOnlyField(&map_obj, "b0.r1.f2");
    r1.parse_field({"f1", "", 0, 16});
    r1.parse_field({"f2", "", 16, 16});

    EXPECT_EQ(r1.read(0xffffffff), 0xdeadbeef);

    // Unmapped fields ignore write
    r1.write(0x123456789abcdef, 0xffffffffffffffff);
    EXPECT_EQ(r1.get(), 0xdeadcdef);
    EXPECT_EQ(r1.read(0xffffffffffffffff), 0xdeadcdef);

    // Read-only fields ignore write
    r1.write(0x11111111, 0xffff0000);
    EXPECT_EQ(r1.get(), 0xdeadcdef);
    EXPECT_EQ(r1.read(0xffffffffffffffff), 0xdeadcdef);

    // Test with a 2 byte register
    auto r2 = simics::Register(&map_obj, "b0.r2");
    reset_register_memory();
    r2.set_byte_pointers({pointers_[0], pointers_[1]});
    r2.init("A 2 byte register", 2, 0xffff);
    EXPECT_EQ(r2.number_of_bytes(), 2);
    EXPECT_EQ(r2.get(), 0xffff);

    // Verify read with different value of enabled_bits
    EXPECT_EQ(r2.read(0), 0);
    EXPECT_EQ(r2.read(0xffff0000), 0);
    EXPECT_EQ(r2.read(0x0000ffff), 0x0000ffff);
    EXPECT_EQ(r2.read(0x00ffff00), 0x0000ff00);

    // Verify write with different value of enabled_bits
    r2.write(write_value, 0);
    EXPECT_EQ(r2.get(), 0xffff);
    r2.write(write_value, 0xffff0000);
    EXPECT_EQ(r2.get(), 0xffff);
    r2.write(write_value, 0x0000ffff);
    EXPECT_EQ(r2.get(), 0xcdef);
    r2.set(0xffff);
    r2.write(write_value, 0x00ffff00);
    EXPECT_EQ(r2.get(), 0xcdff);
    r2.write(r2.read(0xffff), 0xffff);
    EXPECT_EQ(r2.get(), 0xcdff);

    // Add a field
    auto f1 = simics::Field(&map_obj, "b0.r2.f1");
    r2.parse_field({"f1", "", 3, 4});
    EXPECT_EQ(f1.get(), 0xf);

    // Test read
    EXPECT_EQ(r2.read(0xf), 0xf);
    f1.set(0);
    EXPECT_EQ(f1.read(0xf), 0);
    EXPECT_EQ(r2.read(0xf), 0x7);
    f1.set(1);
    EXPECT_EQ(f1.read(0xf), 1);
    EXPECT_EQ(r2.read(0xf), 0xf);

    EXPECT_EQ(r2.read(0xf0), 0x80);
    f1.set(0xa);
    EXPECT_EQ(f1.read(0xf), 0xa);
    EXPECT_EQ(f1.read(0xe), 0xa);
    EXPECT_EQ(r2.read(0xf0), 0xd0);

    // Test write
    EXPECT_EQ(f1.get(), 0xa);
    r2.write(0xf, 0xf);
    EXPECT_EQ(f1.get(), 0xb);
    r2.write(0x10, 0xf0);
    EXPECT_EQ(f1.get(), 0x3);

    // Test with a 8 byte register
    auto r3 = simics::Register(&map_obj, "b0.r3");
    reset_register_memory();
    r3.set_byte_pointers(pointers_);
    r3.init("A 8 byte register", 8, 0xffffffffffffffff);
    EXPECT_EQ(r3.number_of_bytes(), 8);
    EXPECT_EQ(r3.get(), 0xffffffffffffffff);

    // Test read
    for (size_t bit_enable : std::initializer_list<size_t>{0xf, 0xff, 0xfff,
                0xffff, 0xf'ffff, 0xff'ffff, 0xfff'ffff, 0xffff'ffff,
                0xf'ffff'ffff, 0xff'ffff'ffff, 0xfff'ffff'ffff,
                0xffff'ffff'ffff, 0xf'ffff'ffff'ffff,
                0xff'ffff'ffff'ffff, 0xfff'ffff'ffff'ffff,
                0xffff'ffff'ffff'ffff, 0xffff'0000}) {
        EXPECT_EQ(r3.read(bit_enable), bit_enable);
    }

    // Test write
    for (size_t bit_enable : std::initializer_list<size_t>{0xf, 0xff, 0xfff,
                0xffff, 0xf'ffff, 0xff'ffff, 0xfff'ffff, 0xffff'ffff,
                0xf'ffff'ffff, 0xff'ffff'ffff, 0xfff'ffff'ffff,
                0xffff'ffff'ffff, 0xf'ffff'ffff'ffff,
                0xff'ffff'ffff'ffff, 0xfff'ffff'ffff'ffff,
                0xffff'ffff'ffff'ffff, 0xffff'0000}) {
        r3.write(write_value, bit_enable);
        EXPECT_EQ(r3.get() & bit_enable, write_value & bit_enable);
    }

    r3.set(0xffff'ffff'ffff'ffff);
    // Adding a 64 bit field
    auto f3 = simics::Field(&map_obj, "b0.r3.f3");
    r3.parse_field({"f3", "", 0, 64});
    EXPECT_EQ(f3.get(), 0xffff'ffff'ffff'ffff);

    // Test read again with field
    for (size_t bit_enable : std::initializer_list<size_t>{0xf, 0xff, 0xfff,
                0xffff, 0xf'ffff, 0xff'ffff, 0xfff'ffff, 0xffff'ffff,
                0xf'ffff'ffff, 0xff'ffff'ffff, 0xfff'ffff'ffff,
                0xffff'ffff'ffff, 0xf'ffff'ffff'ffff,
                0xff'ffff'ffff'ffff, 0xfff'ffff'ffff'ffff,
                0xffff'ffff'ffff'ffff}) {
        EXPECT_EQ(r3.read(bit_enable), bit_enable);
    }

    // Test write again with field
    for (size_t bit_enable : std::initializer_list<size_t>{0xf, 0xff, 0xfff,
                0xffff, 0xf'ffff, 0xff'ffff, 0xfff'ffff, 0xffff'ffff,
                0xf'ffff'ffff, 0xff'ffff'ffff, 0xfff'ffff'ffff,
                0xffff'ffff'ffff, 0xf'ffff'ffff'ffff,
                0xff'ffff'ffff'ffff, 0xfff'ffff'ffff'ffff,
                0xffff'ffff'ffff'ffff, 0xffff'0000}) {
        r3.write(write_value, bit_enable);
        EXPECT_EQ(r3.get() & bit_enable, write_value & bit_enable);
    }
}

TEST_F(BankObjectFixture, TestRegisterStatusChangeNotify) {
    auto r1 = simics::Register(&map_obj, "b0.r1");
    r1.set_byte_pointers(pointers_);
    EXPECT_EQ(r1.get(), 0);

    auto notify_count_before = Stubs::instance_.sim_notify_cnt_;

    // Set with same value does not notify
    r1.set(r1.get());
    EXPECT_EQ(Stubs::instance_.sim_notify_cnt_, notify_count_before);

    // Set with different value does notify
    r1.set(r1.get() + 1);
    EXPECT_EQ(Stubs::instance_.sim_notify_cnt_,
                      notify_count_before + 1);

    notify_count_before = Stubs::instance_.sim_notify_cnt_;
    // Write with same value does not notify
    r1.write(r1.get(), ~0);
    EXPECT_EQ(Stubs::instance_.sim_notify_cnt_, notify_count_before);

    // Write with different value does notify
    r1.write(r1.get() - 1, ~0);
    EXPECT_EQ(Stubs::instance_.sim_notify_cnt_,
                      notify_count_before + 1);

    // Add a field
    auto f1 = simics::Field(&map_obj, "b0.r1.f1");
    r1.parse_field({"f1", "", 3, 4});
    EXPECT_EQ(f1.get(), 0);

    notify_count_before = Stubs::instance_.sim_notify_cnt_;
    // Set with same value does not notify
    f1.set(f1.get());
    EXPECT_EQ(Stubs::instance_.sim_notify_cnt_, notify_count_before);

    // Set with different value does notify
    f1.set(f1.get() + 1);
    EXPECT_EQ(Stubs::instance_.sim_notify_cnt_,
                      notify_count_before + 1);

    notify_count_before = Stubs::instance_.sim_notify_cnt_;
    // Write with same value does not notify
    f1.write(f1.get(), ~0);
    EXPECT_EQ(Stubs::instance_.sim_notify_cnt_, notify_count_before);

    // Write with different value does notify
    f1.write(f1.get() + 1, ~0);
    EXPECT_EQ(Stubs::instance_.sim_notify_cnt_,
                      notify_count_before + 1);

    notify_count_before = Stubs::instance_.sim_notify_cnt_;
    // Write outside field f1 does not notify
    r1.write(r1.get() + 1, ~0);
    EXPECT_EQ(Stubs::instance_.sim_notify_cnt_, notify_count_before);

    // Write inside field f1 does notify
    r1.write((f1.get() + 1) << 3, ~0);
    EXPECT_EQ(Stubs::instance_.sim_notify_cnt_,
                      notify_count_before + 1);
}

TEST_F(BankObjectFixture, TestRegisterFieldsInfo) {
    auto r1 = simics::Register(&map_obj, "b0.r1");
    r1.set_byte_pointers(pointers_);
    // Add a field
    const auto f1 = simics::Field(&map_obj, "b0.r1.f1");
    r1.parse_field({"f1", "field 1", 3, 4});

    const auto fields_info = r1.fields_info();
    EXPECT_EQ(fields_info.size(), 1);
    const auto first_field = fields_info[0];
    EXPECT_EQ(std::get<0>(first_field), "f1");
    EXPECT_EQ(std::get<1>(first_field), "field 1");
    EXPECT_EQ(std::get<2>(first_field), 3);
    EXPECT_EQ(std::get<3>(first_field), 4);
}

TEST_F(BankObjectFixture, TestRegisterParent) {
    auto log_error_count_before = Stubs::instance_.sim_log_error_cnt_;
    auto b_iface = reinterpret_cast<simics::BankInterface *>(0xa);
    map_obj.set_iface("b0", b_iface);
    simics::Register r {&map_obj, "b0.r1"};
    r.set_byte_pointers({pointers_[0]});

    EXPECT_EQ(r.parent(), b_iface);

    r.init("some description", 1, 0);
    EXPECT_EQ(r.parent(), b_iface);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
              log_error_count_before);

    // Check that the parent is moved correctly
    auto r2 {std::move(r)};
    EXPECT_EQ(r2.parent(), b_iface);
}

class TestField : public simics::Field {
  public:
    TestField(simics::MappableConfObject *dev_obj,
              const std::string &name,
              uint64_t get_return_value)
        : Field(dev_obj, name),
          get_return_value_(get_return_value) {}

    uint64_t get() const override {
        get_is_called = true;
        return get_return_value_;
    }

    void set(uint64_t value) override {
        set_is_called = true;
        set_value = value;
    }

    mutable bool get_is_called {false};
    bool set_is_called {false};
    uint64_t set_value {0};

  private:
    uint64_t get_return_value_ {0};
};

TEST_F(BankObjectFixture, TestRegisterCallsFieldGetSet) {
    {
        auto r1 = simics::Register(&map_obj, "b0.r1");
        r1.set_byte_pointers(pointers_);
        // Set all bits, test if field get() is honored in the test
        r1.set(0xffffffff);

        // f1.get() always return 0
        auto f1 = TestField(&map_obj, "b0.r1.f1", 0);
        auto f2 = TestField(&map_obj, "b0.r1.f2", 0xdeadbeef);
        r1.parse_field({"f1", "", 0, 4});
        r1.parse_field({"f2", "", 4, 28});

        EXPECT_EQ(f1.get_is_called, false);
        EXPECT_EQ(f2.get_is_called, false);
        EXPECT_EQ(r1.get(), 0xeadbeef0);
        EXPECT_EQ(f1.get_is_called, true);
        EXPECT_EQ(f2.get_is_called, true);

        EXPECT_EQ(f1.set_is_called, false);
        EXPECT_EQ(f1.set_value, 0);
        EXPECT_EQ(f2.set_is_called, false);
        EXPECT_EQ(f2.set_value, 0);
        r1.set(0xab);
        EXPECT_EQ(f1.set_is_called, true);
        EXPECT_EQ(f1.set_value, 0xb);
        EXPECT_EQ(f2.set_is_called, true);
        EXPECT_EQ(f2.set_value, 0xa);
    }
    {
        auto r1 = simics::Register(&map_obj, "b0.r1");
        reset_register_memory();
        r1.set_byte_pointers(pointers_);
        // Set all bits, test if field get() is honored in the test
        r1.set(0xffffffffffffffff);

        // f1 fills all the bits of r1
        auto f1 = TestField(&map_obj, "b0.r1.f1", 0xdeadbeefdeadbeef);
        r1.parse_field({"f1", "", 0, 64});

        EXPECT_EQ(f1.get_is_called, false);
        EXPECT_EQ(r1.get(), 0xdeadbeefdeadbeef);
        EXPECT_EQ(f1.get_is_called, true);

        EXPECT_EQ(f1.set_is_called, false);
        EXPECT_EQ(f1.set_value, 0);
        r1.set(0xab);
        EXPECT_EQ(f1.set_is_called, true);
        EXPECT_EQ(f1.set_value, 0xab);
    }
}

TEST_F(BankObjectFixture, TestOperatorStreamOutput) {
    simics::Register reg(&map_obj, "b0.r1");
    reg.set_byte_pointers(pointers_);
    reg.init("Test Register", 2, 0xabcd);

    // Use std::ostringstream to capture the output of operator<<
    std::ostringstream oss;
    oss << reg;
    EXPECT_EQ(oss.str(), "0x000000000000abcd");
}

TEST_F(BankObjectFixture, TestRegisterMoveSelfAssignment) {
    auto r1 = simics::Register(&map_obj, "b0.r9");
    r1.set_byte_pointers(pointers_);
    r1.init("desc-move", 1, 0x42);

    // Move self-assignment
    r1 = std::move(r1);

    // State should be unchanged
    EXPECT_EQ(r1.name(), "r9");
    EXPECT_EQ(r1.description(), "desc-move");
    EXPECT_EQ(r1.number_of_bytes(), 8);
    EXPECT_EQ(r1.get(), 0x42);
}

TEST_F(BankObjectFixture, TestRegisterReset) {
    simics::Register reg(&map_obj, "b0.r0");
    uint8_t storage = 0;
    simics::register_memory_t mem {&storage};
    reg.set_byte_pointers(mem);

    // Initialize with a value
    reg.init("desc", 1, 0x42);
    EXPECT_EQ(reg.get(), 0x42);

    // Change the value
    reg.set(0x77);
    EXPECT_EQ(reg.get(), 0x77);

    // Reset should restore the initial value
    reg.reset();
    EXPECT_EQ(reg.get(), 0x42);
}
