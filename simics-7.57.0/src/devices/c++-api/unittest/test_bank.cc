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

#include <simics/bank.h>

#include <gtest/gtest.h>
#include <simics/base/transaction.h>

#include <string>
#include <utility>
#include <vector>

#include "mock/gtest_extensions.h"  // EXPECT_PRED_THROW
#include "mock/mock-register.h"
#include "mock/stubs.h"
#include "unittest/bank-object-fixture.h"

bool checkEmptyName(const std::exception &ex) {
    EXPECT_STREQ(ex.what(),
                 "Cannot set with invalid name string: ");
    return true;
}

bool checkInvalidName(const std::exception &ex) {
    EXPECT_STREQ(ex.what(),
                 "Bank name (b1.r0) does not match the bank level (bankA)");
    return true;
}

TEST_F(BankObjectFixture, TestBankCreation) {
    // Empty name is not allowed
    EXPECT_PRED_THROW(simics::Bank(&map_obj, ""),
                      std::invalid_argument, checkEmptyName);

    // The name has incorrect hierarchy level
    EXPECT_PRED_THROW(simics::Bank(&map_obj, "b1.r0"),
                      std::invalid_argument, checkInvalidName);

    // The indices are allowed in the name
    auto b = simics::Bank(&map_obj, "b[0]");
    EXPECT_EQ(b.bank_name(), "b[0]");
}

TEST_F(BankObjectFixture, TestBankCTOR) {
    EXPECT_FALSE(std::is_copy_constructible<simics::Bank>::value);
    EXPECT_TRUE(std::is_move_constructible<simics::Bank>::value);

    auto b1 = simics::Bank(&map_obj, "b");
    EXPECT_EQ(b1.bank_name(), "b");
    auto *iface = map_obj.get_iface<simics::BankInterface>("b");
    EXPECT_EQ(iface, &b1);

    auto b2 {std::move(b1)};
    EXPECT_EQ(b2.bank_name(), "b");
    iface = map_obj.get_iface<simics::BankInterface>("b");
    EXPECT_EQ(iface, &b2);

    b1 = std::move(b2);
    EXPECT_EQ(b1.bank_name(), "b");
    iface = map_obj.get_iface<simics::BankInterface>("b");
    EXPECT_EQ(iface, &b1);
}

TEST_F(BankObjectFixture, TestBankMoveSelfAssignment) {
    simics::Bank b1(&map_obj, "b0");
    // Add a register to b1 to give it some state
    auto r = std::make_tuple("r1", std::string("desc"),
                             0, 4, 0, std::vector<simics::field_t>());
    b1.add_register(r);
    unsigned num_regs_before = b1.number_of_registers();

    // Move self-assignment
    b1 = std::move(b1);

    // Check that state is unchanged after move self-assignment
    EXPECT_EQ(b1.name(), "b0");
    EXPECT_EQ(b1.number_of_registers(), num_regs_before);
}

TEST_F(BankObjectFixture, TestAddRegisterSingleArg) {
    auto b = simics::Bank(&map_obj, "b0");
    auto log_error_cnt_before = Stubs::instance_.sim_log_error_cnt_;

    // Invalid number of bytes (16)
    log_error_cnt_before = Stubs::instance_.sim_log_error_cnt_;
    auto r = std::make_tuple("r1", std::string(""), 0,
                        16, 0, std::vector<simics::field_t>());
    b.add_register(r);
    EXPECT_EQ(b.number_of_registers(), 0);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_cnt_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
                      "Cannot add a register with unsupported size (16)");

    // Invalid number of bytes (0)
    log_error_cnt_before = Stubs::instance_.sim_log_error_cnt_;
    r = std::make_tuple("r1", std::string(""), 0,
                        0, 0, std::vector<simics::field_t>());
    b.add_register(r);
    EXPECT_EQ(b.number_of_registers(), 0);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_cnt_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
                      "Cannot add a register with unsupported size (0)");

    // Valid name and size
    log_error_cnt_before = Stubs::instance_.sim_log_error_cnt_;
    auto log_info_cnt_before = Stubs::instance_.sim_log_info_cnt_;
    r = std::make_tuple("r1", std::string(""), 0,
                        4, 0, std::vector<simics::field_t>());
    b.add_register(r);
    EXPECT_EQ(b.number_of_registers(), 1);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_cnt_before);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
              log_info_cnt_before + 2);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
                      "Created default register b0.r1");

    // Overlapped offset
    log_error_cnt_before = Stubs::instance_.sim_log_error_cnt_;
    auto r2 = std::make_tuple("r2", std::string(""), 2,
                              4, 0, std::vector<simics::field_t>());
    b.add_register(r2);
    EXPECT_EQ(b.number_of_registers(), 1);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_cnt_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
                      "Cannot add register(r2): offset"
                      " overlapped with existing registers on the bank");

    // Another valid name and size register
    log_error_cnt_before = Stubs::instance_.sim_log_error_cnt_;
    log_info_cnt_before = Stubs::instance_.sim_log_info_cnt_;
    r2 = std::make_tuple("r2", std::string(""), 4,
                         1, 0, std::vector<simics::field_t>());
    b.add_register(r2);
    EXPECT_EQ(b.number_of_registers(), 2);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_cnt_before);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
              log_info_cnt_before + 2);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
                      "Created default register b0.r2");

    // Device finalized
    log_error_cnt_before = Stubs::instance_.sim_log_error_cnt_;
    set_configured();
    auto r3 = std::make_tuple("r3", std::string(""), 5,
                              1, 0, std::vector<simics::field_t>());
    b.add_register(r3);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      ++log_error_cnt_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
                      "Cannot add registers for bank (b0) when device has"
                      " finalized");
}

TEST_F(BankObjectFixture, TestAddRegisterMultiArgs) {
    auto b = simics::Bank(&map_obj, "b0");
    auto log_error_cnt_before = Stubs::instance_.sim_log_error_cnt_;

    b.add_register("", "", 0, 0, 0, std::vector<simics::field_t>());
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, ++log_error_cnt_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
                      "Cannot add a register with empty name");

    b.add_register("r1", "", 0, 0, 0, std::vector<simics::field_t>());
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, ++log_error_cnt_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
                      "Cannot add a register with unsupported size (0)");

    b.add_register("r1", "", 0, 12, 0, std::vector<simics::field_t>());
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, ++log_error_cnt_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
                      "Cannot add a register with unsupported size (12)");

    // Add a register
    auto r = MockRegister(&map_obj, "b0.r1");
    // Just to increase test coverage
    r.is_mapped_ = false;
    map_obj.set_iface<simics::RegisterInterface>("b0.r1", &r);

    auto log_info_cnt_before = Stubs::instance_.sim_log_info_cnt_;
    // Now add the same register again
    b.add_register("r1", "", 0, 4, 0, std::vector<simics::field_t>());
    EXPECT_EQ(b.number_of_registers(), 1);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, log_info_cnt_before + 2);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
              "Used user defined register b0.r1");

    // Add a register with fields
    auto f1 = simics::field_t("f1", "f1", 0, 4);
    b.add_register("r2", "", 4, 4, 0, {f1});
    EXPECT_EQ(b.number_of_registers(), 2);

    log_error_cnt_before = Stubs::instance_.sim_log_error_cnt_;
    // Add register with same name
    b.add_register("r2", "", 8, 4, 0, {f1});
    EXPECT_EQ(b.number_of_registers(), 2);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, ++log_error_cnt_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Cannot add register(r2): name duplicated"
              " with existing registers on the bank");
}

TEST_F(BankObjectFixture, TestRegisterAtIndex) {
    auto b = simics::Bank(&map_obj, "b");
    auto log_error_cnt_before = Stubs::instance_.sim_log_error_cnt_;

    b.register_at_index(0);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_cnt_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
                      "Invalid register with id 0");

    auto r = std::make_tuple("r", std::string(""), 4,
                             1, 0, std::vector<simics::field_t>());
    b.add_register(r);

    log_error_cnt_before = Stubs::instance_.sim_log_error_cnt_;
    auto result = b.register_at_index(0);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                      log_error_cnt_before);
    EXPECT_EQ(result.first, std::get<2>(r));
}

TEST_F(BankObjectFixture, TestAllMappedRegisters) {
    auto b = simics::Bank(&map_obj, "b");
    auto regs = b.mapped_registers();
    EXPECT_EQ(regs.empty(), true);

    auto r1 = std::make_tuple("r1", std::string(""), 4,
                              1, 0, std::vector<simics::field_t>());
    b.add_register(r1);

    regs = b.mapped_registers();
    EXPECT_EQ(regs.size(), 1);
    auto first_reg = regs.begin();
    EXPECT_EQ(first_reg->first, 4);
    EXPECT_EQ(first_reg->second->name(), "r1");

    auto r2 = std::make_tuple("r2", std::string(""), 0,
                              1, 0, std::vector<simics::field_t>());
    b.add_register(r2);

    // Test the returned registers are ordered by offset
    regs = b.mapped_registers();
    EXPECT_EQ(regs.size(), 2);
    first_reg = regs.begin();
    EXPECT_EQ(first_reg->first, 0);
    EXPECT_EQ(first_reg->second->name(), "r2");
}

class TestBankTransactionAccess : public simics::Bank {
  public:
    using Bank::Bank;

    std::vector<uint8_t> read(uint64_t offset, size_t size,
                              simics::Inquiry inquiry) const override {
        if (inquiry == simics::Inquiry::Inquiry) {
            ++get_count_;
        } else {
            ++read_count_;
        }
        offset_ = offset;
        size_ = size;
        return {};
    }

    void write(uint64_t offset, const std::vector<uint8_t> &value,
               size_t size, simics::Inquiry inquiry) const override {
        if (inquiry == simics::Inquiry::Inquiry) {
            ++set_count_;
        } else {
            ++write_count_;
        }
        offset_ = offset;
        if (value.size() > 8) {
            throw std::invalid_argument(
                "Value size exceeds the bit-width of uint64_t (8 bytes).");
        }
        for (size_t idx = 0; idx < value.size(); ++idx) {
            value_ |= value[idx] << (idx * 8);
        }
        size_ = size;
    }

    mutable int read_count_ {0};
    mutable int get_count_ {0};
    mutable int write_count_ {0};
    mutable int set_count_ {0};
    mutable uint64_t offset_ {0};
    mutable uint64_t size_ {0};
    mutable uint64_t value_ {0};
};

TEST_F(BankObjectFixture, TestTransactionAccess) {
    auto b = TestBankTransactionAccess(&map_obj, "b");
    transaction_t t;

    // 0 byte write transaction
    Stubs::instance_.sim_get_transaction_bytes_.len = 0;
    Stubs::instance_.sim_transaction_is_write_ = true;
    Stubs::instance_.sim_transaction_size_ = 0;

    auto log_spec_violation_cnt_before
        = Stubs::instance_.sim_log_spec_violation_cnt_;
    exception_type_t ret = b.transaction_access(&t, 0);
    EXPECT_EQ(ret, Sim_PE_IO_Not_Taken);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_cnt_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
                      "0 byte transaction ignored");
    EXPECT_EQ(b.read_count_, 0);
    EXPECT_EQ(b.get_count_, 0);
    EXPECT_EQ(b.write_count_, 0);
    EXPECT_EQ(b.set_count_, 0);

    // 1 byte write to empty bank
    std::vector<uint8_t> buf(1);
    buf[0] = 0x12;

    Stubs::instance_.sim_get_transaction_bytes_.data = buf.data();
    Stubs::instance_.sim_get_transaction_bytes_.len = buf.size();
    Stubs::instance_.sim_transaction_is_write_ = true;
    Stubs::instance_.sim_transaction_is_inquiry_ = false;
    Stubs::instance_.sim_transaction_size_ = buf.size();

    ret = b.transaction_access(&t, 0xdeadbeef);
    EXPECT_EQ(ret, Sim_PE_No_Exception);
    EXPECT_EQ(b.read_count_, 0);
    EXPECT_EQ(b.get_count_, 0);
    EXPECT_EQ(b.write_count_, 1);
    EXPECT_EQ(b.set_count_, 0);
    EXPECT_EQ(b.offset_, 0xdeadbeef);
    EXPECT_EQ(b.value_, 0x12);
    EXPECT_EQ(b.size_, 1);

    // 2 byte inquiry write to empty bank
    buf.push_back(0x34);

    Stubs::instance_.sim_get_transaction_bytes_.data = buf.data();
    Stubs::instance_.sim_get_transaction_bytes_.len = buf.size();
    Stubs::instance_.sim_transaction_is_write_ = true;
    Stubs::instance_.sim_transaction_is_inquiry_ = true;
    Stubs::instance_.sim_transaction_size_ = buf.size();

    ret = b.transaction_access(&t, 0xc0ffee);
    EXPECT_EQ(ret, Sim_PE_No_Exception);
    EXPECT_EQ(b.read_count_, 0);
    EXPECT_EQ(b.get_count_, 0);
    EXPECT_EQ(b.write_count_, 1);
    EXPECT_EQ(b.set_count_, 1);
    EXPECT_EQ(b.offset_, 0xc0ffee);
    EXPECT_EQ(b.value_, 0x3412);
    EXPECT_EQ(b.size_, 2);

    // 4 byte read to empty bank
    buf.resize(4);

    Stubs::instance_.sim_get_transaction_bytes_.data = buf.data();
    Stubs::instance_.sim_get_transaction_bytes_.len = buf.size();
    Stubs::instance_.sim_transaction_is_write_ = false;
    Stubs::instance_.sim_transaction_is_read_ = true;
    Stubs::instance_.sim_transaction_is_inquiry_ = false;
    Stubs::instance_.sim_transaction_size_ = buf.size();

    ret = b.transaction_access(&t, 0xfeed);
    EXPECT_EQ(ret, Sim_PE_No_Exception);
    EXPECT_EQ(b.read_count_, 1);
    EXPECT_EQ(b.get_count_, 0);
    EXPECT_EQ(b.write_count_, 1);
    EXPECT_EQ(b.set_count_, 1);
    EXPECT_EQ(b.offset_, 0xfeed);
    EXPECT_EQ(b.size_, 4);

    // 8 byte inquiry read to empty bank
    buf.resize(8);

    Stubs::instance_.sim_get_transaction_bytes_.data = buf.data();
    Stubs::instance_.sim_get_transaction_bytes_.len = buf.size();
    Stubs::instance_.sim_transaction_is_write_ = false;
    Stubs::instance_.sim_transaction_is_read_ = true;
    Stubs::instance_.sim_transaction_is_inquiry_ = true;
    Stubs::instance_.sim_transaction_size_ = buf.size();

    ret = b.transaction_access(&t, 0xbaab);
    EXPECT_EQ(ret, Sim_PE_No_Exception);
    EXPECT_EQ(b.read_count_, 1);
    EXPECT_EQ(b.get_count_, 1);
    EXPECT_EQ(b.write_count_, 1);
    EXPECT_EQ(b.set_count_, 1);
    EXPECT_EQ(b.offset_, 0xbaab);
    EXPECT_EQ(b.size_, 8);

    // 12 byte inquiry read to empty bank
    buf.resize(12);

    Stubs::instance_.sim_get_transaction_bytes_.data = buf.data();
    Stubs::instance_.sim_get_transaction_bytes_.len = buf.size();
    Stubs::instance_.sim_transaction_is_write_ = false;
    Stubs::instance_.sim_transaction_is_read_ = true;
    Stubs::instance_.sim_transaction_is_inquiry_ = true;
    Stubs::instance_.sim_transaction_size_ = buf.size();

    ret = b.transaction_access(&t, 0x5566);
    EXPECT_EQ(ret, Sim_PE_No_Exception);
    EXPECT_EQ(b.read_count_, 1);
    EXPECT_EQ(b.get_count_, 2);
    EXPECT_EQ(b.write_count_, 1);
    EXPECT_EQ(b.set_count_, 1);
    EXPECT_EQ(b.offset_, 0x5566);
    EXPECT_EQ(b.size_, 12);

    // Access with large offset
    Stubs::instance_.sim_get_transaction_bytes_.data = buf.data();
    Stubs::instance_.sim_get_transaction_bytes_.len = buf.size();
    Stubs::instance_.sim_transaction_is_write_ = false;
    Stubs::instance_.sim_transaction_is_read_ = true;
    Stubs::instance_.sim_transaction_is_inquiry_ = false;
    Stubs::instance_.sim_transaction_size_ = buf.size();

    ret = b.transaction_access(&t, 1ULL << 63);
    EXPECT_EQ(ret, Sim_PE_No_Exception);
    EXPECT_EQ(b.read_count_, 2);
    EXPECT_EQ(b.get_count_, 2);
    EXPECT_EQ(b.write_count_, 1);
    EXPECT_EQ(b.set_count_, 1);
    EXPECT_EQ(b.offset_, 1ULL << 63);
    EXPECT_EQ(b.size_, 12);
}

class TestBankRead : public simics::Bank {
  public:
    using Bank::Bank;
    using Bank::read;
};

template<int size>
bool readAccessOutsideRegisters(const std::exception &ex) {
    EXPECT_EQ(std::string(ex.what()),
              "Read " + std::to_string(size)
              + " bytes at offset 0 outside registers or misaligned");
    return true;
}

TEST_F(BankObjectFixture, TestRead) {
    auto b = TestBankRead(&map_obj, "b");

    // Empty regs_
    EXPECT_PRED_THROW(b.read(0, 4), std::runtime_error,
                      readAccessOutsideRegisters<4>);

    // Add a register
    auto r1 = std::make_tuple("r1", std::string(""), 0,
                              4, 0x89abcdef, std::vector<simics::field_t>());
    b.add_register(r1);
    EXPECT_EQ(b.number_of_registers(), 1);

    for (simics::Inquiry inquiry : {simics::Inquiry::NonInquiry,
                                    simics::Inquiry::Inquiry}) {
        // test unaligned access
        auto ret = b.read(1, 1, inquiry);
        std::vector<uint8_t> expected {0xcd};
        EXPECT_EQ(ret, expected);

        // 1 bytes partial access (little endian byte order)
        ret = b.read(0, 1, inquiry);
        expected = {0xef};
        EXPECT_EQ(ret, expected);

        // 2 bytes partial access (little endian byte order)
        ret = b.read(0, 2, inquiry);
        expected = {0xef, 0xcd};
        EXPECT_EQ(ret, expected);

        // 4 bytes full access
        ret = b.read(0, 4, inquiry);
        expected = {0xef, 0xcd, 0xab, 0x89};
        EXPECT_EQ(ret, expected);

        // 8 bytes access (miss_pattern not set)
        if (inquiry == simics::Inquiry::NonInquiry) {
            EXPECT_PRED_THROW(b.read(0, 8, inquiry), std::runtime_error,
                              readAccessOutsideRegisters<8>);
        } else {
            ret = b.read(0, 8, inquiry);
            expected = {0xef, 0xcd, 0xab, 0x89, 0, 0, 0, 0};
            EXPECT_EQ(ret, expected);
        }

        // 8 bytes inquiry access (miss_pattern set)
        if (inquiry != simics::Inquiry::NonInquiry) {
            b.set_miss_pattern(0x34);
            ret = b.read(0, 8, inquiry);
            expected = {0xef, 0xcd, 0xab, 0x89, 0x34, 0x34, 0x34, 0x34};
            EXPECT_EQ(ret, expected);

            // Miss pattern can be changed
            b.set_miss_pattern(0x99);
            ret = b.read(0, 8, inquiry);
            expected = {0xef, 0xcd, 0xab, 0x89, 0x99, 0x99, 0x99, 0x99};
            EXPECT_EQ(ret, expected);
        }
    }

    // Add another register
    auto r2 = std::make_tuple("r2", std::string(""), 4,
                              4, 0x1234567, std::vector<simics::field_t>());
    b.add_register(r2);
    EXPECT_EQ(b.number_of_registers(), 2);

    for (simics::Inquiry inquiry : {simics::Inquiry::NonInquiry,
                                    simics::Inquiry::Inquiry}) {
        // Normal access
        auto ret = b.read(4, 4, inquiry);
        std::vector<uint8_t> expected {0x67, 0x45, 0x23, 0x1};
        EXPECT_EQ(ret, expected);

        // Overlapped access
        ret = b.read(0, 8, inquiry);
        expected = {0xef, 0xcd, 0xab, 0x89, 0x67, 0x45, 0x23, 0x1};
        EXPECT_EQ(ret, expected);
    }
}

class TestBankWrite : public simics::Bank {
  public:
    using Bank::Bank;
    using Bank::write;
};

bool invalidSize(const std::exception &ex) {
    EXPECT_STREQ(ex.what(),
                 "Expected size(4) is larger than value's size(0)");
    return true;
}

template <int size>
bool writeAccessOutsideRegisters(const std::exception &ex) {
    EXPECT_EQ(std::string(ex.what()),
              "Write " + std::to_string(size)
              + " bytes at offset 0 outside registers or misaligned");
    return true;
}

TEST_F(BankObjectFixture, TestWrite) {
    auto b = TestBankWrite(&map_obj, "b");

    // Invalid size
    // size is 4 while the container is empty
    EXPECT_PRED_THROW(b.write(0, {}, 4), std::invalid_argument,
                      invalidSize);

    // Empty regs_
    EXPECT_PRED_THROW(b.write(0, {0xa}, 1), std::runtime_error,
                      writeAccessOutsideRegisters<1>);

    // Add a register
    auto r1 = std::make_tuple("r1", std::string(""), 0,
                              4, 0, std::vector<simics::field_t>());
    b.add_register(r1);
    EXPECT_EQ(b.number_of_registers(), 1);
    auto reg1_iface = map_obj.get_iface<simics::RegisterInterface>("b.r1");

    std::vector<uint8_t> value {0xef, 0xcd, 0xab, 0x89,
            0x67, 0x45, 0x23, 0x1};
    for (simics::Inquiry inquiry : {simics::Inquiry::NonInquiry,
                                    simics::Inquiry::Inquiry}) {
        // Write 1 byte to offset 1
        b.write(1, value, 1, inquiry);
        EXPECT_EQ(reg1_iface->get(), 0xef00);

        // 1 bytes partial access (little endian byte order)
        b.write(0, value, 1, inquiry);
        EXPECT_EQ(reg1_iface->get(), 0xefef);

        // 2 bytes partial access (little endian byte order)
        b.write(0, value, 2, inquiry);
        EXPECT_EQ(reg1_iface->get(), 0xcdef);

        reg1_iface->reset();
    }

    // Add another register
    auto r2 = std::make_tuple("r2", std::string(""), 4,
                              4, 0x1234567,
                              std::vector<simics::field_t>());
    b.add_register(r2);
    EXPECT_EQ(b.number_of_registers(), 2);
    auto reg2_iface = map_obj.get_iface<simics::RegisterInterface>("b.r2");

    for (simics::Inquiry inquiry : {simics::Inquiry::NonInquiry,
                                    simics::Inquiry::Inquiry}) {
        // Normal access
        b.write(4, {0x67, 0x45, 0x23, 0x1}, 4, inquiry);
        EXPECT_EQ(reg2_iface->get(), 0x1234567);

        // Overlapped access
        b.write(0, value, 8);
        EXPECT_EQ(reg1_iface->get(), 0x89abcdef);
        EXPECT_EQ(reg2_iface->get(), 0x1234567);

        reg1_iface->reset();
        reg2_iface->reset();
    }
}

class MockCallbacks : public simics::BankIssueCallbacksInterface {
  public:
    void issue_callbacks(simics::BankAccess *handle,
                         simics::CallbackType type) const override {
        if (type == simics::CallbackType::AR) {
            ++ar_count_;
            handle->value = 0xdead;
        } else if (type == simics::CallbackType::AW) {
            ++aw_count_;
        } else if (type == simics::CallbackType::BR) {
            ++br_count_;
        } else if (type == simics::CallbackType::BW) {
            ++bw_count_;
            handle->value = 0xdead;
        }
    }

    mutable int ar_count_ {0};
    mutable int aw_count_ {0};
    mutable int br_count_ {0};
    mutable int bw_count_ {0};
};

TEST_F(BankObjectFixture, TestCallback) {
    auto b = simics::Bank(&map_obj, "b");
    MockCallbacks c;
    b.set_callbacks(&c);

    // write
    std::vector<uint8_t> buf {0x12};
    Stubs::instance_.sim_get_transaction_bytes_.data = buf.data();
    Stubs::instance_.sim_get_transaction_bytes_.len = buf.size();
    Stubs::instance_.sim_transaction_is_write_ = true;
    Stubs::instance_.sim_transaction_is_read_ = false;
    Stubs::instance_.sim_transaction_is_inquiry_ = false;
    Stubs::instance_.sim_transaction_size_ = buf.size();

    transaction_t t;
    auto ret = b.transaction_access(&t, 0xca11bac0);
    EXPECT_EQ(ret, Sim_PE_IO_Not_Taken);
    EXPECT_EQ(c.ar_count_, 0);
    EXPECT_EQ(c.aw_count_, 1);
    EXPECT_EQ(c.br_count_, 0);
    EXPECT_EQ(c.bw_count_, 1);

    // inquiry write will not trigger the callback
    Stubs::instance_.sim_transaction_is_inquiry_ = true;
    ret = b.transaction_access(&t, 0xca11bac0);
    EXPECT_EQ(ret, Sim_PE_No_Exception);
    EXPECT_EQ(c.ar_count_, 0);
    EXPECT_EQ(c.aw_count_, 1);
    EXPECT_EQ(c.br_count_, 0);
    EXPECT_EQ(c.bw_count_, 1);

    // inquiry read will not trigger the callback
    Stubs::instance_.sim_transaction_is_write_ = false;
    Stubs::instance_.sim_transaction_is_read_ = true;
    ret = b.transaction_access(&t, 0xca11bac0);
    EXPECT_EQ(ret, Sim_PE_No_Exception);
    EXPECT_EQ(c.ar_count_, 0);
    EXPECT_EQ(c.aw_count_, 1);
    EXPECT_EQ(c.br_count_, 0);
    EXPECT_EQ(c.bw_count_, 1);

    // read
    Stubs::instance_.sim_transaction_is_inquiry_ = false;
    ret = b.transaction_access(&t, 0xca11bac0);
    EXPECT_EQ(ret, Sim_PE_IO_Not_Taken);
    EXPECT_EQ(c.ar_count_, 1);
    EXPECT_EQ(c.aw_count_, 1);
    EXPECT_EQ(c.br_count_, 1);
    EXPECT_EQ(c.bw_count_, 1);

    // set callbacks to nullptr will not trigger any callbacks
    b.set_callbacks(nullptr);
    ret = b.transaction_access(&t, 0xca11bac0);
    EXPECT_EQ(ret, Sim_PE_IO_Not_Taken);
    EXPECT_EQ(c.ar_count_, 1);
    EXPECT_EQ(c.aw_count_, 1);
    EXPECT_EQ(c.br_count_, 1);
    EXPECT_EQ(c.bw_count_, 1);

    // set it back will trigger again
    b.set_callbacks(&c);
    ret = b.transaction_access(&t, 0xca11bac0);
    EXPECT_EQ(ret, Sim_PE_IO_Not_Taken);
    EXPECT_EQ(c.ar_count_, 2);
    EXPECT_EQ(c.aw_count_, 1);
    EXPECT_EQ(c.br_count_, 2);
    EXPECT_EQ(c.bw_count_, 1);

    // size > 8, read
    buf.resize(12);
    Stubs::instance_.sim_get_transaction_bytes_.data = buf.data();
    Stubs::instance_.sim_get_transaction_bytes_.len = buf.size();
    Stubs::instance_.sim_transaction_size_ = 12;
    Stubs::instance_.sim_transaction_is_write_ = false;
    Stubs::instance_.sim_transaction_is_read_ = true;
    Stubs::instance_.sim_transaction_is_inquiry_ = false;
    ret = b.transaction_access(&t, 0xca11bac0);
    EXPECT_EQ(c.ar_count_, 3);
    EXPECT_EQ(c.aw_count_, 1);
    EXPECT_EQ(c.br_count_, 3);
    EXPECT_EQ(c.bw_count_, 1);

    // size > 8, write
    Stubs::instance_.sim_transaction_is_write_ = true;
    Stubs::instance_.sim_transaction_is_read_ = false;
    ret = b.transaction_access(&t, 0xca11bac0);
    EXPECT_EQ(c.ar_count_, 3);
    EXPECT_EQ(c.aw_count_, 2);
    EXPECT_EQ(c.br_count_, 3);
    EXPECT_EQ(c.bw_count_, 2);
}

TEST_F(BankObjectFixture, TestRegisterArray) {
    auto b = simics::Bank(&map_obj, "b");

    // Single dimension register array
    auto attr_cnt = Stubs::instance_.sim_register_attribute_with_user_data_cnt_;
    Stubs::instance_.sim_register_attribute_with_user_data_names_.clear();
    auto num_regs = b.number_of_registers();
    b.add_register({"r_1d[2]", "1-dimensional register array", 0, 4, 0xab, {}});
    EXPECT_EQ(b.number_of_registers(), num_regs + 2);
    EXPECT_EQ(
            Stubs::instance_.sim_register_attribute_with_user_data_cnt_,
            attr_cnt + 1);
    auto names = Stubs::instance_.sim_register_attribute_with_user_data_names_;
    EXPECT_EQ(names.size(), 1);
    EXPECT_NE(names.find("r_1d"), names.end());
    auto regs = b.mapped_registers();
    for (int i = 0; i < 2; ++i) {
        EXPECT_EQ(regs.at(4 * i)->name(),
                          "r_1d[" + std::to_string(i) + ']');
    }

    // 2-dimensions register array
    attr_cnt = Stubs::instance_.sim_register_attribute_with_user_data_cnt_;
    Stubs::instance_.sim_register_attribute_with_user_data_names_.clear();
    num_regs = b.number_of_registers();
    b.add_register({"r_2d[2 stride 16][3]", "2-dimensional register array",
                0x10, 2, 0xcd, {}});
    EXPECT_EQ(b.number_of_registers(), num_regs + 2 * 3);
    EXPECT_EQ(
            Stubs::instance_.sim_register_attribute_with_user_data_cnt_,
            attr_cnt + 1);
    names = Stubs::instance_.sim_register_attribute_with_user_data_names_;
    EXPECT_EQ(names.size(), 1);
    EXPECT_NE(names.find("r_2d"), names.end());
    regs = b.mapped_registers();
    for (int i = 0; i < 2; ++i) {
        for (int j = 0; j < 2; ++j) {
            EXPECT_EQ(regs.at(0x10 + 16 * i + 2 * j)->name(),
                              "r_2d[" + std::to_string(i) + "]["
                              + std::to_string(j) + ']');
        }
    }

    // 3-dimensions register array
    attr_cnt = Stubs::instance_.sim_register_attribute_with_user_data_cnt_;
    Stubs::instance_.sim_register_attribute_with_user_data_names_.clear();
    num_regs = b.number_of_registers();
    b.add_register({"r_3d[4][2 stride 16][3]", "3-dimensional register array",
                0x30, 2, 0xcd, {}});
    EXPECT_EQ(b.number_of_registers(), num_regs + 4 * 2 * 3);
    EXPECT_EQ(
            Stubs::instance_.sim_register_attribute_with_user_data_cnt_,
            attr_cnt + 1);
    names = Stubs::instance_.sim_register_attribute_with_user_data_names_;
    EXPECT_EQ(names.size(), 1);
    EXPECT_NE(names.find("r_3d"), names.end());
    regs = b.mapped_registers();
    for (int i = 0; i < 4; ++i) {
        for (int j = 0; j < 2; ++j) {
            for (int k = 0; k < 3; ++k) {
                EXPECT_EQ(
                        regs.at(0x30 + 32 * i + 16 * j + 2 * k)->name(),
                        "r_3d[" + std::to_string(i) + "]["
                        + std::to_string(j) + "][" + std::to_string(k) + ']');
            }
        }
    }
}

class TestBankAllocateBankMemory : public simics::Bank {
  public:
    using Bank::Bank;

    // Expose the function to public
    void allocate_bank_memory(std::string_view name) {
        Bank::allocate_bank_memory(name);
    }
};

TEST_F(BankObjectFixture, TestAllocateBankMemory) {
    TestBankAllocateBankMemory b(&map_obj, "b");
    b.allocate_bank_memory("b");

    // Can re-allocate
    b.allocate_bank_memory("other");

    b.add_register("r0", "", 0, 4, 0, std::vector<simics::field_t>());

    auto log_spec_violation_cnt_before
        = Stubs::instance_.sim_log_spec_violation_cnt_;
    // Cannot re-allocate after registers are added
    b.allocate_bank_memory("b");
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
                      log_spec_violation_cnt_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
              "Cannot reset an allocated non-empty bank memory, ignored");
}

TEST_F(BankObjectFixture, TestAddRegisterOverlapCases) {
    auto b = simics::Bank(&map_obj, "b_overlap");
    auto log_error_cnt_before = Stubs::instance_.sim_log_error_cnt_;

    // Add a register at offset 4, size 4: covers [4,8)
    auto r1 = std::make_tuple("r1", std::string(""), 4,
                              4, 0, std::vector<simics::field_t>());
    b.add_register(r1);
    EXPECT_EQ(b.number_of_registers(), 1);

    // Case 1: New register starts before r1 and extends into it: [2,6)
    auto r2 = std::make_tuple("r2", std::string(""), 2,
                              4, 0, std::vector<simics::field_t>());
    b.add_register(r2);
    EXPECT_EQ(b.number_of_registers(), 1);  // Should not add
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, ++log_error_cnt_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Cannot add register(r2): offset overlapped"
              " with existing registers on the bank");

    // Case 2: New register starts after r1 but overlaps its end: [6,10)
    auto r3 = std::make_tuple("r3", std::string(""), 6,
                              4, 0, std::vector<simics::field_t>());
    b.add_register(r3);
    EXPECT_EQ(b.number_of_registers(), 1);  // Should not add
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, ++log_error_cnt_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Cannot add register(r3): offset overlapped"
              " with existing registers on the bank");

    // Case 3: New register is completely before: [0,2)
    auto r4 = std::make_tuple("r4", std::string(""), 0,
                              2, 0, std::vector<simics::field_t>());
    b.add_register(r4);
    EXPECT_EQ(b.number_of_registers(), 2);  // Should add

    // Case 4: New register is completely after: [10,12)
    auto r5 = std::make_tuple("r5", std::string(""), 10,
                              2, 0, std::vector<simics::field_t>());
    b.add_register(r5);
    EXPECT_EQ(b.number_of_registers(), 3);  // Should add

    // Case 5: New register exactly matches an existing one: [4,8)
    auto r6 = std::make_tuple("r6", std::string(""), 4,
                              4, 0, std::vector<simics::field_t>());
    b.add_register(r6);
    EXPECT_EQ(b.number_of_registers(), 3);  // Should not add
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, ++log_error_cnt_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Cannot add register(r6): offset overlapped"
              " with existing registers on the bank");
}

class ThrowingBank : public simics::Bank {
  public:
    using simics::Bank::Bank;
    std::vector<uint8_t> read(uint64_t, size_t,
                              simics::Inquiry) const override {
        throw std::runtime_error("test read exception");
    }
    void write(uint64_t, const std::vector<uint8_t>&, size_t,
               simics::Inquiry) const override {
        throw std::runtime_error("test write exception");
    }
};

TEST_F(BankObjectFixture, TestBankAccessExceptionLogsSpecViolation) {
    ThrowingBank bank(&map_obj, "b0");
    transaction_t t;

    // Test read exception
    std::vector<uint8_t> buf(4, 0);
    Stubs::instance_.sim_get_transaction_bytes_.data = buf.data();
    Stubs::instance_.sim_get_transaction_bytes_.len = buf.size();
    Stubs::instance_.sim_transaction_is_write_ = false;
    Stubs::instance_.sim_transaction_is_read_ = true;
    Stubs::instance_.sim_transaction_is_inquiry_ = false;
    Stubs::instance_.sim_transaction_size_ = buf.size();

    auto log_count_before = Stubs::instance_.sim_log_spec_violation_cnt_;
    bank.transaction_access(&t, 0);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
              log_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
              std::string("test read exception"));

    // Test write exception
    buf = {0x12, 0x34, 0x56, 0x78};
    Stubs::instance_.sim_get_transaction_bytes_.data = buf.data();
    Stubs::instance_.sim_get_transaction_bytes_.len = buf.size();
    Stubs::instance_.sim_transaction_is_write_ = true;
    Stubs::instance_.sim_transaction_is_read_ = false;
    Stubs::instance_.sim_transaction_is_inquiry_ = false;
    Stubs::instance_.sim_transaction_size_ = buf.size();

    log_count_before = Stubs::instance_.sim_log_spec_violation_cnt_;
    bank.transaction_access(&t, 0);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
              log_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
              std::string("test write exception"));
}
