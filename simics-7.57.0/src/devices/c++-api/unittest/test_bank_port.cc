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

#include <simics/attr-value.h>
#include <simics/bank-port.h>

#include <gtest/gtest.h>

#include <set>
#include <string>

#include "mock/mock-bank.h"
#include "mock/mock-object.h"
#include "mock/stubs.h"

// Test cases for BankPort
class BankPortTest : public ::testing::Test {
  protected:
    BankPortTest() {}

    void SetUp() override {
        Stubs::instance_.sim_port_object_parent_ret_ = dev_obj.obj();
        Stubs::instance_.sim_object_descendant_ret_ = port_obj.obj();
        Stubs::instance_.sim_object_data_ret_ = &map_obj;
        sim_log_info_cnt_ = Stubs::instance_.sim_log_info_cnt_;
        sim_log_spec_violation_cnt_ = \
            Stubs::instance_.sim_log_spec_violation_cnt_;
        sim_log_error_cnt_ = Stubs::instance_.sim_log_error_cnt_;
        Stubs::instance_.SIM_log_info_.clear();
        Stubs::instance_.SIM_log_spec_violation_.clear();
        Stubs::instance_.SIM_log_error_.clear();
        Stubs::instance_.sim_hap_callback_func_ = nullptr;
        Stubs::instance_.sim_register_interface_map_.clear();
    }

    void TearDown() override {
        Stubs::instance_.sim_port_object_parent_ret_ = nullptr;
        Stubs::instance_.sim_object_data_ret_ = nullptr;
        Stubs::instance_.sim_object_descendant_ret_ = nullptr;
        Stubs::instance_.sim_log_info_cnt_ = 0;
        Stubs::instance_.sim_log_spec_violation_cnt_ = 0;
        Stubs::instance_.sim_log_error_cnt_ = 0;
        Stubs::instance_.SIM_log_info_.clear();
        Stubs::instance_.SIM_log_spec_violation_.clear();
        Stubs::instance_.SIM_log_error_.clear();
        Stubs::instance_.sim_hap_callback_func_ = nullptr;
        Stubs::instance_.sim_register_interface_map_.clear();
        delete port_obj.obj();
    }

    void finalizeBankPort(void *bp) {
        Stubs::instance_.sim_object_data_ret_ = bp;
        auto obj_created = reinterpret_cast<
                void (*)(lang_void *, conf_object_t *)>(
                        Stubs::instance_.sim_hap_callback_func_);
        obj_created(nullptr, port_obj.obj());
    }

    MockObject dev_obj {
        reinterpret_cast<conf_object_t *>(0x1234), "foo"
    };
    simics::MappableConfObject map_obj {
        dev_obj.obj()
    };
    MockObject port_obj {
        new conf_object_t, "foo.bank.bar"
    };
    size_t sim_log_info_cnt_;
    size_t sim_log_spec_violation_cnt_;
    size_t sim_log_error_cnt_;
};

TEST_F(BankPortTest, TestCTOR) {
    {
        // Test that passing a nullptr ConfObjectRef to the BankPort
        // constructor throws an exception
        simics::ConfObjectRef null_ref(nullptr);
        EXPECT_THROW(
            {
                try {
                    simics::BankPort<simics::MappableConfObject> bp {
                        null_ref
                    };
                } catch (const std::invalid_argument &e) {
                    // Verify the exception message
                    EXPECT_STREQ(e.what(),
                        "ConfObjectRef passed to Port constructor is null");
                    throw;
                }
            },
            std::invalid_argument);
    }

    {
        // Test that passing a bank object with invalid format will throw
        // an exception
        // The name should be hierarchical, e.g., "foo.bank.bar"
        MockObject mock_obj {
            reinterpret_cast<conf_object_t *>(0xc0ffee), "foo.bar"
        };

        // One-argument CTOR
        EXPECT_THROW(
            {
                try {
                    simics::BankPort<simics::MappableConfObject> bp {
                        mock_obj.obj()
                    };
                } catch (const std::invalid_argument &e) {
                    // Verify the exception message
                    EXPECT_PRED_FORMAT2(::testing::IsSubstring, e.what(),
                        "Invalid bank port name (foo.bar)");
                    throw;
                }
            }, std::invalid_argument);

        // Two-arguments CTOR
        EXPECT_THROW(
            {
                try {
                    simics::BankPort<simics::MappableConfObject> bp(
                        mock_obj.obj(), nullptr);
                } catch (const std::invalid_argument &e) {
                    // Verify the exception message
                    EXPECT_PRED_FORMAT2(::testing::IsSubstring, e.what(),
                        "Invalid bank port name (foo.bar)");
                    throw;
                }
            }, std::invalid_argument);
    }

    {
        // Test that passing an invalid bank pointer will throw an exception
        EXPECT_THROW(
            {
                try {
                    simics::BankPort<simics::MappableConfObject> bp(
                        port_obj.obj(), nullptr);
                } catch (const std::invalid_argument &e) {
                    // Verify the exception message
                    EXPECT_PRED_FORMAT2(::testing::IsSubstring, e.what(),
                        "Bank pointer cannot be nullptr");
                    throw;
                }
            }, std::invalid_argument);
    }

    {
        simics::BankPort<simics::MappableConfObject> bp(port_obj.obj());

        // No logging
        EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, sim_log_info_cnt_);
        EXPECT_EQ(bp.bank_name(), "bar");
        EXPECT_EQ(bp.dev_obj(), &map_obj);
    }

    const simics::bank_t b {"bar", "a bank named bar", {/*No register*/}};

    {
        // Two-arguments CTOR
        simics::BankPort<simics::MappableConfObject> bp {port_obj.obj(), &b};

        EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, ++sim_log_info_cnt_);
        // Since no Bank "bar" in the map, a default bank for bar is created
        EXPECT_EQ(Stubs::instance_.SIM_log_info_,
                          "Created a new default bank for bar");
        EXPECT_EQ(bp.bank_name(), "bar");
        EXPECT_EQ(bp.dev_obj(), &map_obj);
        EXPECT_EQ(bp.big_endian_bitorder(), false);
        EXPECT_EQ(bp.number_of_registers(), 0);
    }

    {
        // Two-arguments CTOR
        MockBank bank;
        bank.name_ = "test";
        map_obj.erase_iface<simics::BankInterface>("bar");
        map_obj.set_iface<simics::BankInterface>("bar", &bank);
        simics::BankPort<simics::MappableConfObject> bp {port_obj.obj(), &b};

        EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, ++sim_log_info_cnt_);
        // Since Bank "bar" is in the map, user defined bank for bar is used
        EXPECT_EQ(Stubs::instance_.SIM_log_info_,
                  "Used user defined bank for bar");
        EXPECT_EQ(bp.bank_name(), "bar");
        EXPECT_EQ(bp.dev_obj(), &map_obj);
        EXPECT_EQ(bp.big_endian_bitorder(), false);
        EXPECT_EQ(bp.number_of_registers(), 0);
        map_obj.erase_iface<simics::BankInterface>("bar");
    }

    EXPECT_FALSE(std::is_copy_constructible<
                     simics::BankPort<simics::MappableConfObject>>::value);
    EXPECT_FALSE(std::is_copy_assignable<
                     simics::BankPort<simics::MappableConfObject>>::value);
}

TEST(TestBankPort, TestAddBankProperties) {
    auto sim_register_interface_cnt_ = \
        Stubs::instance_.sim_register_interface_cnt_;
    Stubs::instance_.a_conf_class_ = reinterpret_cast<conf_class_t*>(
            uintptr_t{0xdeadbeef});
    {
        auto ret = simics::make_class<MockObject>("test_add_bank_properties",
                                                  "short_desc", "description");

        simics::BankPort<simics::MappableConfObject>::addBankProperties(
                ret.get());
    }

    EXPECT_EQ(Stubs::instance_.sim_register_interface_cnt_,
              sim_register_interface_cnt_ + 6);

    std::set<std::string> expected_interface_names {
        "transaction", "register_view", "register_view_read_only",
        "register_view_catalog", "bank_instrumentation_subscribe",
        "instrumentation_order"
    };
    std::set<std::string> actual_keys;
    for (const auto& pair : Stubs::instance_.sim_register_interface_map_) {
        actual_keys.insert(pair.first);
    }
    EXPECT_EQ(actual_keys, expected_interface_names);
}

TEST_F(BankPortTest, TestBankPortInterface) {
    simics::BankPort<simics::MappableConfObject> bp {port_obj.obj()};

    EXPECT_EQ(bp.bank_name(), "bar");
    EXPECT_EQ(bp.bank_iface(), nullptr);
    EXPECT_EQ(bp.dev_obj(), &map_obj);

    bp.set_bank({"bar", "test description", {}});
    EXPECT_STREQ(bp.description(), "test description");
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_,
              ++sim_log_info_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
              "Created a new default bank for bar");
    EXPECT_NE(bp.bank_iface(), nullptr);

    // Bank interface can only be set once
    bp.set_bank({"bar", "test description 2", {}});
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, ++sim_log_error_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "bank iface can only be set once");

    simics::BankPort<simics::MappableConfObject> bp2 {port_obj.obj()};
    // Add a bank with a register
    bp2.set_bank({"bar", "test description",
                  {{"r", "a register with default value 42",
                   0, 4, 42, {}}},
                 });
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, sim_log_error_cnt_);
}

TEST_F(BankPortTest, TestTransactionInterface) {
    simics::BankPort<simics::MappableConfObject> bp {port_obj.obj()};

    EXPECT_EQ(bp.issue(nullptr, 0), Sim_PE_IO_Not_Taken);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
              ++sim_log_error_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "BankPort should have one bank");

    bp.set_bank({"bar", "test description", {}});
    Stubs::instance_.sim_transaction_size_ = 0;
    EXPECT_EQ(bp.issue(nullptr, 0), Sim_PE_IO_Not_Taken);
    EXPECT_EQ(Stubs::instance_.sim_log_spec_violation_cnt_,
              ++sim_log_spec_violation_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_spec_violation_,
              "0 byte transaction ignored");
}

TEST_F(BankPortTest, TestRegisterViewInterface) {
    simics::BankPort<simics::MappableConfObject> bp {port_obj.obj()};

    EXPECT_EQ(bp.description(), nullptr);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
              ++sim_log_error_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "BankPort should have one bank");

    EXPECT_EQ(bp.big_endian_bitorder(), false);

    // Empty bank port has no registers
    EXPECT_EQ(bp.number_of_registers(), 0);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, sim_log_error_cnt_);

    EXPECT_TRUE(SIM_attr_is_nil(bp.register_info(0)));
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
              ++sim_log_error_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Invalid register index 0");

    EXPECT_EQ(bp.get_register_value(0), 0);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
              ++sim_log_error_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Invalid register index 0");

    bp.set_register_value(0, 0xdead);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
              ++sim_log_error_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Invalid register index 0");

    // Add a bank with a register
    bp.set_bank({"bar", "test description",
                 {{"r", "a register with default value 42",
                  0, 4, 42, {}}},
                });
    finalizeBankPort(&bp);

    EXPECT_STREQ(bp.description(), "test description");

    EXPECT_EQ(bp.number_of_registers(), 1);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
              sim_log_error_cnt_);

    EXPECT_TRUE(SIM_attr_is_list(simics::AttrValue(bp.register_info(0))));
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
              sim_log_error_cnt_);

    EXPECT_EQ(bp.get_register_value(0), 42);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
              sim_log_error_cnt_);

    bp.set_register_value(0, 0);
    EXPECT_EQ(bp.get_register_value(0), 0);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
              sim_log_error_cnt_);
}

TEST_F(BankPortTest, TestRegisterViewReadOnlyInterface) {
    simics::BankPort<simics::MappableConfObject> bp {port_obj.obj()};

    EXPECT_EQ(bp.is_read_only(0), false);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
              ++sim_log_error_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Invalid register index 0");

    // Add a bank with a register
    bp.set_bank({"bar", "test description",
                 {{"r", "a register with default value 42",
                  0, 4, 42, {}}},
                });
    finalizeBankPort(&bp);

    EXPECT_EQ(bp.is_read_only(0), false);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
              sim_log_error_cnt_);
}

TEST_F(BankPortTest, TestRegisterViewCatalogInterface) {
    {
        simics::BankPort<simics::MappableConfObject> bp {port_obj.obj()};

        simics::AttrValue names {bp.register_names()};
        EXPECT_TRUE(SIM_attr_is_list(names));
        EXPECT_EQ(SIM_attr_list_size(names), 0);
        // Empty bank port has no registers
        EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, sim_log_error_cnt_);

        simics::AttrValue offsets {bp.register_offsets()};
        EXPECT_TRUE(SIM_attr_is_list(offsets));
        EXPECT_EQ(SIM_attr_list_size(offsets), 0);
        // No errors as register_offsets() does not access bank_iface_
        EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                  sim_log_error_cnt_);
    }

    {
        simics::BankPort<simics::MappableConfObject> bp {port_obj.obj()};

        // Add a bank with a register
        bp.set_bank({"bar", "test description",
                    {{"r", "a register with default value 42",
                    0, 4, 42, {}}},
                    });
        finalizeBankPort(&bp);

        simics::AttrValue names {bp.register_names()};
        EXPECT_TRUE(SIM_attr_is_list(names));
        EXPECT_EQ(SIM_attr_list_size(names), 1);
        EXPECT_EQ(simics::attr_to_std<std::string>(
                      SIM_attr_list_item(names, 0)), "r");
        simics::AttrValue offsets {bp.register_offsets()};
        EXPECT_TRUE(SIM_attr_is_list(offsets));
        EXPECT_EQ(SIM_attr_list_size(offsets), 1);
        EXPECT_EQ(simics::attr_to_std<int>(SIM_attr_list_item(offsets, 0)),
                  0);
        EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                  sim_log_error_cnt_);
    }
}

class TestPortBank {
  public:
    TestPortBank(simics::BankPortInterface *port_iface,
                 simics::Description desc) {
        port_iface->set_bank({port_iface->bank_name().data(), desc, {}});
    }
};

class TestPortBankWithArgs {
  public:
    TestPortBankWithArgs(simics::BankPortInterface *port_iface,
                         simics::Description desc, std::string suffix) {
        port_iface->set_bank({port_iface->bank_name().data(),
                              std::string(desc) + suffix, {}});
    }
};

TEST_F(BankPortTest, TestBankPortSimpleBankPort) {
    simics::SimpleBankPort<TestPortBank> bp {port_obj.obj()};

    EXPECT_EQ(bp.bank_name(), "bar");
    EXPECT_EQ(bp.dev_obj(), &map_obj);

    EXPECT_STREQ(bp.description(),
                 "A bank created through the SimicsBankPort utility class");

    simics::SimpleBankPort<TestPortBankWithArgs, std::string> bpa {
        port_obj.obj(), " with args"
    };

    EXPECT_EQ(bpa.bank_name(), "bar");
    EXPECT_EQ(bpa.dev_obj(), &map_obj);

    EXPECT_STREQ(bpa.description(),
                 "A bank created through the SimicsBankPort utility class"
                 " with args");
}
