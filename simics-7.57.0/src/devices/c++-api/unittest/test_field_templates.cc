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

#include <simics/field-templates.h>

#include <gtest/gtest.h>

#include <string>
#include <vector>

#include "mock/stubs.h"
#include "mock/mock-register.h"
#include "unittest/bank-object-fixture.h"

class TestEnv : public BankObjectFixture {
  public:
    TestEnv() {}

    uint8_t bits {0};
    simics::bits_type slice {{&bits, 0x3c}};
    size_t log_error_count_before {Stubs::instance_.sim_log_error_cnt_};
    size_t log_spec_violation_count_before {
        Stubs::instance_.sim_log_spec_violation_cnt_
    };
    size_t log_unimplemented_count_before {
        Stubs::instance_.sim_log_unimplemented_cnt_
    };
    size_t log_info_count_before {Stubs::instance_.sim_log_info_cnt_};
    size_t all_ones {0xffffffffffffffff};
};

TEST_F(TestEnv, TestIgnoreWriteField) {
    simics::IgnoreWriteField f {&map_obj, "b0.r1.f2"};

    f.init("test field", slice, 2);
    EXPECT_EQ(f.get(), 0);

    // Writes are ignored
    f.write(0xf, all_ones);
    EXPECT_EQ(f.get(), 0);
    f.write(0x1, all_ones);
    EXPECT_EQ(f.get(), 0);

    // Set is OK
    f.set(0xf);
    EXPECT_EQ(f.get(), 0xf);

    // No log output
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before);
}

TEST_F(TestEnv, TestRead0Field) {
    simics::Read0Field f {&map_obj, "b0.r1.f2"};

    f.init("test field", slice, 2);
    EXPECT_EQ(f.get(), 0);

    // Writes are unaffected
    f.write(0xf, all_ones);
    EXPECT_EQ(f.get(), 0xf);

    // Reads return 0, regardless of the actual value
    EXPECT_EQ(f.read(all_ones), 0);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      ++log_info_count_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
                      "Read from read-zero field f2 -> 0x0.");

    // No log output
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before);
}

TEST_F(TestEnv, TestWriteOnlyField) {
    simics::WriteOnlyField f {&map_obj, "b0.r1.f2"};

    f.init("test field", slice, 2);
    EXPECT_EQ(f.get(), 0);

    // Writes are unaffected
    f.write(0xf, all_ones);
    EXPECT_EQ(f.get(), 0xf);

    // Reads return 0, regardless of the actual value
    EXPECT_EQ(f.read(all_ones), 0);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      ++log_info_count_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
                      "Read from write-only field f2 -> 0x0.");

    // No log output
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before);
}

TEST_F(TestEnv, TestReadOnlyField) {
    simics::ReadOnlyField f {&map_obj, "b0.r1.f2"};

    f.init("test field", slice, 2);
    EXPECT_EQ(f.get(), 0);

    // Write results in a spec_violation
    f.write(0xf, all_ones);
    EXPECT_EQ(f.get(), 0);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      ++log_spec_violation_count_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
                      "Write to read-only field f2 (value written"
                      " = 0x0000000f, contents = 0x00000000).");
    // Only log if the written value is different from the old value
    f.write(0, all_ones);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
              log_spec_violation_count_before);

    // Set is OK
    f.set(0xf);
    EXPECT_EQ(f.get(), 0xf);

    // No other log output
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before);
}

TEST_F(TestEnv, TestWrite1ClearsField) {
    simics::Write1ClearsField f {&map_obj, "b0.r1.f2"};

    f.init("test field", slice, 2);
    f.set(0xf);
    EXPECT_EQ(f.get(), 0xf);

    // SW can only clear bits
    f.write(0x1, all_ones);
    EXPECT_EQ(f.get(), 0xe);

    f.write(0xf, all_ones);
    EXPECT_EQ(f.get(), 0);

    // No log output
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before);
}

TEST_F(TestEnv, TestClearOnReadField) {
    simics::ClearOnReadField f {&map_obj, "b0.r1.f2"};

    f.init("test field", slice, 2);
    f.set(0xf);
    EXPECT_EQ(f.get(), 0xf);

    // SW reads return the object value. The object value
    // is then reset to 0 as a side-effect of the read
    EXPECT_EQ(f.read(0xffffffffffffff), 0xf);
    EXPECT_EQ(f.read(0xffffffffffffff), 0);
    EXPECT_EQ(f.get(), 0);

    // No log output
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before);
}

TEST_F(TestEnv, TestWrite1OnlyField) {
    simics::Write1OnlyField f {&map_obj, "b0.r1.f2"};

    f.init("test field", slice, 2);
    EXPECT_EQ(f.get(), 0);

    // SW can only set bits to 1
    f.write(0x1, 0xffffffffffffff);
    EXPECT_EQ(f.get(), 0x1);
    f.write(0, 0xffffffffffffff);
    EXPECT_EQ(f.get(), 0x1);
    f.write(0xf, 0xffffffffffffff);
    EXPECT_EQ(f.get(), 0xf);

    // No log output
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before);
}

TEST_F(TestEnv, TestWrite0OnlyField) {
    simics::Write0OnlyField f {&map_obj, "b0.r1.f2"};

    f.init("test field", slice, 2);
    EXPECT_EQ(f.get(), 0);

    // Set is OK
    f.set(0xf);
    EXPECT_EQ(f.get(), 0xf);

    // SW can only set bits to 0
    f.write(0x1, 0xffffffffffffff);
    EXPECT_EQ(f.get(), 0x1);
    f.write(0, 0xffffffffffffff);
    EXPECT_EQ(f.get(), 0);
    f.write(0xf, 0xffffffffffffff);
    EXPECT_EQ(f.get(), 0);

    // No log output
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before);
}

TEST_F(TestEnv, TestReadConstantField) {
    simics::ReadConstantField f {&map_obj, "b0.r1.f2", 0x5};

    f.init("test field", slice, 2);
    EXPECT_EQ(f.get(), 0);

    // Writes are unaffected
    f.write(0xf, all_ones);
    EXPECT_EQ(f.get(), 0xf);

    // Reads return a constant value
    EXPECT_EQ(f.read(all_ones), 0x5);
    f.set(0);
    EXPECT_EQ(f.get(), 0);
    EXPECT_EQ(f.read(all_ones), 0x5);

    // No log output
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before);
}

TEST_F(TestEnv, TestConstantField) {
    simics::ConstantField f {&map_obj, "b0.r1.f2", 0x5};

    f.init("test field", slice, 2);
    EXPECT_EQ(f.get(), 0x5);

    // Writes are forbidden and have no effect
    f.write(0xf, all_ones);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      ++log_spec_violation_count_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
                      "Write to constant field f2 (value written ="
                      " 0x0000000f, contents = 0x00000005).");
    EXPECT_EQ(f.get(), 0x5);
    // Only logs when field value is not equal to write value
    f.write(0x5, all_ones);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before);

    // Set is OK
    f.set(0xf);
    EXPECT_EQ(f.get(), 0xf);

    // No other log output
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before);
}

TEST_F(TestEnv, TestSilentConstantField) {
    simics::SilentConstantField f {&map_obj, "b0.r1.f2", 0x5};

    f.init("test field", slice, 2);
    EXPECT_EQ(f.get(), 0x5);

    // Writes are ignored and do not update the object value
    f.write(0xf, all_ones);
    EXPECT_EQ(f.get(), 0x5);

    // Set is OK
    f.set(0xf);
    EXPECT_EQ(f.get(), 0xf);

    // No log output
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before);
}

TEST_F(TestEnv, TestZerosField) {
    simics::ZerosField f {&map_obj, "b0.r1.f2"};

    f.init("test field", slice, 2);
    EXPECT_EQ(f.get(), 0);

    // Writes are forbidden and do not update the object value
    f.write(0xf, all_ones);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      ++log_spec_violation_count_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
                      "Write to constant field f2 (value written ="
                      " 0x0000000f, contents = 0x00000000).");
    EXPECT_EQ(f.get(), 0);
    // Only logs when field value is not equal to write value
    f.write(0, all_ones);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before);

    // Set is OK
    f.set(0xf);
    EXPECT_EQ(f.get(), 0xf);

    // No other log output
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before);
}

TEST_F(TestEnv, TestOnesField) {
    simics::OnesField f {&map_obj, "b0.r1.f2"};

    f.init("test field", slice, 2);
    EXPECT_EQ(f.get(), 0xf);

    // Writes do not update the object value
    f.write(0, all_ones);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      ++log_spec_violation_count_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
                      "Write to constant field f2 (value written ="
                      " 0x00000000, contents = 0x0000000f).");
    EXPECT_EQ(f.get(), 0xf);
    // Only logs when field value is not equal to write value
    f.write(0xf, all_ones);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before);

    // Set is OK
    f.set(0);
    EXPECT_EQ(f.get(), 0);
    EXPECT_EQ(f.read(all_ones), 0);

    // No other log output
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before);
}

TEST_F(TestEnv, TestIgnoreField) {
    simics::IgnoreField f {&map_obj, "b0.r1.f2"};

    f.init("test field", slice, 2);
    EXPECT_EQ(f.get(), 0);

    // Writes are ignored
    f.write(0xf, all_ones);
    EXPECT_EQ(f.get(), 0);

    // Set is OK
    f.set(0xf);
    EXPECT_EQ(f.get(), 0xf);

    // Reads return 0
    EXPECT_EQ(f.read(all_ones), 0);

    // No log output
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before);
}

TEST_F(TestEnv, TestReservedField) {
    simics::ReservedField f {&map_obj, "b0.r1.f2"};

    f.init("test field", slice, 2);
    EXPECT_EQ(f.get(), 0);

    // Writes update the object value
    f.write(0xf, all_ones);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      ++log_spec_violation_count_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
                      "Write to reserved field f2 (value written ="
                      " 0x0000000f, contents = 0x00000000), will"
                      " not warn again.");
    EXPECT_EQ(f.get(), 0xf);
    // Only logs when field value is not equal to write value
    f.write(0xf, all_ones);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before);
    // No logs on subsequence write
    f.write(0, all_ones);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before);

    // Reads return the object value
    EXPECT_EQ(f.read(all_ones), 0);

    // No other log output
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before);
}

TEST_F(TestEnv, TestReadUnimplField) {
    simics::ReadUnimplField f {&map_obj, "b0.r1.f2"};

    f.init("test field", slice, 2);
    EXPECT_EQ(f.get(), 0);

    // Writes are implemented as default
    f.write(0xf, all_ones);
    EXPECT_EQ(f.get(), 0xf);

    // Reads from a field does not result in a log-message
    EXPECT_EQ(f.read(all_ones), 0xf);

    // No log output
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before);
}

TEST_F(TestEnv, TestUnimplField) {
    simics::UnimplField f {&map_obj, "b0.r1.f2"};

    f.init("test field", slice, 2);
    EXPECT_EQ(f.get(), 0);

    // Writes are implemented as default
    f.write(0xf, all_ones);
    EXPECT_EQ(Stubs::instance_.sim_log_unimplemented_cnt_,
                      ++log_unimplemented_count_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_unimplemented_,
                      "Write to unimplemented field f2 (value written"
                      " = 0x0000000f, contents = 0x00000000).");
    EXPECT_EQ(f.get(), 0xf);
    // Only logs when field value is not equal to write value
    f.write(0xf, all_ones);
    EXPECT_EQ(Stubs::instance_.sim_log_unimplemented_cnt_,
                      log_unimplemented_count_before);

    // Reads from a field does not result in a log-message
    EXPECT_EQ(f.read(all_ones), 0xf);

    // No log output
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_unimplemented_cnt_,
                      log_unimplemented_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before);
}

TEST_F(TestEnv, TestWriteUnimplField) {
    simics::WriteUnimplField f {&map_obj, "b0.r1.f2"};

    f.init("test field", slice, 2);
    EXPECT_EQ(f.get(), 0);

    // Writes are implemented as default
    f.write(0xf, all_ones);
    EXPECT_EQ(Stubs::instance_.sim_log_unimplemented_cnt_,
                      ++log_unimplemented_count_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_unimplemented_,
                      "Write to unimplemented field f2 (value written"
                      " = 0x0000000f, contents = 0x00000000).");
    EXPECT_EQ(f.get(), 0xf);
    // Only logs when field value is not equal to write value
    f.write(0xf, all_ones);
    EXPECT_EQ(Stubs::instance_.sim_log_unimplemented_cnt_,
                      log_unimplemented_count_before);

    // Reads are implemented as default
    EXPECT_EQ(f.read(all_ones), 0xf);

    // No log output
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_unimplemented_cnt_,
                      log_unimplemented_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before);
}

TEST_F(TestEnv, TestSilentUnimplField) {
    simics::SilentUnimplField f {&map_obj, "b0.r1.f2"};

    f.init("test field", slice, 2);
    EXPECT_EQ(f.get(), 0);

    // Writes are implemented as default
    f.write(0xf, all_ones);
    EXPECT_EQ(Stubs::instance_.sim_log_unimplemented_cnt_,
                      ++log_unimplemented_count_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_unimplemented_,
                      "Write to unimplemented field f2 (value written"
                      " = 0x0000000f, contents = 0x00000000).");
    EXPECT_EQ(f.get(), 0xf);
    // Only logs when field value is not equal to write value
    f.write(0xf, all_ones);
    EXPECT_EQ(Stubs::instance_.sim_log_unimplemented_cnt_,
                      log_unimplemented_count_before);

    // Reads from a field does not result in a log-message
    EXPECT_EQ(f.read(all_ones), 0xf);

    // No log output
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_unimplemented_cnt_,
                      log_unimplemented_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before);
}

TEST_F(TestEnv, TestUndocumentedField) {
    simics::UndocumentedField f {&map_obj, "b0.r1.f2"};

    f.init("test field", slice, 2);
    EXPECT_EQ(f.get(), 0);

    // Writes are implemented as default
    f.write(0xf, all_ones);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      ++log_spec_violation_count_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
                      "Write to poorly or non-documented field"
                      " f2 (value written = 0x0000000f, contents"
                      " = 0x00000000).");
    EXPECT_EQ(f.get(), 0xf);

    // Reads from a field result in a spec-violation log-message
    EXPECT_EQ(f.read(all_ones), 0xf);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      ++log_spec_violation_count_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
                      "Read from poorly or non-documented field f2"
                      " (contents = 0x0000000f).");

    // No other log output
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before);
}

TEST_F(TestEnv, TestDesignLimitationField) {
    simics::DesignLimitationField f {&map_obj, "b0.r1.f2"};

    f.init("test field", slice, 2);
    EXPECT_EQ(f.get(), 0);

    // Writes are implemented as default
    f.write(0xf, all_ones);
    EXPECT_EQ(f.get(), 0xf);

    // Reads are implemented as default
    EXPECT_EQ(f.read(all_ones), 0xf);

    // No log output
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before);
}

class FieldWithManyArguments : public simics::Field {
  public:
    FieldWithManyArguments(simics::MappableConfObject *obj,
                           const std::string &name,
                           int a, char *b, const std::vector<uint8_t> &c)
        : Field(obj, name),
          a_(a), b_(b), c_(c) {}

    int a_;
    char *b_;
    std::vector<uint8_t> c_;
};

TEST_F(TestEnv, TestRegisterField) {
    {
        // Default template parameter
        auto r = MockRegister(&map_obj, "b0.r1");
        map_obj.set_iface<simics::RegisterInterface>("b0.r1", &r);
        simics::RegisterField<> f {&r, "f0",
            "some description for f0", 0, 4};

        EXPECT_EQ(f.name(), "f0");
        EXPECT_EQ(f.dev_obj(), &map_obj);
        EXPECT_EQ(f.parent(), &r);
        EXPECT_EQ(map_obj.get_iface<simics::FieldInterface>("b0.r1.f0"),
                  &f);
    }
    {
        // Test field array
        auto r = MockRegister(&map_obj, "b0.r1");
        map_obj.set_iface<simics::RegisterInterface>("b0.r1", &r);
        simics::RegisterField<> f0 {&r, "f[0]",
            "some description for f0", 0, 4};
        simics::RegisterField<> f1 {&r, "f[1]",
            "some description for f1", 4, 8};

        EXPECT_EQ(f0.name(), "f[0]");
        EXPECT_EQ(f1.name(), "f[1]");
        EXPECT_EQ(f0.dev_obj(), &map_obj);
        EXPECT_EQ(f1.dev_obj(), &map_obj);
        EXPECT_EQ(f0.parent(), &r);
        EXPECT_EQ(f1.parent(), &r);
        EXPECT_EQ(map_obj.get_iface<simics::FieldInterface>("b0.r1.f[0]"),
                  &f0);
        EXPECT_EQ(map_obj.get_iface<simics::FieldInterface>("b0.r1.f[1]"),
                  &f1);
    }
    {
        // Test extra template arguments
        auto r = MockRegister(&map_obj, "b0.r1");
        map_obj.set_iface<simics::RegisterInterface>("b0.r1", &r);
        char *c = reinterpret_cast<char *>(uintptr_t{0xdeadbeef});
        std::vector<uint8_t> v {0xa, 0xb};
        simics::RegisterField<FieldWithManyArguments, int, char *,
                              const std::vector<uint8_t> &> f {
                                static_cast<simics::RegisterInterface *>(&r),
                                "f1", "some description for f0",
                                0, 4, 0xab, c, v
                            };

        EXPECT_EQ(f.name(), "f1");
        EXPECT_EQ(f.dev_obj(), &map_obj);
        EXPECT_EQ(f.parent(), &r);
        EXPECT_EQ(map_obj.get_iface<simics::FieldInterface>("b0.r1.f1"),
                  &f);
        EXPECT_EQ(f.a_, 0xab);
        EXPECT_EQ(f.b_, c);
        EXPECT_EQ(f.c_, v);
    }
}

TEST_F(TestEnv, TestWriteOnceField) {
    simics::WriteOnceField f {&map_obj, "b0.r1.f2"};

    f.init("test field", slice, 2);
    EXPECT_EQ(f.get(), 0);

    // First write is OK
    f.write(0x1, 0x1);

    // The second write results in a spec_violation
    f.write(0x3, 0x3);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
              ++log_spec_violation_count_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
              "Write to write-once field f2"
              " (value written = 0x00000003, contents = 0x00000001)");
    EXPECT_EQ(f.get(), 0x1);

    // No other log output
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before);
}

TEST_F(TestEnv, TestReadOnlyClearOnReadField) {
    simics::ReadOnlyClearOnReadField f {&map_obj, "b0.r1.f2"};

    f.init("test field", slice, 2);
    EXPECT_EQ(f.get(), 0);

    // Write results in a spec_violation
    f.write(0xf, all_ones);
    EXPECT_EQ(f.get(), 0);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      ++log_spec_violation_count_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
                      "Write to read-only field f2 (value written"
                      " = 0x0000000f, contents = 0x00000000).");
    // Only log if the written value is different from the old value
    f.write(0, all_ones);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
              log_spec_violation_count_before);

    // Set is OK
    f.set(0xf);
    EXPECT_EQ(f.get(), 0xf);

    // SW reads return the object value. The object value
    // is then reset to 0 as a side-effect of the read
    EXPECT_EQ(f.read(0xffffffffffffff), 0xf);
    EXPECT_EQ(f.read(0xffffffffffffff), 0);
    EXPECT_EQ(f.get(), 0);

    // No other log output
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_count_before);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
                      log_info_count_before);
}
