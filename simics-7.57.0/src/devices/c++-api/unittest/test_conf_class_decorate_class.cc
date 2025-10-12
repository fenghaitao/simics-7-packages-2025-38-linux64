// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2020 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include <gtest/gtest.h>

// Just some globals modified by the decorator
bool this_decorate_class_called = false;

// Define decorate_class before including conf-class.h
namespace simics {
template <typename T>
void decorate_class(void *, void *cls) {
    this_decorate_class_called = true;
}
}  // simics

#include <simics/conf-class.h>

#include <string>

#include "mock/stubs.h"
#include "mock/mock-object.h"

TEST(TestConfClassDecorateClass, TestMakeClass) {
    this_decorate_class_called = false;
    std::string name { "TestMakeClass_name" };
    std::string short_desc { "TestMakeClass_short_desc" };
    std::string description { "TestMakeClass_description" };
    Stubs::instance_.a_conf_class_ = reinterpret_cast<conf_class_t*>(
            uintptr_t{0xdeadbeef});

    simics::make_class<MockObject>(name, short_desc, description);

    EXPECT_TRUE(this_decorate_class_called);
}
