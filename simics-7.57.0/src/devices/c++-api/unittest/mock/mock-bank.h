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

#ifndef UNITTEST_MOCK_MOCK_BANK_H
#define UNITTEST_MOCK_MOCK_BANK_H

#include <simics/bank-interface.h>

#include <map>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

class MockBank : public simics::BankInterface {
  public:
    std::string_view name() const override {
        return name_;
    }

    simics::MappableConfObject *dev_obj() const override {
        return dev_obj_;
    }

    const std::string &description() const override {
        return desc_;
    }

    void set_description(std::string_view desc) override {
        desc_ = desc;
    }

    void add_register(const simics::register_t &reg) override {
        std::string hierarchical_name {name()};
        hierarchical_name += '.';
        hierarchical_name += std::get<0>(reg);
        all_registers_.insert(
                {size_t(std::get<2>(reg)),
                 dev_obj_->get_iface<simics::RegisterInterface>(
                         hierarchical_name)});
    }

    void add_register(std::string_view name, std::string_view desc,
                      simics::Offset offset, simics::ByteSize number_of_bytes,
                      simics::InitValue init_value,
                      const std::vector<simics::field_t> &fields) override {
        std::string hierarchical_name {this->name()};
        hierarchical_name += '.';
        hierarchical_name += name;
        all_registers_.insert(
                {offset,
                 dev_obj_->get_iface<simics::RegisterInterface>(
                         hierarchical_name)});
    }

    unsigned number_of_registers() const override {
        return (unsigned)all_registers_.size();
    }

    std::pair<size_t, simics::RegisterInterface *> register_at_index(
            unsigned index) const override {
        auto it = all_registers_.cbegin();
        std::advance(it, index);
        return *it;
    }

    const std::map<size_t, simics::RegisterInterface *> &
    mapped_registers() const override {
        return all_registers_;
    }

    void set_callbacks(
            simics::BankIssueCallbacksInterface *callbacks) override {
        callbacks_ = callbacks;
    }

    simics::ByteOrder get_byte_order() const override {
        return byte_order_;
    }

    void set_miss_pattern(uint8_t miss_pattern) override {
        miss_pattern_ = miss_pattern;
    }

    exception_type_t transaction_access(transaction_t *t,
                                        uint64_t offset) override {
        transaction_access_offset_ = offset;
        return Sim_PE_No_Exception;
    }

    std::string name_;
    std::string desc_;
    simics::MappableConfObject *dev_obj_ {nullptr};
    std::map<size_t, simics::RegisterInterface *> all_registers_;
    simics::BankIssueCallbacksInterface *callbacks_ {nullptr};
    simics::ByteOrder byte_order_ {simics::ByteOrder::BE};
    uint8_t miss_pattern_;
    uint64_t transaction_access_offset_;
};

#endif
