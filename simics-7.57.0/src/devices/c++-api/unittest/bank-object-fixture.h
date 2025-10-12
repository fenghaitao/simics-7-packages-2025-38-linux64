// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2021 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef UNITTEST_BANK_OBJECT_FIXTURE_H
#define UNITTEST_BANK_OBJECT_FIXTURE_H

#include <simics/mappable-conf-object.h>

#include <array>
#include <memory>
#include <string>

#include "mock/stubs.h"
#include "mock/mock-object.h"

class BankObjectFixture : public ::testing::Test {
  public:
    explicit BankObjectFixture(const std::string &name = "")
        : conf_obj(new conf_object_t),
          name_(name),
          bank_obj(conf_obj.get(), name_),
          map_obj(bank_obj.obj()) {
        Stubs::instance_.sim_port_object_parent_ret_ = conf_obj.get();
        Stubs::instance_.sim_object_descendant_ret_ = conf_obj.get();
        Stubs::instance_.sim_object_data_ret_ = &map_obj;
        Stubs::instance_.sim_get_attribute_ret_ = SIM_alloc_attr_list(5);
        SIM_attr_list_set_item(&Stubs::instance_.sim_get_attribute_ret_, 0,
                               SIM_make_attr_string("Register_Read"));
        SIM_attr_list_set_item(&Stubs::instance_.sim_get_attribute_ret_, 1,
                               SIM_make_attr_string("Register_Write"));
        SIM_attr_list_set_item(&Stubs::instance_.sim_get_attribute_ret_, 2,
                               SIM_make_attr_string("Register_Read_Exception"));
        SIM_attr_list_set_item(&Stubs::instance_.sim_get_attribute_ret_, 3,
                               SIM_make_attr_string(
                                       "Register_Write_Exception"));
        SIM_attr_list_set_item(&Stubs::instance_.sim_get_attribute_ret_, 4,
                               SIM_make_attr_string("Default_Group"));
        reset_register_memory();
        unset_configured();
    }
    virtual ~BankObjectFixture() {
        Stubs::instance_.sim_port_object_parent_ret_ = nullptr;
        Stubs::instance_.sim_object_descendant_ret_ = nullptr;
        Stubs::instance_.sim_object_data_ret_ = nullptr;
        SIM_attr_free(&Stubs::instance_.sim_get_attribute_ret_);
        Stubs::instance_.sim_get_attribute_ret_ = SIM_make_attr_nil();
        reset_register_memory();
        unset_configured();
    }

    void set_configured() {
        Stubs::instance_.sim_object_is_configured_ret_ = true;
    }

    void unset_configured() {
        Stubs::instance_.sim_object_is_configured_ret_ = false;
    }

    void reset_register_memory() {
        bytes_.fill(0);
    }

    // some API like SIM_object_class needs a real conf_object_t
    std::unique_ptr<conf_object_t> conf_obj;

    std::string name_;
    std::array<uint8_t, 8> bytes_;
    simics::register_memory_t pointers_ {
        bytes_.data(), bytes_.data() + 1, bytes_.data() + 2,
        bytes_.data() + 3, bytes_.data() + 4, bytes_.data() + 5,
        bytes_.data() + 6, bytes_.data() + 7
    };
    MockObject bank_obj;
    simics::MappableConfObject map_obj;
};

#endif
