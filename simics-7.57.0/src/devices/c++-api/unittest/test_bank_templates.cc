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

#include <simics/bank-templates.h>

#include <gtest/gtest.h>

#include <string>
#include <vector>

#include "mock/mock-object.h"
#include "mock/stubs.h"
#include "unittest/bank-object-fixture.h"

class TestBigEndianBankRead : public simics::BigEndianBank {
  public:
    using BigEndianBank::BigEndianBank;
    using BigEndianBank::read;
};

TEST_F(BankObjectFixture, TestBigEndianBankRead) {
    auto b = TestBigEndianBankRead(&map_obj, "b0");
    EXPECT_EQ(b.get_byte_order(), simics::ByteOrder::BE);

    // Add a register
    auto r1 = std::make_tuple("r1", std::string(""), 0,
                              4, 0x89abcdef, std::vector<simics::field_t>());
    b.add_register(r1);
    EXPECT_EQ(b.number_of_registers(), 1);

    // 1 bytes partial access
    auto ret = b.read(0, 1);
    std::vector<uint8_t> expected {0xef};
    EXPECT_EQ(ret, expected);

    // 2 bytes partial access
    ret = b.read(0, 2);
    expected = {0xcd, 0xef};
    EXPECT_EQ(ret, expected);

    // 4 bytes full access
    ret = b.read(0, 4);
    expected = {0x89, 0xab, 0xcd, 0xef};
    EXPECT_EQ(ret, expected);
}

class TestBigEndianBankWrite : public simics::BigEndianBank {
  public:
    using BigEndianBank::BigEndianBank;
    using BigEndianBank::write;
    using BigEndianBank::read;
};

TEST_F(BankObjectFixture, TestBigEndianBankWrite) {
    auto b = TestBigEndianBankWrite(&map_obj, "b0");
    EXPECT_EQ(b.get_byte_order(), simics::ByteOrder::BE);

    // Add a register
    auto r1 = std::make_tuple("r1", std::string(""), 0,
                              8, 0, std::vector<simics::field_t>());
    b.add_register(r1);
    EXPECT_EQ(b.number_of_registers(), 1);

    // 1 bytes partial inquiry access
    std::vector<uint8_t> expected {0xef};
    b.write(0, expected, 1, simics::Inquiry::Inquiry);
    EXPECT_EQ(b.read(0, 1, simics::Inquiry::Inquiry), expected);

    // 2 bytes partial inquiry access
    expected = {0xab, 0xcd};
    b.write(1, expected, 2, simics::Inquiry::Inquiry);
    EXPECT_EQ(b.read(1, 2, simics::Inquiry::Inquiry), expected);

    // 4 bytes full inquiry access
    expected = {0x23, 0x45, 0x67, 0x89};
    b.write(3, expected, 4, simics::Inquiry::Inquiry);
    EXPECT_EQ(b.read(3, 4, simics::Inquiry::Inquiry), expected);
}

class TestMissPatternBankRead : public simics::MissPatternBank {
  public:
    using MissPatternBank::MissPatternBank;
    using MissPatternBank::read;
};

TEST_F(BankObjectFixture, TestMissPatternBank) {
    auto b = TestMissPatternBankRead(&map_obj, "b0", 0x22);
    auto r1 = std::make_tuple("r1", std::string(""), 0,
                              4, 0x89abcdef, std::vector<simics::field_t>());
    b.add_register(r1);
    EXPECT_EQ(b.number_of_registers(), 1);

    auto ret = b.read(0, 8);
    std::vector<uint8_t> expected {
        0xef, 0xcd, 0xab, 0x89, 0x22, 0x22, 0x22, 0x22};
    EXPECT_EQ(ret, expected);
}

class MockBankPort : public simics::BankPortInterface {
  public:
    MockBankPort(std::string_view bank_name,
                 simics::MappableConfObject *dev_obj)
        : bank_name_(bank_name),
          dev_obj_(dev_obj) {}

    std::string_view bank_name() const override {
        return bank_name_;
    }

    const simics::BankInterface *bank_iface() const override {
        return nullptr;
    }

    simics::MappableConfObject *dev_obj() const override {
        return dev_obj_;
    }

    bool validate_bank_iface() const override {
        return true;
    }

    void set_bank(const simics::bank_t &bank) override {
        bank_ = bank;
    }

    std::string_view bank_name_;
    simics::MappableConfObject *dev_obj_;
    simics::bank_t bank_ {"invalid", "invalid", {}};
};

class BankWithManyArguments : public simics::Bank {
  public:
    BankWithManyArguments(simics::MappableConfObject *dev_obj,
                          const std::string &name,
                          int a, char *b, const std::vector<uint8_t> &c)
        : Bank::Bank(dev_obj, name),
          a_(a), b_(b), c_(c) {}

    int a_;
    char *b_;
    std::vector<uint8_t> c_;
};

TEST_F(BankObjectFixture, TestPortBank) {
    {
        // Default template parameter
        auto p = MockBankPort("test_bank", &map_obj);
        auto b = simics::PortBank<>(&p, "some description");
        EXPECT_EQ(std::get<simics::Name>(p.bank_), "test_bank");
        EXPECT_EQ(std::get<simics::Description>(p.bank_), "some description");
        EXPECT_EQ(b.name(), "test_bank");
        EXPECT_EQ(b.dev_obj(), &map_obj);
        EXPECT_EQ(map_obj.get_iface<simics::BankInterface>("test_bank"), &b);
    }
    {
        // Test extra template arguments
        auto p = MockBankPort("test_bank", &map_obj);
        std::vector<uint8_t> v {0xa, 0xb};
        char *c = reinterpret_cast<char *>(uintptr_t{0xdeadbeef});
        auto b = simics::PortBank<BankWithManyArguments, int, char *,
                                  const std::vector<uint8_t> &>(
                &p, "some description", 0xab, c, v);
        EXPECT_EQ(std::get<simics::Name>(p.bank_), "test_bank");
        EXPECT_EQ(std::get<simics::Description>(p.bank_), "some description");
        EXPECT_EQ(b.name(), "test_bank");
        EXPECT_EQ(b.dev_obj(), &map_obj);
        EXPECT_EQ(map_obj.get_iface<simics::BankInterface>("test_bank"), &b);
        EXPECT_EQ(b.a_, 0xab);
        EXPECT_EQ(b.b_, c);
        EXPECT_EQ(b.c_, v);
    }
}

TEST_F(BankObjectFixture, TestSharedMemoryBank) {
    simics::SharedMemoryBank b1(&map_obj, "b1", "name_of_shared_memory");
    auto *mem = map_obj.get_bank_memory("_name_of_shared_memory");
    EXPECT_EQ(mem->size(), 0);

    // Add a 8 bytes register at offset 0
    auto r1 = std::make_tuple("r1", std::string(""), 0,
                              8, 0, std::vector<simics::field_t>());
    b1.add_register(r1);
    EXPECT_EQ(mem->size(), 8);

    // Another bank sharing the same bank memory
    simics::SharedMemoryBank b2(&map_obj, "b2", "name_of_shared_memory");

    // Add a 4 bytes register at offset 6
    auto r2 = std::make_tuple("r2", std::string(""), 6,
                              4, 0, std::vector<simics::field_t>());
    b2.add_register(r2);
    // Since the two banks share memory, r2 partially overlaps with r1
    // in memory. The total allocated bytes is now 10.
    EXPECT_EQ(mem->size(), 10);
}
