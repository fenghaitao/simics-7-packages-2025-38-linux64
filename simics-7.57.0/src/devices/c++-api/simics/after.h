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

#ifndef SIMICS_AFTER_H
#define SIMICS_AFTER_H

#include <iostream>
#include <string>
#include <tuple>
#include <typeinfo>
#include <unordered_set>
#include <utility>

#include "simics/after-interface.h"
#include "simics/attr-value.h"
#include "simics/attribute-traits.h"
#include "simics/event.h"

namespace simics {

/*
 * This class serves as a manager for a collection of interfaces that implement
 * the `AfterCallInterface`. It provides static methods to add, remove,
 * and find interface instances based on their names.
 */
class AfterCall {
  public:
    static void addIface(AfterCallInterface *iface);
    static void removeIface(AfterCallInterface *iface);
    static AfterCallInterface *findIface(const std::string &name);

  private:
    static std::unordered_set<AfterCallInterface*> &getIfaces();
};

// FunctionCall contains information about a callable function, including
// its name, arguments, and a pointer to the function itself.
template<typename... Args>
class FunctionCall : public AfterCallInterface {
  public:
    using FunctionType = void(*)(Args...);

    FunctionCall(FunctionType func, const std::string &name)
        : func_(func),
          name_(name + typeid(func).name()) {}

    std::string name() const override {
        return name_;
    }

    void set_args(const attr_value_t &value) override {
        args_ = attr_to_std<std::tuple<Args...>>(value);
    }

    AfterCallInterface *make_copy() override {
        // The allocated pointer is deleted after the function call is invoked
        return new FunctionCall<Args...>(*this);
    }

    attr_value_t get_value() override {
        return std_to_attr(std::make_pair(name_, args_));
    }

  private:
    // Invokes the stored function with the current arguments
    void invoke() override {
        invoke_impl(std::index_sequence_for<Args...>{});
    }

    // Helper function to unpack the tuple and call the function
    template<std::size_t... I>
    void invoke_impl(std::index_sequence<I...>) {
        func_(std::get<I>(args_)...);
    }

    FunctionType func_;
    std::string name_;
    std::tuple<Args...> args_;
};

// MemberFunctionCall contains information about a class member function,
// including a pointer to the object, the function's name, its arguments,
// and a pointer to the member function itself
template<typename Class, typename... Args>
class MemberFunctionCall : public AfterCallInterface {
  public:
    using MemberFunctionType = void (Class::*)(Args...);

    MemberFunctionCall(MemberFunctionType func, const std::string &name)
        : func_(func), name_(name + typeid(func).name()),
          obj_(nullptr) {}

    std::string name() const override {
        return name_;
    }

    // Sets the arguments for the member function call from a given
    // attribute value.
    // The first element is treated as a reference to the object, and
    // subsequent elements are treated as arguments for the member function
    void set_args(const attr_value_t &value) override {
        auto t = attr_to_std<std::tuple<ConfObjectRef, Args...>>(value);
        obj_ = std::get<0>(t);
        set_args_impl(t, std::index_sequence_for<Args...>{});
    }

    AfterCallInterface *make_copy() override {
        // The allocated pointer is deleted after the function call is invoked
        return new MemberFunctionCall<Class, Args...>(*this);
    }

    attr_value_t get_value() override {
        auto rest = std::tuple_cat(std::make_tuple(obj_), args_);
        return std_to_attr(std::make_pair(name_, rest));
    }

  private:
    void invoke() override {
        if (!obj_) {
            throw std::invalid_argument {
                "Cannot call class member function without class instance"
            };
        }
        invoke_impl(std::index_sequence_for<Args...>{});
    }

    // Helper function to unpack the tuple and call the function
    template<std::size_t... I>
    void invoke_impl(std::index_sequence<I...>) {
        (from_obj<Class>(obj_)->*func_)(std::get<I>(args_)...);
    }

    // Helper function to return a tuple by removing the first item
    template <std::size_t... Is>
    void set_args_impl(const std::tuple<ConfObjectRef, Args...> &input_tuple,
                       std::index_sequence<Is...>) {
        args_ = std::make_tuple(std::get<Is + 1>(input_tuple)...);
    }

    MemberFunctionType func_;
    std::string name_;
    ConfObjectRef obj_;
    std::tuple<Args...> args_;
};

template<typename... Args>
constexpr void check_function_call(void(*func)(Args...)) {}

class BankInterface;
class RegisterInterface;
class FieldInterface;
template<typename Class, typename... Args>
constexpr void check_function_call(void(Class::*func)(Args...)) {
    static_assert(std::is_base_of<ConfObject, Class>::value
                  || std::is_base_of<BankInterface, Class>::value
                  || std::is_base_of<RegisterInterface, Class>::value
                  || std::is_base_of<FieldInterface, Class>::value,
                  "Only class derived of ConfObject/BankInterface/"
                  "RegisterInterface/FieldInterface supports the after call");
}

// Helper function to create a Functional object with deduced types
template<typename... Args>
constexpr auto make_function_call(void(*func)(Args...),
                                  const std::string &name) {
    return new FunctionCall<Args...>(func, name);
}

// Helper function to create a MemberFunctionCall object with deduced types
template<typename Class, typename... Args>
constexpr auto make_function_call(void (Class::*func)(Args...),
                                  const std::string &name) {
    return new MemberFunctionCall<Class, Args...>(func, name);
}

class AfterEvent : public Event {
  public:
    using Event::Event;

    // EventInterface
    void callback(void *data) override;
    attr_value_t get_value(void *data) override;
    void *set_value(attr_value_t value) override;

    void remove(void * = nullptr) const;
    void post(double seconds, void *data = nullptr);
    void post(cycles_t cycles, void *data = nullptr);

  private:
    void checkSetValueFormat(const attr_value_t &value);
};

template <typename T>
class EnableAfterCall : public AfterInterface {
  public:
    explicit EnableAfterCall(ConfObject *obj)
        : obj_(obj), after_event(obj, event_cls) {}

    // return EventInfo that can be used to register the event on class T
    static EventInfo afterEventInfo(const std::string &name = "after_event") {
        return {
            name, Sim_EC_No_Flags, &event_cls,
            EVENT_HELPER(T, after_event, callback),
            EVENT_HELPER(T, after_event, destroy),
            EVENT_HELPER(T, after_event, get_value),
            EVENT_HELPER(T, after_event, set_value),
            EVENT_HELPER(T, after_event, describe)
        };
    }

    // AfterInterface
    void schedule(double seconds, const std::string &name,
                  const attr_value_t &args) override {
        auto *iface = get_iface(name);
        if (iface) {
            iface->set_args(args);
            after_event.post(seconds, iface);
        }
    }
    void schedule(cycles_t cycles, const std::string &name,
                  const attr_value_t &args) override {
        auto *iface = get_iface(name);
        if (iface) {
            iface->set_args(args);
            after_event.post(cycles, iface);
        }
    }
    void cancel_all() override {
        after_event.remove();
    }

    static event_class_t *event_cls;

  protected:
    ConfObject *obj_ {nullptr};
    AfterEvent after_event;

  private:
    // Get AfterCallInterface by name with the arguments configured
    AfterCallInterface *get_iface(const std::string &name) {
        auto *iface = AfterCall::findIface(name);
        if (iface == nullptr) {
            SIM_LOG_ERROR_STR(
                    obj_->obj(), 0,
                    std::string("After call (" + name + ") needs to be "
                                "registered by REGISTER_AFTER_CALL or "
                                "REGISTER_REG_BANK_AFTER_CALL first"));
            return nullptr;
        }
        return iface->make_copy();
    }
};

template <typename T>
event_class_t *EnableAfterCall<T>::event_cls = nullptr;

}  // namespace simics

#define FUNC_AND_NAME(f) f, #f

#define REGISTER_AFTER_CALL(f)                                                \
    simics::AfterCall::addIface(simics::make_function_call(FUNC_AND_NAME(f)));

#define AFTER_CALL(dev, t, f, ...) {                \
    simics::check_function_call(f);                                         \
    auto *iface = dynamic_cast<simics::AfterInterface *>(dev);       \
    if (iface == nullptr) {                                                 \
        std::cerr << "The first argument to the AFTER_CALL does "           \
                  << "not implement AfterInterface*"                        \
                  << std::endl;                                             \
    } else {                                                                \
        iface->schedule(t, std::string(#f) + typeid(f).name(),              \
                        simics::AttrValue(simics::std_to_attr(              \
                                std::forward_as_tuple(__VA_ARGS__))));      \
    }                                                                       \
}
#endif
