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

#include <simics/register-templates.h>

#include <gtest/gtest.h>

#include <string>
#include <vector>

#include "mock/stubs.h"
#include "mock/mock-bank.h"
#include "unittest/bank-object-fixture.h"

TEST_F(BankObjectFixture, TestRegisterTemplate) {
    auto ignore_write_r = simics::IgnoreWriteRegister(&map_obj,
                                                      "b0.ignore_write_r");
    EXPECT_EQ(ignore_write_r.get(), 0);
    auto log_info_count_before = Stubs::instance_.sim_log_info_cnt_;
    ignore_write_r.write(0x1, 0x1);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before);
    EXPECT_EQ(ignore_write_r.get(), 0);

    auto read_0_r = simics::Read0Register(&map_obj, "b0.read_0_r");
    reset_register_memory();
    read_0_r.set_byte_pointers(pointers_);
    EXPECT_EQ(read_0_r.read(0), 0);

    auto read_only_r = simics::ReadOnlyRegister(&map_obj, "b0.read_only_r");
    reset_register_memory();
    read_only_r.set_byte_pointers({pointers_[0], pointers_[1],
            pointers_[2], pointers_[3]});
    EXPECT_EQ(read_only_r.is_read_only(), true);
    log_info_count_before = Stubs::instance_.sim_log_info_cnt_;
    auto log_spec_violation_count_before
        = Stubs::instance_.sim_log_spec_violation_cnt_;
    read_only_r.write(0x1, 0x1);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, log_info_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
              log_spec_violation_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
                      "Write to read-only register read_only_r (value written"
                      " = 0x00000001, contents = 0x00000000)");
    EXPECT_EQ(read_only_r.get(), 0);

    auto write_only_r = simics::WriteOnlyRegister(&map_obj, "b0.write_only_r");
    reset_register_memory();
    write_only_r.set_byte_pointers(pointers_);
    log_spec_violation_count_before
        = Stubs::instance_.sim_log_spec_violation_cnt_;
    write_only_r.read(0x1);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
                      "Read from write-only register write_only_r (returning"
                      " 0)");
    EXPECT_EQ(write_only_r.get(), 0);

    auto write_clear_r = simics::Write1ClearsRegister(&map_obj,
                                                      "b0.write_clear_r");
    reset_register_memory();
    write_clear_r.set_byte_pointers(pointers_);
    write_clear_r.set(0b00011011);
    EXPECT_EQ(write_clear_r.get(), 0b00011011);
    write_clear_r.write(0b1111, 0b1111);
    EXPECT_EQ(write_clear_r.get(), 0b00010000);

    auto clear_on_read_r = simics::ClearOnReadRegister(&map_obj,
                                                       "b0.clear_on_read_r");
    reset_register_memory();
    clear_on_read_r.set_byte_pointers(pointers_);
    clear_on_read_r.set(1);
    EXPECT_EQ(clear_on_read_r.get(), 1);
    EXPECT_EQ(clear_on_read_r.read(0x1), 1);
    EXPECT_EQ(clear_on_read_r.get(), 0);

    auto write_1_only_r = simics::Write1OnlyRegister(&map_obj,
                                                     "b0.write_1_only_r");
    reset_register_memory();
    write_1_only_r.set_byte_pointers(pointers_);
    write_1_only_r.set(0b00011011);
    write_1_only_r.write(0b1111, 0b1111);
    EXPECT_EQ(write_1_only_r.get(), 0b00011111);

    auto write_0_only_r = simics::Write0OnlyRegister(&map_obj,
                                                     "b0.write_0_only_r");
    reset_register_memory();
    write_0_only_r.set_byte_pointers(pointers_);
    write_0_only_r.set(0b00011011);
    write_0_only_r.write(0b1111, 0b11111111);
    EXPECT_EQ(write_0_only_r.get(), 0b00001011);

    auto read_constant_r = simics::ReadConstantRegister(&map_obj,
                                                        "b0.read_constant_r",
                                                        0xa);
    reset_register_memory();
    read_constant_r.set_byte_pointers(pointers_);
    read_constant_r.set(0xb);
    EXPECT_EQ(read_constant_r.read(0b1111), 0xa);
    read_constant_r.write(0xb, 0b1111);
    EXPECT_EQ(read_constant_r.read(0b1111), 0xa);

    auto constant_r = simics::ConstantRegister(&map_obj, "b0.constant_r");
    reset_register_memory();
    constant_r.set_byte_pointers({pointers_[0], pointers_[1],
            pointers_[2], pointers_[3]});
    constant_r.set(0xc);
    log_spec_violation_count_before
        = Stubs::instance_.sim_log_spec_violation_cnt_;
    constant_r.write(1, 1);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
                      "Write to constant register constant_r (value written"
                      " = 0x00000001, contents = 0x0000000c)");
    EXPECT_EQ(constant_r.get(), 0xc);

    auto silent_constant_r = simics::SilentConstantRegister(
        &map_obj, "b0.silent_constant_r");
    reset_register_memory();
    silent_constant_r.set_byte_pointers(pointers_);
    EXPECT_EQ(silent_constant_r.get(), 0);
    log_info_count_before = Stubs::instance_.sim_log_info_cnt_;
    silent_constant_r.write(0x1, 0x1);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before);
    EXPECT_EQ(silent_constant_r.get(), 0);

    auto zeros_r = simics::ZerosRegister(&map_obj, "b0.zeros_r");
    reset_register_memory();
    zeros_r.set_byte_pointers({pointers_[0]});
    log_spec_violation_count_before
        = Stubs::instance_.sim_log_spec_violation_cnt_;
    auto log_error_count_before
        = Stubs::instance_.sim_log_error_cnt_;
    zeros_r.write(1, 1);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
                      "Write to constant register zeros_r (value written"
                      " = 0x00000001, contents = 0x00000000)");
    log_spec_violation_count_before
        = Stubs::instance_.sim_log_spec_violation_cnt_;
    zeros_r.init("", 1, 1);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
                      "Invalid non-zeros init_val for ZerosRegister");
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, log_error_count_before);

    auto ones_r = simics::OnesRegister(&map_obj, "b0.ones_r");
    reset_register_memory();
    ones_r.set_byte_pointers(pointers_);
    ones_r.init("", 8, 0xffffffffffffffff);
    log_spec_violation_count_before = \
        Stubs::instance_.sim_log_spec_violation_cnt_;
    log_error_count_before
        = Stubs::instance_.sim_log_error_cnt_;
    ones_r.write(1, 1);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
                      "Write to constant register ones_r (value written"
                      " = 0x00000001, contents = 0xffffffffffffffff)");
    log_spec_violation_count_before = \
        Stubs::instance_.sim_log_spec_violation_cnt_;
    ones_r.init("", 8, 1);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
                      "Invalid non-ones init_val for OnesRegister");
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, log_error_count_before);

    auto ignore_r = simics::IgnoreRegister(&map_obj, "b0.ignore_r");
    reset_register_memory();
    ignore_r.set_byte_pointers(pointers_);
    EXPECT_EQ(ignore_r.get(), 0);
    log_info_count_before = Stubs::instance_.sim_log_info_cnt_;
    ignore_r.write(0x1, 0x1);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before);
    EXPECT_EQ(ignore_r.get(), 0);
    EXPECT_EQ(ignore_r.read(1), 0);

    auto reserved_r = simics::ReservedRegister(&map_obj, "b0.reserved_r");
    reset_register_memory();
    reserved_r.set_byte_pointers({pointers_[0], pointers_[1],
            pointers_[2], pointers_[3]});
    log_spec_violation_count_before = \
        Stubs::instance_.sim_log_spec_violation_cnt_;
    reserved_r.write(1, 1);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
                      "Write to reserved register reserved_r (value written"
                      " = 0x00000001, contents = 0x00000000), will not warn"
                      " again.");
    log_spec_violation_count_before = \
        Stubs::instance_.sim_log_spec_violation_cnt_;
    reserved_r.write(1, 1);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before);

    auto read_unimpl_r = simics::ReadUnimplRegister(&map_obj,
                                                    "b0.read_unimpl_r");
    reset_register_memory();
    read_unimpl_r.set_byte_pointers(pointers_);
    EXPECT_EQ(read_unimpl_r.description(),
                      "Read access not implemented. ");
    auto log_unimplemented_count_before = \
        Stubs::instance_.sim_log_unimplemented_cnt_;
    EXPECT_EQ(read_unimpl_r.read(1), 0);
    EXPECT_EQ(Stubs::instance_.sim_log_unimplemented_cnt_,
                      log_unimplemented_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_unimplemented_,
                      "Read from unimplemented register read_unimpl_r (contents"
                      " = 0x00000000).");

    auto unimpl_r = simics::UnimplRegister(&map_obj, "b0.unimpl_r");
    reset_register_memory();
    unimpl_r.set_byte_pointers({pointers_[0], pointers_[1],
            pointers_[2], pointers_[3]});
    EXPECT_EQ(unimpl_r.description(), "Not implemented. ");
    log_unimplemented_count_before = \
        Stubs::instance_.sim_log_unimplemented_cnt_;
    unimpl_r.write(1, 1);
    EXPECT_EQ(Stubs::instance_.sim_log_unimplemented_cnt_,
                      log_unimplemented_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_unimplemented_,
                      "Write to unimplemented register unimpl_r (value written"
                      " = 0x00000001, contents = 0x00000000).");
    log_unimplemented_count_before = \
        Stubs::instance_.sim_log_unimplemented_cnt_;
    EXPECT_EQ(unimpl_r.read(1), 1);
    EXPECT_EQ(Stubs::instance_.sim_log_unimplemented_cnt_,
                      log_unimplemented_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_unimplemented_,
                      "Read from unimplemented register unimpl_r (contents"
                      " = 0x00000001).");

    auto write_unimpl_r = simics::WriteUnimplRegister(&map_obj,
                                                      "b0.write_unimpl_r");
    reset_register_memory();
    write_unimpl_r.set_byte_pointers({pointers_[0], pointers_[1],
            pointers_[2], pointers_[3]});
    EXPECT_EQ(write_unimpl_r.description(),
                      "Write access not implemented. ");
    log_unimplemented_count_before = \
        Stubs::instance_.sim_log_unimplemented_cnt_;
    write_unimpl_r.write(1, 1);
    EXPECT_EQ(Stubs::instance_.sim_log_unimplemented_cnt_,
                      log_unimplemented_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_unimplemented_,
                      "Write to unimplemented register write_unimpl_r (value"
                      " written = 0x00000001, contents = 0x00000000).");

    auto silent_unimpl_r = simics::UnimplRegister(&map_obj,
                                                  "b0.silent_unimpl_r");
    reset_register_memory();
    silent_unimpl_r.set_byte_pointers({pointers_[0], pointers_[1],
            pointers_[2], pointers_[3]});
    log_unimplemented_count_before = \
        Stubs::instance_.sim_log_unimplemented_cnt_;
    silent_unimpl_r.write(1, 1);
    EXPECT_EQ(Stubs::instance_.sim_log_unimplemented_cnt_,
                      log_unimplemented_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_unimplemented_,
                      "Write to unimplemented register silent_unimpl_r (value"
                      " written = 0x00000001, contents = 0x00000000).");
    log_unimplemented_count_before = \
        Stubs::instance_.sim_log_unimplemented_cnt_;
    EXPECT_EQ(silent_unimpl_r.read(1), 1);
    EXPECT_EQ(Stubs::instance_.sim_log_unimplemented_cnt_,
                      log_unimplemented_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_unimplemented_,
                      "Read from unimplemented register silent_unimpl_r"
                      " (contents = 0x00000001).");

    auto undocumented_r = simics::UndocumentedRegister(&map_obj,
                                                       "b0.undocumented_r");
    reset_register_memory();
    undocumented_r.set_byte_pointers({pointers_[0], pointers_[1],
            pointers_[2], pointers_[3]});
    log_spec_violation_count_before = \
        Stubs::instance_.sim_log_spec_violation_cnt_;
    undocumented_r.write(1, 1);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
                      "Write to poorly or non-documented register"
                      " undocumented_r (value written = 0x00000001, contents"
                      " = 0x00000000).");
    log_spec_violation_count_before = \
        Stubs::instance_.sim_log_spec_violation_cnt_;
    EXPECT_EQ(undocumented_r.read(1), 1);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
                      "Read from poorly or non-documented register"
                      " undocumented_r (contents = 0x00000001).");

    auto design_limitation_r = simics::DesignLimitationRegister(
        &map_obj, "b0.design_limitation_r");
    EXPECT_EQ(design_limitation_r.description(),
                      "Not implemented (design limitation). This register"
                      " is a dummy register with no side effects. ");

    auto unmapped_r = simics::UnmappedRegister(&map_obj,
                                               "b0.unmapped_r", 2, 1);
    EXPECT_EQ(unmapped_r.number_of_bytes(), 2);
    EXPECT_EQ(unmapped_r.is_mapped(), false);
    EXPECT_EQ(unmapped_r.description(), "Unmapped. ");

    auto alias_r = simics::AliasRegister(&map_obj, "b0.alias_r",
                                         "b0.read_only_r");
    reset_register_memory();
    alias_r.set_byte_pointers({pointers_[0], pointers_[1],
            pointers_[2], pointers_[3]});
    EXPECT_EQ(alias_r.is_read_only(), true);

    log_spec_violation_count_before = \
        Stubs::instance_.sim_log_spec_violation_cnt_;
    alias_r.write(0x1, 0x1);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
                      "Write to read-only register read_only_r (value written "
                      "= 0x00000001, contents = 0x00000000)");

    auto write_once_r = simics::WriteOnceRegister(&map_obj,
                                                  "b0.write_once_r");
    reset_register_memory();
    write_once_r.set_byte_pointers({pointers_[0], pointers_[1],
            pointers_[2], pointers_[3]});
    log_info_count_before = Stubs::instance_.sim_log_info_cnt_;
    log_spec_violation_count_before
        = Stubs::instance_.sim_log_spec_violation_cnt_;
    write_once_r.write(0x1, 0x1);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, log_info_count_before + 1);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
              log_spec_violation_count_before);
    write_once_r.write(0x3, 0x3);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, log_info_count_before + 1);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
              log_spec_violation_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
              "Write to write-once register write_once_r"
              " (value written = 0x00000003, contents = 0x00000001)");
    EXPECT_EQ(write_once_r.get(), 0x1);

    auto readonly_clearonread_r = simics::ReadOnlyClearOnReadRegister(
            &map_obj, "b0.readonly_clearonread_r");
    reset_register_memory();
    readonly_clearonread_r.set_byte_pointers({pointers_[0], pointers_[1],
            pointers_[2], pointers_[3]});
    EXPECT_EQ(readonly_clearonread_r.is_read_only(), true);
    log_info_count_before = Stubs::instance_.sim_log_info_cnt_;
    log_spec_violation_count_before
        = Stubs::instance_.sim_log_spec_violation_cnt_;
    readonly_clearonread_r.write(0x1, 0x1);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, log_info_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
              log_spec_violation_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
              "Write to read-only register readonly_clearonread_r"
              " (value written = 0x00000001, contents = 0x00000000)");
    EXPECT_EQ(readonly_clearonread_r.get(), 0);

    readonly_clearonread_r.set(1);
    EXPECT_EQ(readonly_clearonread_r.get(), 1);
    EXPECT_EQ(readonly_clearonread_r.read(0x1), 1);
    EXPECT_EQ(readonly_clearonread_r.get(), 0);
}

class RegisterWithManyArguments : public simics::Register {
  public:
    RegisterWithManyArguments(simics::MappableConfObject *dev_obj,
                              const std::string &hierarchical_name,
                              int a, char *b, const std::vector<uint8_t> &c)
        : Register::Register(dev_obj, hierarchical_name),
          a_(a), b_(b), c_(c) {}

    int a_;
    char *b_;
    std::vector<uint8_t> c_;
};

TEST_F(BankObjectFixture, TestBankRegister) {
    {
        // Default template parameter
        auto b = MockBank();
        b.name_ = "test_bank";
        b.dev_obj_ = &map_obj;
        map_obj.set_iface<simics::BankInterface>("test_bank", &b);
        auto r = simics::BankRegister<>(&b, "r0", "some description", 0, 4,
                                        0xdeadbeef);
        EXPECT_EQ(r.name(), "r0");
        EXPECT_EQ(r.dev_obj(), &map_obj);
        EXPECT_EQ(r.parent(), &b);
        EXPECT_EQ(map_obj.get_iface<simics::RegisterInterface>("test_bank.r0"),
                  &r);
        EXPECT_EQ(b.number_of_registers(), 1);
    }
    {
        // Test extra template arguments
        auto b = MockBank();
        b.name_ = "test_bank";
        b.dev_obj_ = &map_obj;
        map_obj.set_iface<simics::BankInterface>("test_bank", &b);
        char *c = reinterpret_cast<char *>(uintptr_t{0xdeadbeef});
        std::vector<uint8_t> v {0xa, 0xb};
        auto r = simics::BankRegister<RegisterWithManyArguments, int, char *,
                                      const std::vector<uint8_t> &>(
                                      static_cast<simics::BankInterface *>(&b),
                                      "r1", "some description", 0, 4,
                                      0xdeadbeef, {}, 0xab, c, v);
        EXPECT_EQ(r.name(), "r1");
        EXPECT_EQ(r.dev_obj(), &map_obj);
        EXPECT_EQ(r.parent(), &b);
        EXPECT_EQ(map_obj.get_iface<simics::RegisterInterface>("test_bank.r1"),
                  &r);
        EXPECT_EQ(r.a_, 0xab);
        EXPECT_EQ(r.b_, c);
        EXPECT_EQ(r.c_, v);
    }
}

TEST_F(BankObjectFixture, TestExtendRegisterWithOffset) {
    {
        // Default template parameter
        auto b = MockBank();
        b.name_ = "test_bank";
        b.dev_obj_ = &map_obj;
        map_obj.set_iface<simics::BankInterface>("test_bank", &b);
        auto r = simics::BankRegister<
            simics::ExtendRegisterWithOffset<simics::Register>>(
                    &b, "r0", "some description", 0x100, 4, 0xdeadbeef);
        EXPECT_EQ(r.name(), "r0");
        EXPECT_EQ(r.dev_obj(), &map_obj);
        EXPECT_EQ(r.parent(), &b);
        EXPECT_EQ(b.mapped_registers().size(), 1);
        EXPECT_EQ(r.offset(), 0x100);
        EXPECT_EQ(map_obj.get_iface<simics::RegisterInterface>("test_bank.r0"),
                  &r);
        EXPECT_EQ(b.number_of_registers(), 1);
    }
}
