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

#ifndef UNITTEST_MOCK_MOCK_OBJECT_H
#define UNITTEST_MOCK_MOCK_OBJECT_H

#include <simics/conf-object.h>

#include <string>

#include "stubs.h"

// ConfObjectRef CTOR tries to get the name by SIM_object_name,
// fake it in the stub
class SetName {
  public:
    explicit SetName(conf_object_t *obj, const std::string &name)
        : name_(name) {
        Stubs::instance_.sim_object_name_[obj] = name_.c_str();
    }

  private:
    std::string name_;
};

class MockConfObject : public SetName,
                       public simics::ConfObject {
  public:
    explicit MockConfObject(conf_object_t *obj, const std::string &name)
        : SetName(obj, name),
          simics::ConfObject(obj) {}
};

class MockObject : public MockConfObject {
  public:
    explicit MockObject(conf_object_t *obj, std::string name = "")
        : MockConfObject(obj, name) {
        ++instance_cnt_;
    }

    static void init_class(void *) {
        ++init_class_cnt_;
    }
    static size_t instance_cnt_;
    static size_t init_class_cnt_;
};

class MockObjectWithArg : public MockConfObject {
  public:
    explicit MockObjectWithArg(conf_object_t *obj, void *arg,
                               std::string name = "")
        : MockConfObject(obj, name) {
        ++instance_cnt_;
    }

    static void init_class(void *) {
        ++init_class_cnt_;
    }
    static size_t instance_cnt_;
    static size_t init_class_cnt_;
};

#endif
