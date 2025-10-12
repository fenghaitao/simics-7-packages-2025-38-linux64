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

#include <gtest/gtest.h>
#include <simics/after.h>

#include <cstdint>
#include <memory>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

#include "mock/counted-int.h"
#include "mock/gtest_extensions.h"  // EXPECT_PRED_THROW
#include "mock/mock-object.h"
#include "mock/stubs.h"

bool checkNullAfterCallInterface(const std::exception &ex) {
    EXPECT_STREQ(ex.what(), "AfterCallInterface pointer cannot be nullptr");
    return true;
}

bool checkFindWithEmptyName(const std::exception &ex) {
    EXPECT_STREQ(ex.what(),
                 "Empty name cannot be used to find AfterCallInterface");
    return true;
}

int test_after_call_invoke_count = 0;
int test_after_call_set_args_count = 0;
int test_after_call_get_value_count = 0;
class TestAfterCall : public simics::AfterCallInterface {
  public:
    explicit TestAfterCall(const std::string &name) : name_(name) {}

    std::string name() const override {
        return name_;
    }
    // Following methods are not implemented
    simics::AfterCallInterface *make_copy() override {
        return this;
    }
    void set_args(const attr_value_t &args) override {
        ++test_after_call_set_args_count;
    }
    void invoke() override {
        ++test_after_call_invoke_count;
    }
    attr_value_t get_value() override {
        ++test_after_call_get_value_count;
        return {};
    }

  private:
    std::string name_;
};

TEST(TestAfter, TestAfterCall) {
    simics::AfterCall ac;

    // Adding nullptr will throw
    EXPECT_PRED_THROW(ac.addIface(nullptr), std::invalid_argument,
                      checkNullAfterCallInterface);

    // Removing nullptr will throw
    EXPECT_PRED_THROW(ac.removeIface(nullptr), std::invalid_argument,
                      checkNullAfterCallInterface);

    // Use empty name to find AfterCallInterface will throw
    EXPECT_PRED_THROW(ac.findIface(""), std::invalid_argument,
                      checkFindWithEmptyName);

    EXPECT_EQ(ac.findIface("TestAfterCall"), nullptr);

    TestAfterCall t {"TestAfterCall"};
    ac.addIface(&t);
    EXPECT_EQ(ac.findIface("TestAfterCall"), &t);

    // Add same interface again is nop
    ac.addIface(&t);
    EXPECT_EQ(ac.findIface("TestAfterCall"), &t);

    ac.removeIface(&t);
    EXPECT_EQ(ac.findIface("TestAfterCall"), nullptr);
}

int test_function_call1_called_count = 0;
void test_function_call1() {
    ++test_function_call1_called_count;
}

TEST(TestAfter, TestFunctionCallNoArgument) {
    simics::FunctionCall<> fc {&test_function_call1, "&test_function_call1"};

    // Test class methods
    std::string expected_name {
        std::string("&test_function_call1") +
        typeid(&test_function_call1).name()
    };
    EXPECT_EQ(fc.name(), expected_name);

    simics::AttrValue attr {fc.get_value()};
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    std::string name = SIM_attr_string(SIM_attr_list_item(attr, 0));
    EXPECT_EQ(name, expected_name);
    auto value = simics::attr_to_std<
        std::pair<std::string, std::tuple<>>>(attr);
    EXPECT_EQ(value, std::make_pair(expected_name, std::make_tuple()));

    fc.set_args(simics::AttrValue(simics::std_to_attr<std::tuple<>>(
                                          std::make_tuple())));
    EXPECT_THROW(fc.set_args(simics::AttrValue(
                                     simics::std_to_attr<std::tuple<int>>(2))),
                 simics::detail::SetIllegalType);

    std::unique_ptr<simics::AfterCallInterface> new_fc {fc.make_copy()};
    EXPECT_EQ(new_fc->name(), expected_name);
    attr = new_fc->get_value();
    value = simics::attr_to_std<
        std::pair<std::string, std::tuple<>>>(attr);
    EXPECT_EQ(value, std::make_pair(expected_name, std::make_tuple()));
}

int test_function_call2_called_arg = 0;
void test_function_call2(int arg) {
    test_function_call2_called_arg = arg;
}

TEST(TestAfter, TestFunctionCallOneIntArgument) {
    simics::FunctionCall<int> fc {&test_function_call2, "&test_function_call2"};

    // Test class methods
    std::string expected_name {
        std::string("&test_function_call2") +
        typeid(&test_function_call2).name()
    };
    EXPECT_EQ(fc.name(), expected_name);

    simics::AttrValue attr {fc.get_value()};
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    std::string name = SIM_attr_string(SIM_attr_list_item(attr, 0));
    EXPECT_EQ(name, expected_name);
    auto value = simics::attr_to_std<
        std::pair<std::string, std::tuple<int>>>(attr);
    EXPECT_EQ(value, std::make_pair(expected_name, std::make_tuple(0)));

    fc.set_args(simics::AttrValue(simics::std_to_attr<std::tuple<int>>(
                                          std::make_tuple(0x1234))));
    EXPECT_THROW(fc.set_args(
                         simics::AttrValue(
                                 simics::std_to_attr<std::tuple<bool>>(true))),
                 simics::detail::SetIllegalType);

    std::unique_ptr<simics::AfterCallInterface> new_fc {fc.make_copy()};
    EXPECT_EQ(new_fc->name(), expected_name);
    attr = new_fc->get_value();
    value = simics::attr_to_std<
        std::pair<std::string, std::tuple<int>>>(attr);
    EXPECT_EQ(value, std::make_pair(expected_name, std::make_tuple(0x1234)));
}

const char *test_function_call3_called_arg {""};
void test_function_call3(std::string arg) {
    test_function_call3_called_arg = arg.c_str();
}

TEST(TestAfter, TestFunctionCallOneStrArgument) {
    simics::FunctionCall<std::string> fc {
        &test_function_call3, "&test_function_call3"};

    // Test class methods
    std::string expected_name {
        std::string("&test_function_call3") +
        typeid(&test_function_call3).name()
    };
    EXPECT_EQ(fc.name(), expected_name);

    simics::AttrValue attr {fc.get_value()};
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    std::string name = SIM_attr_string(SIM_attr_list_item(attr, 0));
    EXPECT_EQ(name, expected_name);
    auto value = simics::attr_to_std<
        std::pair<std::string, std::tuple<std::string>>>(attr);
    EXPECT_EQ(value, std::make_pair(expected_name,
                                    std::make_tuple(std::string(""))));

    fc.set_args(simics::AttrValue(
                        simics::std_to_attr<std::tuple<std::string>>(
                                std::make_tuple(std::string("coffee")))));
    EXPECT_THROW(fc.set_args(
                         simics::AttrValue(
                                 simics::std_to_attr<std::tuple<bool>>(true))),
                 simics::detail::SetIllegalType);

    std::unique_ptr<simics::AfterCallInterface> new_fc {fc.make_copy()};
    EXPECT_EQ(new_fc->name(), expected_name);
    attr = new_fc->get_value();
    value = simics::attr_to_std<
        std::pair<std::string, std::tuple<std::string>>>(attr);
    EXPECT_EQ(value, std::make_pair(expected_name, std::make_tuple(
                                        std::string("coffee"))));
}

std::vector<float> test_function_call4_called_arg1;
int test_function_call4_called_arg2 = 0;
void test_function_call4(std::vector<float> arg1, int arg2) {
    test_function_call4_called_arg1 = arg1;
    test_function_call4_called_arg2 = arg2;
}

TEST(TestAfter, TestFunctionCallTwoArguments) {
    simics::FunctionCall<std::vector<float>, int> fc {
        &test_function_call4, "&test_function_call4"};

    // Test class methods
    std::string expected_name {
        std::string("&test_function_call4") +
        typeid(&test_function_call4).name()
    };
    EXPECT_EQ(fc.name(), expected_name);

    simics::AttrValue attr {fc.get_value()};
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    std::string name = SIM_attr_string(SIM_attr_list_item(attr, 0));
    EXPECT_EQ(name, expected_name);
    auto value = simics::attr_to_std<
        std::pair<std::string, std::tuple<std::vector<float>, int>>>(
            attr);
    EXPECT_EQ(value, std::make_pair(expected_name,
                                    std::make_tuple(std::vector<float>(), 0)));

    std::vector<float> v {1.234f, 5.678f};
    fc.set_args(
            simics::AttrValue(
                    simics::std_to_attr<std::tuple<std::vector<float>, int>>(
                            std::make_tuple(v, 0x1234))));
    EXPECT_THROW(fc.set_args(
                         simics::AttrValue(
                                 simics::std_to_attr<std::tuple<bool>>(true))),
                 simics::detail::SetIllegalType);

    std::unique_ptr<simics::AfterCallInterface> new_fc {fc.make_copy()};
    EXPECT_EQ(new_fc->name(), expected_name);
    attr = new_fc->get_value();
    value = simics::attr_to_std<
        std::pair<std::string, std::tuple<std::vector<float>, int>>>(attr);
    EXPECT_EQ(value, std::make_pair(expected_name,
                                    std::make_tuple(v, 0x1234)));
}

int test_static_member_function_call_count = 0;
int test_member_function_call1_count = 0;
const char *test_member_function_call2_string {""};
class TestMemberFunctionCall : public simics::ConfObject {
  public:
    using ConfObject::ConfObject;

    static void test_static_member_function_call() {
        ++test_static_member_function_call_count;
    }

    void test_member_function_call1() {
        ++test_member_function_call1_count;
    }

    void test_member_function_call2(std::string s) {
        test_member_function_call2_string = s.c_str();
    }
};

TEST(TestAfter, TestStaticMemberFunctionCall) {
    simics::FunctionCall<> fc {
        &TestMemberFunctionCall::test_static_member_function_call,
        "&TestMemberFunctionCall::test_static_member_function_call"
    };

    // Test class methods
    std::string expected_name {
        std::string("&TestMemberFunctionCall::test_static_member_function_call")
        + typeid(&test_function_call1).name()
    };
    EXPECT_EQ(fc.name(), expected_name);

    simics::AttrValue attr {fc.get_value()};
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    std::string name = SIM_attr_string(SIM_attr_list_item(attr, 0));
    EXPECT_EQ(name, expected_name);
    auto value = simics::attr_to_std<
        std::pair<std::string, std::tuple<>>>(attr);
    EXPECT_EQ(value, std::make_pair(expected_name, std::make_tuple()));

    fc.set_args(simics::AttrValue(
                        simics::std_to_attr<std::tuple<>>(std::make_tuple())));
    EXPECT_THROW(fc.set_args(
                         simics::AttrValue(
                                 simics::std_to_attr<std::tuple<int>>(2))),
                 simics::detail::SetIllegalType);

    std::unique_ptr<simics::AfterCallInterface> new_fc {fc.make_copy()};
    EXPECT_EQ(new_fc->name(), expected_name);
    attr = new_fc->get_value();
    value = simics::attr_to_std<
        std::pair<std::string, std::tuple<>>>(attr);
    EXPECT_EQ(value, std::make_pair(expected_name, std::make_tuple()));
}

TEST(TestAfter, TestMemberFunctionCallNoArgument) {
    auto obj = std::make_unique<conf_object_t>();
    TestMemberFunctionCall t {obj.get()};
    Stubs::instance_.sim_object_data_ret_ = &t;

    simics::MemberFunctionCall<TestMemberFunctionCall> mfc {
        &TestMemberFunctionCall::test_member_function_call1,
        "&TestMemberFunctionCall::test_member_function_call1"
    };

    // Test class methods
    std::string expected_name {
        std::string("&TestMemberFunctionCall::test_member_function_call1")
        + typeid(&TestMemberFunctionCall::test_member_function_call1).name()
    };
    EXPECT_EQ(mfc.name(), expected_name);

    simics::AttrValue attr {mfc.get_value()};
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    std::string name = SIM_attr_string(SIM_attr_list_item(attr, 0));
    EXPECT_EQ(name, expected_name);
    auto value = simics::attr_to_std<
        std::pair<std::string,
                  std::tuple<simics::ConfObjectRef>>>(attr);
    EXPECT_EQ(value, std::make_pair(expected_name,
                                    std::make_tuple(
                                        simics::ConfObjectRef(nullptr))));

    mfc.set_args(simics::AttrValue(simics::std_to_attr<
                                   std::tuple<simics::ConfObjectRef>>(
                                           std::make_tuple(t.obj()))));
    EXPECT_THROW(mfc.set_args(simics::AttrValue(
                     simics::std_to_attr<std::tuple<simics::ConfObjectRef,
                                         int>>(std::make_tuple(t.obj(), 2)))),
                 simics::detail::SetIllegalType);

    std::unique_ptr<simics::AfterCallInterface> new_mfc {mfc.make_copy()};
    EXPECT_EQ(new_mfc->name(), expected_name);
    attr = new_mfc->get_value();
    value = simics::attr_to_std<
        std::pair<std::string, std::tuple<simics::ConfObjectRef>>>(attr);
    EXPECT_EQ(value, std::make_pair(expected_name,
                                    std::make_tuple(t.obj())));
}

TEST(TestAfter, TestMemberFunctionCallOneStrArgument) {
    auto obj = std::make_unique<conf_object_t>();
    TestMemberFunctionCall t {obj.get()};
    Stubs::instance_.sim_object_data_ret_ = &t;

    simics::MemberFunctionCall<TestMemberFunctionCall, std::string> mfc {
        &TestMemberFunctionCall::test_member_function_call2,
        "&TestMemberFunctionCall::test_member_function_call2"
    };

    // Test class methods
    std::string expected_name {
        std::string("&TestMemberFunctionCall::test_member_function_call2")
        + typeid(&TestMemberFunctionCall::test_member_function_call2).name()
    };
    EXPECT_EQ(mfc.name(), expected_name);

    simics::AttrValue attr {mfc.get_value()};
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

    std::string test_s {"coffee"};
    mfc.set_args(simics::AttrValue(
                         simics::std_to_attr<
                         std::tuple<simics::ConfObjectRef, std::string>>(
                                 std::make_tuple(t.obj(), test_s))));
    EXPECT_THROW(mfc.set_args(simics::AttrValue(
                    simics::std_to_attr<std::tuple<simics::ConfObjectRef,
                                        int>>(std::make_tuple(t.obj(), 2)))),
                 simics::detail::SetIllegalType);

    std::unique_ptr<simics::AfterCallInterface> new_mfc {mfc.make_copy()};
    EXPECT_EQ(new_mfc->name(), expected_name);
    attr = new_mfc->get_value();
    value = simics::attr_to_std<
        std::pair<std::string, std::tuple<simics::ConfObjectRef,
                                          std::string>>>(attr);
    EXPECT_EQ(value, std::make_pair(expected_name, std::make_tuple(
                                        t.obj(), test_s)));
}

TEST(TestAfter, TestMakeFunctionCall) {
    auto *fc1 = simics::make_function_call(&test_function_call1,
                                           "&test_function_call1");
    static_assert(std::is_same_v<std::decay_t<decltype(fc1)>,
                  simics::FunctionCall<> *>,
                  "Expected a FunctionCall");
    delete fc1;
    auto *fc2 = simics::make_function_call(&test_function_call2,
                                           "&test_function_call2");
    static_assert(std::is_same_v<std::decay_t<decltype(fc2)>,
                  simics::FunctionCall<int> *>,
                  "Expected a FunctionCall");
    delete fc2;
    auto *fc3 = simics::make_function_call(&test_function_call3,
                                           "&test_function_call3");
    static_assert(std::is_same_v<std::decay_t<decltype(fc3)>,
                  simics::FunctionCall<std::string> *>,
                  "Expected a FunctionCall");
    delete fc3;
    auto *fc4 = simics::make_function_call(&test_function_call4,
                                           "&test_function_call4");
    static_assert(std::is_same_v<std::decay_t<decltype(fc4)>,
                  simics::FunctionCall<std::vector<float>, int> *>,
                  "Expected a FunctionCall");
    delete fc4;
    auto *fc5 = simics::make_function_call(
        &TestMemberFunctionCall::test_static_member_function_call,
        "&TestMemberFunctionCall::test_static_member_function_call");
    static_assert(std::is_same_v<std::decay_t<decltype(fc5)>,
                  simics::FunctionCall<> *>,
                  "Expected a FunctionCall");
    delete fc5;
    auto *fc6 = simics::make_function_call(
        &TestMemberFunctionCall::test_member_function_call1,
        "&TestMemberFunctionCall::test_member_function_call1");
    static_assert(std::is_same_v<std::decay_t<decltype(fc6)>,
                  simics::MemberFunctionCall<TestMemberFunctionCall> *>,
                  "Expected a MemberFunctionCall");
    delete fc6;
}

bool checkAfterEventSetValue(const std::exception &ex) {
    EXPECT_STREQ(ex.what(),
                 "Invalid value to restore after event");
    return true;
}

TEST(TestAfter, TestAfterEvent) {
    auto obj = std::make_unique<conf_object_t>();
    MockObject a_conf_object {
        obj.get(), "a_conf_object"
    };
    event_class_t *event_cls {reinterpret_cast<event_class_t *>(0xdead)};
    simics::AfterEvent ae {&a_conf_object, event_cls};

    // Test methods
    TestAfterCall *t = new TestAfterCall("foo");
    EXPECT_EQ(test_after_call_get_value_count, 0);
    ae.get_value(t);
    EXPECT_EQ(test_after_call_get_value_count, 1);

    EXPECT_PRED_THROW(ae.set_value(SIM_make_attr_nil()), std::invalid_argument,
                      checkAfterEventSetValue);
    simics::AttrValue attr1 {simics::std_to_attr<std::tuple<>>(std::tuple<>())};
    EXPECT_PRED_THROW(ae.set_value(attr1), std::invalid_argument,
                      checkAfterEventSetValue);
    simics::AttrValue attr2 {simics::std_to_attr<std::pair<int, int>>({2, 3})};
    EXPECT_PRED_THROW(ae.set_value(attr2), std::invalid_argument,
                      checkAfterEventSetValue);
    simics::AttrValue attr3 {
        simics::std_to_attr<std::pair<std::string, int>>({"2", 3})
    };
    EXPECT_PRED_THROW(ae.set_value(attr3), std::invalid_argument,
                      checkAfterEventSetValue);
    simics::AttrValue attr4 {
        simics::std_to_attr<std::pair<std::string, std::tuple<>>>(
                {"foo", std::tuple<>()})
    };
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, 0);
    ae.set_value(attr4);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Cannot find AfterInterface for function foo");

    simics::AfterCall::addIface(t);
    EXPECT_EQ(test_after_call_set_args_count, 0);
    EXPECT_EQ(ae.set_value(attr4), t);
    EXPECT_EQ(test_after_call_set_args_count, 1);

    EXPECT_EQ(test_after_call_invoke_count, 0);
    ae.callback(t);
    EXPECT_EQ(test_after_call_invoke_count, 1);
    simics::AfterCall::removeIface(t);

    // nop since clock_ is not set yet
    ae.remove();
}

TEST(TestAfter, TestPostSeconds) {
    Stubs::instance_.sim_log_error_cnt_ = 0;

    auto obj = std::make_unique<conf_object_t>();
    MockObject a_conf_object {
        obj.get(), "a_conf_object"
    };
    event_class_t *event_cls {reinterpret_cast<event_class_t *>(0xdead)};
    simics::AfterEvent ae {&a_conf_object, event_cls};

    ae.post(1.0);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Queue not set, unable to post events");

    conf_object_t *a_clock {
        reinterpret_cast<conf_object_t *>(0xdead)
    };
    Stubs::instance_.object_clock_ret_ = a_clock;

    // Simulation that SIM_event_post_time raised a Simics exception
    Stubs::instance_.sim_clear_exception_ret_ = SimExc_General;
    Stubs::instance_.sim_last_error_ret_ = "test last error";
    ae.post(1.0);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, 2);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_, "test last error");
    Stubs::instance_.sim_last_error_ret_ = "";
    Stubs::instance_.sim_clear_exception_ret_ = SimExc_No_Exception;

    Stubs::instance_.event_post_time_seconds_ = 0.0;
    ae.post(1.0);
    EXPECT_EQ(Stubs::instance_.event_post_time_seconds_, 1.0);

    Stubs::instance_.object_clock_ret_ = nullptr;
}

TEST(TestAfter, TestPostCycles) {
    Stubs::instance_.sim_log_error_cnt_ = 0;

    auto obj = std::make_unique<conf_object_t>();
    MockObject a_conf_object {
        obj.get(), "a_conf_object"
    };
    event_class_t *event_cls {reinterpret_cast<event_class_t *>(0xdead)};
    simics::AfterEvent ae {&a_conf_object, event_cls};

    ae.post(static_cast<cycles_t>(1));
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Queue not set, unable to post events");

    conf_object_t *a_clock {
        reinterpret_cast<conf_object_t *>(0xdead)
    };
    Stubs::instance_.object_clock_ret_ = a_clock;

    // Simulation that SIM_event_post_time raised a Simics exception
    Stubs::instance_.sim_clear_exception_ret_ = SimExc_General;
    Stubs::instance_.sim_last_error_ret_ = "test last error";
    ae.post(static_cast<cycles_t>(1));
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, 2);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_, "test last error");
    Stubs::instance_.sim_last_error_ret_ = "";
    Stubs::instance_.sim_clear_exception_ret_ = SimExc_No_Exception;

    Stubs::instance_.event_post_cycle_cycles_ = 0;
    ae.post(static_cast<cycles_t>(2));
    EXPECT_EQ(Stubs::instance_.event_post_cycle_cycles_, 2);
    Stubs::instance_.object_clock_ret_ = nullptr;
}

class TestEnableAfterEvent
    : public simics::ConfObject,
      public simics::EnableAfterCall<TestEnableAfterEvent> {
  public:
    explicit TestEnableAfterEvent(simics::ConfObjectRef obj)
        : ConfObject(obj), EnableAfterCall(this) {}

    void test_member_function_call3(std::vector<int> v) {}
};

TEST(TestAfter, TestEnableAfterEvent) {
    auto ev_info = TestEnableAfterEvent::afterEventInfo();
    EXPECT_EQ(ev_info.name, "after_event");
    EXPECT_EQ(ev_info.flags, Sim_EC_No_Flags);
    EXPECT_EQ(ev_info.ev,
              &simics::EnableAfterCall<TestEnableAfterEvent>::event_cls);

    auto obj = std::make_unique<conf_object_t>();
    simics::EnableAfterCall<TestEnableAfterEvent>::event_cls = \
        reinterpret_cast<event_class_t *>(0xdead);
    TestEnableAfterEvent ev {obj.get()};

    // Test methods
    Stubs::instance_.sim_log_error_cnt_ = 0;
    ev.schedule(1.0, "foo", SIM_make_attr_nil());
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "After call (foo) needs to be registered by REGISTER_AFTER_CALL "
              "or REGISTER_REG_BANK_AFTER_CALL first");

    TestAfterCall t {"test_enable_after_event"};
    simics::AfterCall::addIface(&t);
    EXPECT_EQ(simics::AfterCall::findIface("test_enable_after_event"), &t);
    ev.schedule(1.0, "test_enable_after_event", SIM_make_attr_nil());
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Queue not set, unable to post events");

    conf_object_t *a_clock {
        reinterpret_cast<conf_object_t *>(0xdead)
    };
    Stubs::instance_.object_clock_ret_ = a_clock;

    Stubs::instance_.event_post_time_seconds_ = 0.0;
    ev.schedule(1.0, "test_enable_after_event", SIM_make_attr_nil());
    EXPECT_EQ(Stubs::instance_.event_post_time_seconds_, 1.0);

    Stubs::instance_.event_post_cycle_cycles_ = 0;
    ev.schedule(static_cast<cycles_t>(15), "test_enable_after_event",
                SIM_make_attr_nil());
    EXPECT_EQ(Stubs::instance_.event_post_cycle_cycles_, 15);

    Stubs::instance_.event_cancel_time_obj_ = nullptr;
    ev.cancel_all();
    EXPECT_EQ(Stubs::instance_.event_cancel_time_obj_, obj.get());

    simics::AfterCall::removeIface(&t);
    Stubs::instance_.object_clock_ret_ = nullptr;
}

TEST(TestAfter, TestMacros) {
    std::string expected_name {
        std::string("&test_function_call1") +
        typeid(&test_function_call1).name()
    };
    EXPECT_EQ(simics::AfterCall::findIface(expected_name), nullptr);
    REGISTER_AFTER_CALL(&test_function_call1);
    EXPECT_NE(simics::AfterCall::findIface(expected_name), nullptr);
    auto *iface = simics::AfterCall::findIface(expected_name);
    EXPECT_EQ(iface->name(), expected_name);

    auto obj = std::make_unique<conf_object_t>();
    simics::EnableAfterCall<TestEnableAfterEvent>::event_cls = \
        reinterpret_cast<event_class_t *>(0xdead);
    TestEnableAfterEvent ev {obj.get()};
    conf_object_t *a_clock {
        reinterpret_cast<conf_object_t *>(0xdead)
    };
    Stubs::instance_.object_clock_ret_ = a_clock;

    Stubs::instance_.event_post_time_seconds_ = 0.0;
    AFTER_CALL(&ev, 1.0, &test_function_call1);
    EXPECT_EQ(Stubs::instance_.event_post_time_seconds_, 1.0);
    simics::AfterCall::removeIface(iface);
    // The interface registered in REGISTER_AFTER_CALL should remain valid
    // throughout the entire Simics process. However, to comply with
    // AddressSanitizer, we need to free it here.
    delete iface;

    expected_name = "&TestEnableAfterEvent::test_member_function_call3";
    expected_name += typeid(
        &TestEnableAfterEvent::test_member_function_call3).name();
    EXPECT_EQ(simics::AfterCall::findIface(expected_name), nullptr);
    REGISTER_AFTER_CALL(&TestEnableAfterEvent::test_member_function_call3);
    EXPECT_NE(simics::AfterCall::findIface(expected_name), nullptr);
    iface = simics::AfterCall::findIface(expected_name);
    EXPECT_EQ(iface->name(), expected_name);
    Stubs::instance_.event_post_cycle_cycles_ = 0;
    std::vector<int> arg {1, 2, 3, 4, 5};
    AFTER_CALL(&ev, static_cast<cycles_t>(15),
               &TestEnableAfterEvent::test_member_function_call3,
               ev.obj(), arg);
    EXPECT_EQ(Stubs::instance_.event_post_cycle_cycles_, 15);
    simics::AfterCall::removeIface(iface);
    // See previous comment why free it here
    delete iface;
    Stubs::instance_.object_clock_ret_ = nullptr;
}

void test_function_call5(CountedInt ci) {}

TEST(TestAfter, TestNoExtraCopy) {
    auto obj = std::make_unique<conf_object_t>();
    simics::EnableAfterCall<TestEnableAfterEvent>::event_cls = \
        reinterpret_cast<event_class_t *>(uintptr_t{0xdeadbeef});
    TestEnableAfterEvent ev {obj.get()};
    conf_object_t *a_clock {
        reinterpret_cast<conf_object_t *>(0xdead)
    };
    Stubs::instance_.object_clock_ret_ = a_clock;
    CountedInt::resetCounters();

    CountedInt ci {4};
    AFTER_CALL(&ev, 1.0, &test_function_call5, ci);
    EXPECT_EQ(CountedInt::getCopyConstructorCalls(), 0);
    EXPECT_EQ(CountedInt::getCopyAssignmentCalls(), 0);
}
