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

// Register bank extension for after feature

#ifndef SIMICS_AFTER_BANK_H
#define SIMICS_AFTER_BANK_H

#include <string>
#include <tuple>
#include <utility>

#include "simics/after.h"
#include "simics/after-interface.h"
#include "simics/bank-interface.h"
#include "simics/field-interface.h"
#include "simics/hierarchical-object.h"
#include "simics/mappable-conf-object.h"
#include "simics/register-interface.h"

namespace simics {

// RegBankFunctionCall contains class member function for bank/register/field
// information like object name, function name, arguments and the function
// pointer
template<typename Class, typename... Args>
class RegBankFunctionCall : public AfterCallInterface {
  public:
    using RegBankFunctionType = void (Class::*)(Args...);

    RegBankFunctionCall(RegBankFunctionType func, const std::string &name)
        : func_(func), name_(name + typeid(func).name()),
          obj_(nullptr), dev_obj_(nullptr), hierarchical_object_name_("") {}

    std::string name() const override {
        return name_;
    }

    void set_args(const attr_value_t &value) override {
        auto t = attr_to_std<std::tuple<
            ConfObjectRef, std::string, Args...>>(value);
        dev_obj_ = std::get<0>(t);
        hierarchical_object_name_ = std::get<1>(t);
        set_args_impl(t, std::index_sequence_for<Args...>{});
    }

    AfterCallInterface *make_copy() override {
        // The allocated pointer is deleted after the function call is invoked
        return new RegBankFunctionCall<Class, Args...>(*this);
    }

    attr_value_t get_value() override {
        auto rest = std::tuple_cat(
                std::make_tuple(dev_obj_, hierarchical_object_name_),
                args_);
        return std_to_attr(std::make_pair(name_, rest));
    }

  private:
    void invoke() override {
        auto level = static_cast<Level>(
                HierarchicalObject::level_of_hierarchical_name(
                        hierarchical_object_name_));
        auto *dev = from_obj<MappableConfObject>(dev_obj_);
        switch (level) {
        case Level::BANK:
            obj_ = dynamic_cast<Class *>(dev->get_iface<BankInterface>(
                                                 hierarchical_object_name_));
            break;
        case Level::REGISTER:
            obj_ = dynamic_cast<Class *>(dev->get_iface<RegisterInterface>(
                                                 hierarchical_object_name_));
            break;
        case Level::FIELD:
            obj_ = dynamic_cast<Class *>(dev->get_iface<FieldInterface>(
                                                 hierarchical_object_name_));
            break;
        default:
            SIM_LOG_ERROR(dev_obj_, 0,
                          "%s is not a valid hierarchical object name",
                          hierarchical_object_name_.c_str());
        }
        invoke_impl(std::index_sequence_for<Args...>{});
    }

    // Helper function to unpack the tuple and call the function
    template<std::size_t... I>
    void invoke_impl(std::index_sequence<I...>) {
        (obj_->*func_)(std::get<I>(args_)...);
    }

    // Helper function to return a tuple by removing the first item
    template <std::size_t... Is>
    void set_args_impl(const std::tuple<ConfObjectRef, std::string,
                                        Args...>& input_tuple,
                       std::index_sequence<Is...>) {
        args_ = std::make_tuple(std::get<Is + 2>(input_tuple)...);
    }

    RegBankFunctionType func_;
    std::string name_;
    Class *obj_ {nullptr};
    ConfObjectRef dev_obj_;
    std::string hierarchical_object_name_;
    std::tuple<Args...> args_;
};


// Helper function to create a RegBankFunctionCall object with deduced types
template<typename Class, typename... Args>
constexpr auto make_reg_bank_function_call(void (Class::*func)(Args...),
                                           const std::string &name) {
    return new RegBankFunctionCall<Class, Args...>(func, name);
}

}  // namespace simics

#define REGISTER_REG_BANK_AFTER_CALL(f)                                \
    simics::AfterCall::addIface(simics::make_reg_bank_function_call(   \
                                        FUNC_AND_NAME(f)));


#endif
