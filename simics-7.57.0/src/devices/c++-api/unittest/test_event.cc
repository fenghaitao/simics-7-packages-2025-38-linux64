// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2023 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include <simics/event.h>

#include <gtest/gtest.h>

#include <memory>

#include "mock/gtest_extensions.h"  // EXPECT_PRED_THROW
#include "mock/mock-object.h"
#include "mock/stubs.h"

bool checkEmptyEventName(const std::exception &ex) {
    EXPECT_STREQ(ex.what(), "Event name cannot be empty");
    return true;
}

bool checkEmptyEventClass(const std::exception &ex) {
    EXPECT_STREQ(ex.what(),
                 "Pointer of event class pointer for event ev is missing");
    return true;
}

bool checkNullCallback(const std::exception &ex) {
    EXPECT_STREQ(ex.what(), "Callback function for event ev is missing");
    return true;
}

bool checkECNotSaved(const std::exception &ex) {
    EXPECT_STREQ(ex.what(),
                 "Event 'ev' with Sim_EC_Notsaved flag must not have get_value"
                 " or set_value callbacks");
    return true;
}

class EventTest : public ::testing::Test {
  public:
    static void callback(conf_object_t *, lang_void *) {
        ++callback_cnt;
    }
    static void destroy(conf_object_t *, lang_void *) {
        ++destroy_cnt;
    }
    static attr_value_t get_value(conf_object_t *obj,
                                  lang_void *data) {
        ++get_value_cnt;
        return SIM_make_attr_nil();
    }
    static lang_void *set_value(conf_object_t *obj,
                                attr_value_t value) {
        ++set_value_cnt;
        return nullptr;
    }
    static char *describe(conf_object_t *obj, lang_void *data) {
        return nullptr;
    }

    void SetUp() override {
        Stubs::instance_.object_clock_ret_ = a_clock;
        Stubs::instance_.event_post_time_evclass_ = nullptr;
        Stubs::instance_.event_post_time_obj_ = nullptr;
        Stubs::instance_.event_post_time_seconds_ = 0.0;
        Stubs::instance_.event_post_time_user_data_ = nullptr;
        Stubs::instance_.event_cancel_step_evclass_ = nullptr;
        Stubs::instance_.event_cancel_step_obj_ = nullptr;
        Stubs::instance_.event_cancel_step_data_ = nullptr;
        Stubs::instance_.event_cancel_time_evclass_ = nullptr;
        Stubs::instance_.event_cancel_time_obj_ = nullptr;
        Stubs::instance_.event_cancel_time_data_ = nullptr;
        Stubs::instance_.event_post_cycle_evclass_ = nullptr;
        Stubs::instance_.event_post_cycle_obj_ = nullptr;
        Stubs::instance_.event_post_cycle_cycles_ = 0;
        Stubs::instance_.event_post_cycle_user_data_ = nullptr;
        Stubs::instance_.event_post_step_evclass_ = nullptr;
        Stubs::instance_.event_post_step_obj_ = nullptr;
        Stubs::instance_.event_post_step_steps_ = 0;
        Stubs::instance_.event_post_step_user_data_ = nullptr;
    }
    void TearDown() override {
        Stubs::instance_.object_clock_ret_ = nullptr;
        Stubs::instance_.event_post_time_evclass_ = nullptr;
        Stubs::instance_.event_post_time_obj_ = nullptr;
        Stubs::instance_.event_post_time_seconds_ = 0.0;
        Stubs::instance_.event_post_time_user_data_ = nullptr;
        Stubs::instance_.event_cancel_step_evclass_ = nullptr;
        Stubs::instance_.event_cancel_step_obj_ = nullptr;
        Stubs::instance_.event_cancel_step_data_ = nullptr;
        Stubs::instance_.event_cancel_time_evclass_ = nullptr;
        Stubs::instance_.event_cancel_time_obj_ = nullptr;
        Stubs::instance_.event_cancel_time_data_ = nullptr;
        Stubs::instance_.event_post_cycle_evclass_ = nullptr;
        Stubs::instance_.event_post_cycle_obj_ = nullptr;
        Stubs::instance_.event_post_cycle_cycles_ = 0;
        Stubs::instance_.event_post_cycle_user_data_ = nullptr;
        Stubs::instance_.event_post_step_evclass_ = nullptr;
        Stubs::instance_.event_post_step_obj_ = nullptr;
        Stubs::instance_.event_post_step_steps_ = 0;
        Stubs::instance_.event_post_step_user_data_ = nullptr;
        delete an_event;
    }

    static int callback_cnt;
    static int destroy_cnt;
    static int get_value_cnt;
    static int set_value_cnt;
    event_class_flag_t flags {Sim_EC_No_Flags};
    conf_object_t *a_clock {
        reinterpret_cast<conf_object_t *>(0xdead)
    };
    std::unique_ptr<conf_object_t> an_object {
        new conf_object_t
    };
    MockObject a_conf_object {
        an_object.get(), "a_conf_object"
    };
    event_class_t *an_event {
        new event_class_t
    };
};

int EventTest::callback_cnt = 0;
int EventTest::destroy_cnt = 0;
int EventTest::get_value_cnt = 0;
int EventTest::set_value_cnt = 0;

TEST_F(EventTest, TestEventInfo) {
    // Empty name
    EXPECT_PRED_THROW(simics::EventInfo("", flags, &an_event, callback, destroy,
                                        get_value, set_value, nullptr),
                      std::invalid_argument, checkEmptyEventName);

    // Null callback
    EXPECT_PRED_THROW(simics::EventInfo("ev", flags, &an_event, nullptr,
                                        destroy, nullptr, nullptr, nullptr),
                      std::invalid_argument, checkNullCallback);

    // Should throw if get_value is not null
    EXPECT_PRED_THROW(
        simics::EventInfo("ev", Sim_EC_Notsaved, &an_event, callback, destroy,
                          get_value, nullptr, describe),
        std::invalid_argument, checkECNotSaved);

    // Should throw if set_value is not null
    EXPECT_PRED_THROW(
        simics::EventInfo("ev", Sim_EC_Notsaved, &an_event, callback, destroy,
                          nullptr, set_value, describe),
        std::invalid_argument, checkECNotSaved);

    // Should throw if both are not null
    EXPECT_PRED_THROW(
        simics::EventInfo("ev", Sim_EC_Notsaved, &an_event, callback, destroy,
                          get_value, set_value, describe),
        std::invalid_argument, checkECNotSaved);

    // Should NOT throw if both are null
    EXPECT_NO_THROW(
        simics::EventInfo("ev", Sim_EC_Notsaved, &an_event, callback, destroy,
                          nullptr, nullptr, describe));

    auto ev = simics::EventInfo("ev", flags, &an_event, callback, destroy,
                                get_value, set_value, describe);

    EXPECT_EQ(ev.name, "ev");
    EXPECT_EQ(ev.flags, flags);
    EXPECT_EQ(ev.ev, &an_event);
    EXPECT_EQ(ev.callback, callback);
    EXPECT_EQ(ev.destroy, destroy);
    EXPECT_EQ(ev.get_value, get_value);
    EXPECT_EQ(ev.set_value, set_value);
    EXPECT_EQ(ev.describe, describe);

    ev = simics::EventInfo("ev", &an_event, callback);

    EXPECT_EQ(ev.name, "ev");
    EXPECT_EQ(ev.flags, Sim_EC_No_Flags);
    EXPECT_EQ(ev.ev, &an_event);
    EXPECT_EQ(ev.callback, callback);
    EXPECT_EQ(ev.destroy, nullptr);
    EXPECT_EQ(ev.get_value, nullptr);
    EXPECT_EQ(ev.set_value, nullptr);
    EXPECT_EQ(ev.describe, nullptr);
}

bool checkNullObject(const std::exception &ex) {
    EXPECT_STREQ(ex.what(), "Device object can't be NULL");
    return true;
}

// Simplest event with only a callback
class SimpleEvent : public simics::Event {
  public:
    using Event::Event;
    using Event::name;

    // Event
    void callback(void *data) override {
        ++callback_count_;
        callback_data_ = data;
    }

    int callback_count_ {0};
    void *callback_data_ {nullptr};
};

bool checkNullEventClass(const std::exception &ex) {
    EXPECT_STREQ(ex.what(),
                 "Event is not registered yet. Call add() from the"
                 " device class");
    return true;
}

bool checkEventRegistered(const std::exception &ex) {
    EXPECT_STREQ(ex.what(), "Event 'ev' is not registered");
    return true;
}

TEST_F(EventTest, TestSimpleEvent) {
    // Null ConfObject *
    EXPECT_PRED_THROW(SimpleEvent(nullptr, nullptr),
                      std::invalid_argument, checkNullObject);

    // Null ev_class_t *
    EXPECT_PRED_THROW(SimpleEvent(&a_conf_object, nullptr),
                      std::invalid_argument, checkNullEventClass);

    // Empty event name
    EXPECT_PRED_THROW(SimpleEvent(&a_conf_object, ""),
                      std::invalid_argument, checkEmptyEventName);

    // Null ConfObject *
    EXPECT_PRED_THROW(SimpleEvent(nullptr, "ev"),
                      std::invalid_argument, checkNullObject);

    auto ev = SimpleEvent(&a_conf_object, an_event);

    EXPECT_EQ(ev, an_event);
    void *test_data = reinterpret_cast<void *>(0xdead);
    ev.callback(test_data);

    EXPECT_EQ(ev.callback_count_, 1);
    EXPECT_EQ(ev.callback_data_, test_data);
    // Test the default implementation of other event methods
    ev.destroy(nullptr);
    EXPECT_EQ(SIM_attr_is_nil(ev.get_value(nullptr)), true);
    EXPECT_EQ(ev.set_value(SIM_make_attr_nil()), nullptr);
    EXPECT_EQ(ev.describe(nullptr), nullptr);
    EXPECT_EQ(ev.name(), an_event->name);

    EXPECT_PRED_THROW(SimpleEvent(&a_conf_object, "ev"),
                      std::invalid_argument, checkEventRegistered);

    Stubs::instance_.sim_get_event_class_ret_ = an_event;
    ev = SimpleEvent(&a_conf_object, "ev");

    EXPECT_EQ(ev, an_event);
    ev.callback(test_data);
    EXPECT_EQ(ev.callback_count_, 1);
    EXPECT_EQ(ev.callback_data_, test_data);
    EXPECT_EQ(ev.name(), an_event->name);
}

// Override all methods
class CompleteEvent : public SimpleEvent {
  public:
    using SimpleEvent::SimpleEvent;

    // SimpleEvent
    void destroy(void *data) override {}
    attr_value_t get_value(void *data) override {
        return SIM_make_attr_nil();
    }
    void *set_value(attr_value_t value) override {
        return nullptr;
    }
    char *describe(void *data) const override {
        return test_describe_;
    }

    // Test protected pointer_eq
    bool test_pointer_eq(void *a, void *b) const {
        return Event::pointer_eq(a, b);
    }

    // Test protected device_ptr
    template<typename T>
    T* test_device_ptr() {
        return device_ptr<T>();
    }

    char *test_describe_ {reinterpret_cast<char *>(0x9876)};
};

TEST_F(EventTest, TestCompleteEvent) {
    auto ev = CompleteEvent(&a_conf_object, an_event);

    EXPECT_EQ(ev, an_event);
    void *test_data = reinterpret_cast<void *>(0xdead);
    ev.callback(test_data);

    EXPECT_EQ(ev.callback_count_, 1);
    EXPECT_EQ(ev.callback_data_, test_data);

    // Test the overridden implementation of other event methods
    ev.destroy(nullptr);
    EXPECT_EQ(SIM_attr_is_nil(ev.get_value(nullptr)), true);
    EXPECT_EQ(ev.set_value(SIM_make_attr_nil()), nullptr);
    EXPECT_EQ(ev.describe(nullptr), reinterpret_cast<char *>(0x9876));

    // Test protected methods in Event class
    EXPECT_EQ(ev.test_pointer_eq(reinterpret_cast<void *>(0xbeef),
                                 reinterpret_cast<void *>(0xbeef)), true);
    EXPECT_EQ(ev.test_pointer_eq(reinterpret_cast<void *>(0xbeef),
                                 reinterpret_cast<void *>(0xdead)), false);
    EXPECT_EQ(ev.test_device_ptr<MockObject>(), &a_conf_object);
}

class SimpleTimeEvent : public simics::TimeEvent<> {
  public:
    using TimeEvent::TimeEvent;

    // Event
    void callback(void *data) override {
    }
};

TEST_F(EventTest, TestSimpleTimeEvent) {
    auto ev = SimpleTimeEvent(&a_conf_object, an_event);

    // When no queue is specified
    Stubs::instance_.object_clock_ret_ = nullptr;
    auto log_error_count_before = Stubs::instance_.sim_log_error_cnt_;
    ev.post(1);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
              log_error_count_before + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Queue not set, unable to post events");

    Stubs::instance_.object_clock_ret_ = a_clock;
    void *data = reinterpret_cast<void *>(0xdead);
    // No clock is setup yet
    EXPECT_EQ(ev.posted(), false);
    EXPECT_EQ(ev.posted(nullptr), false);
    EXPECT_EQ(ev.posted(data), false);
    EXPECT_EQ(ev.next(), -1.0);
    EXPECT_EQ(ev.next(nullptr), -1.0);
    EXPECT_EQ(ev.next(data), -1.0);

    EXPECT_EQ(Stubs::instance_.event_cancel_time_evclass_, nullptr);
    EXPECT_EQ(Stubs::instance_.event_cancel_time_obj_, nullptr);
    EXPECT_EQ(Stubs::instance_.event_cancel_time_data_, nullptr);
    // Remove the event is a nop
    ev.remove(data);
    EXPECT_EQ(Stubs::instance_.event_cancel_time_evclass_, nullptr);
    EXPECT_EQ(Stubs::instance_.event_cancel_time_obj_, nullptr);
    EXPECT_EQ(Stubs::instance_.event_cancel_time_data_, nullptr);

    EXPECT_EQ(Stubs::instance_.event_post_time_evclass_, nullptr);
    EXPECT_EQ(Stubs::instance_.event_post_time_obj_, nullptr);
    EXPECT_EQ(Stubs::instance_.event_post_time_seconds_, 0.0);
    EXPECT_EQ(Stubs::instance_.event_post_time_user_data_, nullptr);
    // Post the event will set the clock
    ev.post(0.5, data);
    EXPECT_EQ(Stubs::instance_.event_post_time_evclass_, an_event);
    EXPECT_EQ(Stubs::instance_.event_post_time_obj_, an_object.get());
    EXPECT_EQ(Stubs::instance_.event_post_time_seconds_, 0.5);
    EXPECT_EQ(Stubs::instance_.event_post_time_user_data_, data);

    ev.remove(data);
    EXPECT_EQ(Stubs::instance_.event_cancel_time_evclass_, an_event);
    EXPECT_EQ(Stubs::instance_.event_cancel_time_obj_, an_object.get());
    EXPECT_EQ(Stubs::instance_.event_cancel_time_data_, data);

    // Post again without data
    ev.post(500.0);
    EXPECT_EQ(Stubs::instance_.event_post_time_seconds_, 500.0);
    EXPECT_EQ(Stubs::instance_.event_post_time_user_data_, nullptr);
}

class SimpleCycleEvent : public simics::CycleEvent<> {
  public:
    using CycleEvent::CycleEvent;

    // Event
    void callback(void *data) override {
    }
};

TEST_F(EventTest, TestSimpleCycleEvent) {
    auto ev = SimpleCycleEvent(&a_conf_object, an_event);

    void *data = reinterpret_cast<void *>(0xdead);
    // No clock is setup yet
    EXPECT_EQ(ev.posted(), false);
    EXPECT_EQ(ev.posted(nullptr), false);
    EXPECT_EQ(ev.posted(data), false);
    EXPECT_EQ(ev.next(), -1.0);
    EXPECT_EQ(ev.next(nullptr), -1.0);
    EXPECT_EQ(ev.next(data), -1.0);

    EXPECT_EQ(Stubs::instance_.event_cancel_time_evclass_, nullptr);
    EXPECT_EQ(Stubs::instance_.event_cancel_time_obj_, nullptr);
    EXPECT_EQ(Stubs::instance_.event_cancel_time_data_, nullptr);
    // Remove the event is a nop
    ev.remove(data);
    EXPECT_EQ(Stubs::instance_.event_cancel_time_evclass_, nullptr);
    EXPECT_EQ(Stubs::instance_.event_cancel_time_obj_, nullptr);
    EXPECT_EQ(Stubs::instance_.event_cancel_time_data_, nullptr);

    EXPECT_EQ(Stubs::instance_.event_post_cycle_evclass_, nullptr);
    EXPECT_EQ(Stubs::instance_.event_post_cycle_obj_, nullptr);
    EXPECT_EQ(Stubs::instance_.event_post_cycle_cycles_, 0);
    EXPECT_EQ(Stubs::instance_.event_post_cycle_user_data_, nullptr);
    // Post the event will set the clock
    ev.post(0, data);
    EXPECT_EQ(Stubs::instance_.event_post_cycle_evclass_, an_event);
    EXPECT_EQ(Stubs::instance_.event_post_cycle_obj_, an_object.get());
    EXPECT_EQ(Stubs::instance_.event_post_cycle_cycles_, 0);
    EXPECT_EQ(Stubs::instance_.event_post_cycle_user_data_, data);

    ev.remove(data);
    EXPECT_EQ(Stubs::instance_.event_cancel_time_evclass_, an_event);
    EXPECT_EQ(Stubs::instance_.event_cancel_time_obj_, an_object.get());
    EXPECT_EQ(Stubs::instance_.event_cancel_time_data_, data);

    // Post again without data
    ev.post(500);
    EXPECT_EQ(Stubs::instance_.event_post_cycle_cycles_, 500);
    EXPECT_EQ(Stubs::instance_.event_post_cycle_user_data_, nullptr);
}

class SimpleStepEvent : public simics::StepEvent<> {
  public:
    using StepEvent::StepEvent;

    // Event
    void callback(void *data) override {
    }
};

TEST_F(EventTest, TestSimpleStepEvent) {
    auto ev = SimpleStepEvent(&a_conf_object, an_event);

    void *data = reinterpret_cast<void *>(0xdead);
    // No clock is setup yet
    EXPECT_EQ(ev.posted(), false);
    EXPECT_EQ(ev.posted(nullptr), false);
    EXPECT_EQ(ev.posted(data), false);
    EXPECT_EQ(ev.next(), -1.0);
    EXPECT_EQ(ev.next(nullptr), -1.0);
    EXPECT_EQ(ev.next(data), -1.0);

    EXPECT_EQ(Stubs::instance_.event_cancel_step_evclass_, nullptr);
    EXPECT_EQ(Stubs::instance_.event_cancel_step_obj_, nullptr);
    EXPECT_EQ(Stubs::instance_.event_cancel_step_data_, nullptr);
    // Remove the event is a nop
    ev.remove(data);
    EXPECT_EQ(Stubs::instance_.event_cancel_step_evclass_, nullptr);
    EXPECT_EQ(Stubs::instance_.event_cancel_step_obj_, nullptr);
    EXPECT_EQ(Stubs::instance_.event_cancel_step_data_, nullptr);

    EXPECT_EQ(Stubs::instance_.event_post_step_evclass_, nullptr);
    EXPECT_EQ(Stubs::instance_.event_post_step_obj_, nullptr);
    EXPECT_EQ(Stubs::instance_.event_post_step_steps_, 0);
    EXPECT_EQ(Stubs::instance_.event_post_step_user_data_, nullptr);
    // Post the event will set the clock
    ev.post(0, data);
    EXPECT_EQ(Stubs::instance_.event_post_step_evclass_, an_event);
    EXPECT_EQ(Stubs::instance_.event_post_step_obj_, an_object.get());
    EXPECT_EQ(Stubs::instance_.event_post_step_steps_, 0);
    EXPECT_EQ(Stubs::instance_.event_post_step_user_data_, data);

    ev.remove(data);
    EXPECT_EQ(Stubs::instance_.event_cancel_step_evclass_, an_event);
    EXPECT_EQ(Stubs::instance_.event_cancel_step_obj_, an_object.get());
    EXPECT_EQ(Stubs::instance_.event_cancel_step_data_, data);

    // Post again without data
    ev.post(500);
    EXPECT_EQ(Stubs::instance_.event_post_step_steps_, 500);
    EXPECT_EQ(Stubs::instance_.event_post_step_user_data_, nullptr);
}
