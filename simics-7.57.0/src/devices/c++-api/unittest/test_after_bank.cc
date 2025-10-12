// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2024 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/


#include <simics/after-bank.h>

#include <gtest/gtest.h>
#include <memory>
#include <string>
#include <tuple>
#include <utility>

#include "mock/gtest_extensions.h"  // EXPECT_PRED_THROW
#include "mock/mock-bank.h"
#include "mock/mock-register.h"
#include "mock/stubs.h"

int test_bank_function_call1_count = 0;
const char *test_bank_function_call2_string {""};
class TestBankFunctionCall : public MockBank {
  public:
    void test_bank_function_call1() {
        ++test_bank_function_call1_count;
    }

    void test_bank_function_call2(std::string s) {
        test_bank_function_call2_string = s.c_str();
    }
};

TEST(TestAfter, TestBankFunctionCallNoArgument) {
    TestBankFunctionCall t;
    Stubs::instance_.sim_object_data_ret_ = &t;

    simics::RegBankFunctionCall<TestBankFunctionCall> bfc {
        &TestBankFunctionCall::test_bank_function_call1,
        "&TestBankFunctionCall::test_bank_function_call1"
    };

    // Test class methods
    std::string expected_name {
        std::string("&TestBankFunctionCall::test_bank_function_call1")
        + typeid(&TestBankFunctionCall::test_bank_function_call1).name()
    };
    EXPECT_EQ(bfc.name(), expected_name);

    simics::AttrValue attr {bfc.get_value()};
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    std::string name = SIM_attr_string(SIM_attr_list_item(attr, 0));
    EXPECT_EQ(name, expected_name);
    auto value = simics::attr_to_std<
        std::pair<std::string,
                  std::tuple<simics::ConfObjectRef, std::string>>>(attr);
    EXPECT_EQ(value, std::make_pair(expected_name,
                                    std::make_tuple(
                                        simics::ConfObjectRef(nullptr),
                                        std::string(""))));

    auto obj = std::unique_ptr<conf_object_t>();
    bfc.set_args(simics::AttrValue(simics::std_to_attr<
                 std::tuple<simics::ConfObjectRef, std::string>>(
                     std::make_tuple(simics::ConfObjectRef(obj.get()),
                                     std::string("b")))));
    EXPECT_THROW(bfc.set_args(
                    simics::AttrValue(
                        simics::std_to_attr<std::tuple<simics::ConfObjectRef,
                        int>>(std::make_tuple(simics::ConfObjectRef(obj.get()),
                                              2)))),
                 simics::detail::SetIllegalType);

    std::unique_ptr<simics::AfterCallInterface> new_bfc {bfc.make_copy()};
    EXPECT_EQ(new_bfc->name(), expected_name);
    attr = new_bfc->get_value();
    value = simics::attr_to_std<
        std::pair<std::string, std::tuple<simics::ConfObjectRef,
                                          std::string>>>(attr);
    EXPECT_EQ(value,
              std::make_pair(expected_name,
                             std::make_tuple(simics::ConfObjectRef(obj.get()),
                                             std::string("b"))));
}

TEST(TestAfter, TestBankFunctionCallOneStrArgument) {
    TestBankFunctionCall t;
    Stubs::instance_.sim_object_data_ret_ = &t;

    simics::RegBankFunctionCall<TestBankFunctionCall, std::string> bfc {
        &TestBankFunctionCall::test_bank_function_call2,
        "&TestBankFunctionCall::test_bank_function_call2"
    };

    // Test class methods
    std::string expected_name {
        std::string("&TestBankFunctionCall::test_bank_function_call2")
        + typeid(&TestBankFunctionCall::test_bank_function_call2).name()
    };
    EXPECT_EQ(bfc.name(), expected_name);

    simics::AttrValue attr {bfc.get_value()};
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    std::string name = SIM_attr_string(SIM_attr_list_item(attr, 0));
    EXPECT_EQ(name, expected_name);
    auto value = simics::attr_to_std<
        std::pair<std::string,
                  std::tuple<simics::ConfObjectRef,
                             std::string, std::string>>>(attr);
    EXPECT_EQ(value, std::make_pair(expected_name,
                                    std::make_tuple(
                                        simics::ConfObjectRef(nullptr),
                                        std::string(""), std::string(""))));

    std::string test_s {"coffee"};
    auto obj = std::unique_ptr<conf_object_t>();
    bfc.set_args(simics::AttrValue(simics::std_to_attr<
                 std::tuple<simics::ConfObjectRef, std::string, std::string>>(
                         std::make_tuple(simics::ConfObjectRef(obj.get()),
                                         std::string("b"), test_s))));
    EXPECT_THROW(
            bfc.set_args(simics::AttrValue(
               simics::std_to_attr<std::tuple<simics::ConfObjectRef,
               int>>(std::make_tuple(simics::ConfObjectRef(obj.get()), 2)))),
            simics::detail::SetIllegalType);

    std::unique_ptr<simics::AfterCallInterface> new_bfc {bfc.make_copy()};
    EXPECT_EQ(new_bfc->name(), expected_name);
    attr = new_bfc->get_value();
    value = simics::attr_to_std<
        std::pair<std::string, std::tuple<simics::ConfObjectRef,
                                          std::string, std::string>>>(attr);
    EXPECT_EQ(value,
              std::make_pair(expected_name,
                             std::make_tuple(simics::ConfObjectRef(obj.get()),
                                             std::string("b"), test_s)));
}

int test_register_function_call1_count = 0;
int test_register_function_call2_int = 0;
class TestRegisterFunctionCall : public MockRegister {
  public:
    using MockRegister::MockRegister;
    void test_register_function_call1() {
        ++test_register_function_call1_count;
    }

    void test_register_function_call2(int i) {
        test_register_function_call2_int = i;
    }
};

TEST(TestAfter, TestRegisterFunctionCallNoArgument) {
    auto obj = std::make_unique<conf_object_t>();
    simics::MappableConfObject map_obj {obj.get()};
    TestRegisterFunctionCall t {&map_obj, "b.r"};
    Stubs::instance_.sim_object_data_ret_ = &t;

    simics::RegBankFunctionCall<TestRegisterFunctionCall> rfc {
        &TestRegisterFunctionCall::test_register_function_call1,
        "&TestRegisterFunctionCall::test_register_function_call1"
    };

    // Test class methods
    std::string expected_name {
        std::string("&TestRegisterFunctionCall::test_register_function_call1")
        + typeid(&TestRegisterFunctionCall::test_register_function_call1).name()
    };
    EXPECT_EQ(rfc.name(), expected_name);

    simics::AttrValue attr {rfc.get_value()};
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    std::string name = SIM_attr_string(SIM_attr_list_item(attr, 0));
    EXPECT_EQ(name, expected_name);
    auto value = simics::attr_to_std<
        std::pair<std::string,
                  std::tuple<simics::ConfObjectRef, std::string>>>(attr);
    EXPECT_EQ(value, std::make_pair(expected_name,
                                    std::make_tuple(
                                        simics::ConfObjectRef(nullptr),
                                        std::string(""))));

    rfc.set_args(simics::AttrValue(simics::std_to_attr<
                 std::tuple<simics::ConfObjectRef, std::string>>(
                         std::make_tuple(simics::ConfObjectRef(obj.get()),
                                         std::string("b.r")))));
    EXPECT_THROW(
            rfc.set_args(simics::AttrValue(
               simics::std_to_attr<std::tuple<simics::ConfObjectRef,
               int>>(std::make_tuple(simics::ConfObjectRef(obj.get()), 2)))),
            simics::detail::SetIllegalType);

    std::unique_ptr<simics::AfterCallInterface> new_rfc {rfc.make_copy()};
    EXPECT_EQ(new_rfc->name(), expected_name);
    attr = new_rfc->get_value();
    value = simics::attr_to_std<
        std::pair<std::string, std::tuple<simics::ConfObjectRef,
                                          std::string>>>(attr);
    EXPECT_EQ(value,
              std::make_pair(expected_name,
                             std::make_tuple(simics::ConfObjectRef(obj.get()),
                                             std::string("b.r"))));
}

TEST(TestAfter, TestRegisterFunctionCallOneIntArgument) {
    auto obj = std::make_unique<conf_object_t>();
    simics::MappableConfObject map_obj {obj.get()};
    TestRegisterFunctionCall t {&map_obj, "b.r"};
    Stubs::instance_.sim_object_data_ret_ = &t;

    simics::RegBankFunctionCall<TestRegisterFunctionCall, int> rfc {
        &TestRegisterFunctionCall::test_register_function_call2,
        "&TestRegisterFunctionCall::test_register_function_call2"
    };

    // Test class methods
    std::string expected_name {
        std::string("&TestRegisterFunctionCall::test_register_function_call2")
        + typeid(&TestRegisterFunctionCall::test_register_function_call2).name()
    };
    EXPECT_EQ(rfc.name(), expected_name);

    simics::AttrValue attr {rfc.get_value()};
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    std::string name = SIM_attr_string(SIM_attr_list_item(attr, 0));
    EXPECT_EQ(name, expected_name);
    auto value = simics::attr_to_std<
        std::pair<std::string,
                  std::tuple<simics::ConfObjectRef, std::string, int>>>(attr);
    EXPECT_EQ(value, std::make_pair(expected_name,
                                    std::make_tuple(
                                        simics::ConfObjectRef(nullptr),
                                        std::string(""), 0)));

    rfc.set_args(simics::AttrValue(simics::std_to_attr<
                 std::tuple<simics::ConfObjectRef, std::string, int>>(
                     std::make_tuple(simics::ConfObjectRef(obj.get()),
                                     std::string("b.r"), 0xc0ffee))));
    EXPECT_THROW(
            rfc.set_args(simics::AttrValue(
               simics::std_to_attr<std::tuple<simics::ConfObjectRef,
               int>>(std::make_tuple(simics::ConfObjectRef(obj.get()), 2)))),
            simics::detail::SetIllegalType);

    std::unique_ptr<simics::AfterCallInterface> new_rfc {rfc.make_copy()};
    EXPECT_EQ(new_rfc->name(), expected_name);
    attr = new_rfc->get_value();
    value = simics::attr_to_std<
        std::pair<std::string, std::tuple<simics::ConfObjectRef,
                                          std::string, int>>>(attr);
    EXPECT_EQ(value,
              std::make_pair(expected_name,
                             std::make_tuple(simics::ConfObjectRef(obj.get()),
                                             std::string("b.r"),
                                                    0xc0ffee)));
}

int test_field_function_call1_count = 0;
std::pair<int, bool> test_field_function_call2_pair {0, false};
class TestFieldFunctionCall: public simics::FieldInterface {
  public:
    explicit TestFieldFunctionCall(const std::string &name)
        : name_(name) {}

    std::string_view name() const override {
        return name_;
    }

    const std::string &description() const override {
        return name_;
    }

    unsigned number_of_bits() const override {
        return 1;
    }

    void init(std::string_view desc, const simics::bits_type &bits,
              int8_t offset) override {}

    simics::RegisterInterface *parent() const override {
        return nullptr;
    }

    void set(uint64_t value) override {}
    void write(uint64_t value, uint64_t enabled_bits) override {}
    uint64_t get() const override {
        return 0;
    }
    uint64_t read(uint64_t enabled_bits) override {
        return 0;
    }

    void test_field_function_call1() {
        ++test_field_function_call1_count;
    }

    void test_field_function_call2(std::pair<int, bool> p) {
        test_field_function_call2_pair = p;
    }

  private:
    std::string name_;
};

TEST(TestAfter, TestFieldFunctionCallNoArgument) {
    TestFieldFunctionCall t {"b.r.f"};
    Stubs::instance_.sim_object_data_ret_ = &t;

    simics::RegBankFunctionCall<TestFieldFunctionCall> ffc {
        &TestFieldFunctionCall::test_field_function_call1,
        "&TestFieldFunctionCall::test_field_function_call1"
    };

    // Test class methods
    std::string expected_name {
        std::string("&TestFieldFunctionCall::test_field_function_call1")
        + typeid(&TestFieldFunctionCall::test_field_function_call1).name()
    };
    EXPECT_EQ(ffc.name(), expected_name);

    simics::AttrValue attr {ffc.get_value()};
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    std::string name = SIM_attr_string(SIM_attr_list_item(attr, 0));
    EXPECT_EQ(name, expected_name);
    auto value = simics::attr_to_std<
        std::pair<std::string,
                  std::tuple<simics::ConfObjectRef, std::string>>>(attr);
    EXPECT_EQ(value, std::make_pair(expected_name,
                                    std::make_tuple(
                                        simics::ConfObjectRef(nullptr),
                                        std::string(""))));

    auto obj = std::make_unique<conf_object_t>();
    ffc.set_args(simics::AttrValue(simics::std_to_attr<
                 std::tuple<simics::ConfObjectRef, std::string>>(
                     std::make_tuple(simics::ConfObjectRef(obj.get()),
                                     std::string("b.r.f")))));
    EXPECT_THROW(
            ffc.set_args(simics::AttrValue(
               simics::std_to_attr<std::tuple<simics::ConfObjectRef,
               int>>(std::make_tuple(simics::ConfObjectRef(obj.get()), 2)))),
            simics::detail::SetIllegalType);

    std::unique_ptr<simics::AfterCallInterface> new_ffc {ffc.make_copy()};
    EXPECT_EQ(new_ffc->name(), expected_name);
    attr = new_ffc->get_value();
    value = simics::attr_to_std<
        std::pair<std::string, std::tuple<simics::ConfObjectRef,
                                          std::string>>>(attr);
    EXPECT_EQ(value,
              std::make_pair(expected_name,
                             std::make_tuple(simics::ConfObjectRef(obj.get()),
                                             std::string("b.r.f"))));
}

TEST(TestAfter, TestFieldFunctionCallOnePairArgument) {
    TestFieldFunctionCall t {"b.r.f"};
    Stubs::instance_.sim_object_data_ret_ = &t;

    simics::RegBankFunctionCall<TestFieldFunctionCall,
                                std::pair<int, bool>> ffc {
        &TestFieldFunctionCall::test_field_function_call2,
        "&TestFieldFunctionCall::test_field_function_call2"
    };

    // Test class methods
    std::string expected_name {
        std::string("&TestFieldFunctionCall::test_field_function_call2")
        + typeid(&TestFieldFunctionCall::test_field_function_call2).name()
    };
    EXPECT_EQ(ffc.name(), expected_name);

    simics::AttrValue attr {ffc.get_value()};
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    std::string name = SIM_attr_string(SIM_attr_list_item(attr, 0));
    EXPECT_EQ(name, expected_name);
    auto value = simics::attr_to_std<
        std::pair<std::string,
                  std::tuple<simics::ConfObjectRef, std::string,
                             std::pair<int, bool>>>>(attr);
    EXPECT_EQ(value, std::make_pair(expected_name,
                                    std::make_tuple(
                                        simics::ConfObjectRef(nullptr),
                                        std::string(""),
                                        std::make_pair(0, false))));

    std::unique_ptr<conf_object_t> obj {new conf_object_t};
    ffc.set_args(simics::AttrValue(simics::std_to_attr<
                 std::tuple<simics::ConfObjectRef, std::string,
                            std::pair<int, bool>>>(
                     std::make_tuple(simics::ConfObjectRef(obj.get()),
                                     std::string("b.r.f"),
                                     std::make_pair(2, true)))));
    EXPECT_THROW(
            ffc.set_args(simics::AttrValue(
               simics::std_to_attr<std::tuple<simics::ConfObjectRef,
               int>>(std::make_tuple(simics::ConfObjectRef(obj.get()), 2)))),
            simics::detail::SetIllegalType);

    std::unique_ptr<simics::AfterCallInterface> new_ffc {ffc.make_copy()};
    EXPECT_EQ(new_ffc->name(), expected_name);
    attr = new_ffc->get_value();
    value = simics::attr_to_std<
        std::pair<std::string, std::tuple<simics::ConfObjectRef,
                                          std::string,
                                          std::pair<int, bool>>>>(attr);
    EXPECT_EQ(value, std::make_pair(expected_name,
                                    std::make_tuple(
                                            simics::ConfObjectRef(obj.get()),
                                            std::string("b.r.f"),
                                            std::make_pair(2, true))));
}

TEST(TestAfter, TestMakeRegBankFunctionCall) {
    std::unique_ptr<simics::RegBankFunctionCall<TestBankFunctionCall>> fc1 {
        simics::make_reg_bank_function_call(
                &TestBankFunctionCall::test_bank_function_call1,
                "&TestBankFunctionCall::test_bank_function_call1")
    };
    static_assert(std::is_same_v<std::decay_t<decltype(fc1.get())>,
                  simics::RegBankFunctionCall<TestBankFunctionCall> *>,
                  "Expected a RegBankFunctionCall");

    std::unique_ptr<simics::RegBankFunctionCall<TestRegisterFunctionCall>> fc2 {
        simics::make_reg_bank_function_call(
                &TestRegisterFunctionCall::test_register_function_call1,
                "&TestRegisterFunctionCall::test_register_function_call1")
    };
    static_assert(std::is_same_v<std::decay_t<decltype(fc2.get())>,
                  simics::RegBankFunctionCall<TestRegisterFunctionCall> *>,
                  "Expected a RegBankFunctionCall");

    std::unique_ptr<simics::RegBankFunctionCall<TestFieldFunctionCall>> fc3 {
        simics::make_reg_bank_function_call(
                &TestFieldFunctionCall::test_field_function_call1,
                "&TestFieldFunctionCall::test_field_function_call1")
    };
    static_assert(std::is_same_v<std::decay_t<decltype(fc3.get())>,
                  simics::RegBankFunctionCall<TestFieldFunctionCall> *>,
                  "Expected a RegBankFunctionCall");
}
