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

#ifndef UNITTEST_MOCK_MOCK_REGISTER_H
#define UNITTEST_MOCK_MOCK_REGISTER_H

#include <simics/register-interface.h>

#include <string>
#include <string_view>
#include <vector>

class MockRegister : public simics::RegisterInterface {
  public:
    explicit MockRegister(simics::MappableConfObject *obj,
                          const std::string &name)
        : obj_(obj),
          hierarchical_name_(name),
          name_(name.substr(name.rfind('.') + 1)) {
    }

    std::string_view name() const override {
        return name_;
    }

    const std::string &hierarchical_name() const override {
        return hierarchical_name_;
    }

    const std::string &description() const override {
        return name_;
    }

    simics::MappableConfObject *dev_obj() const override {
        return obj_;
    }

    simics::ConfObjectRef bank_obj_ref() const override {
        return {};
    }

    unsigned number_of_bytes() const override {
        return 0;
    }

    void init(std::string_view desc, unsigned number_of_bytes,
              uint64_t init_val) override {}
    void reset() override {}

    bool is_read_only() const override {
        return false;
    }

    bool is_mapped() const override {
        return is_mapped_;
    }

    void parse_field(const simics::field_t &f) override {}

    void add_field(std::string_view field_name, std::string_view desc,
                   simics::Offset offset, simics::BitWidth width) override {}

    std::vector<simics::field_t> fields_info() const override {
        return {};
    }

    simics::BankInterface *parent() const override {
        return nullptr;
    }

    void set(uint64_t value) override {}
    uint64_t get() const override {
        return 0;
    }
    void write(uint64_t value, uint64_t enabled_bits) override {
    }
    uint64_t read(uint64_t enabled_bits) override {
        return 0;
    }

    void set_byte_pointers(
            const simics::register_memory_t &byte_pointers) override {}

    bool is_mapped_ {true};

  private:
    simics::MappableConfObject *obj_;
    std::string hierarchical_name_;
    std::string name_;
};

#endif
