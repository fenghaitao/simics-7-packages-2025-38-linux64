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

#include <simics/port.h>

#include <gtest/gtest.h>
#include <gtest_extensions.h>

#include "mock/mock-object.h"
#include "mock/stubs.h"

class PortTest : public ::testing::Test {
  protected:
    void SetUp() override {
        // Reset the stubs
        Stubs::instance_.sim_port_object_parent_ret_ = nullptr;
        Stubs::instance_.sim_object_data_ret_ = nullptr;
    }

    void TearDown() override {
        // Clean up if necessary
        Stubs::instance_.sim_port_object_parent_ret_ = nullptr;
        Stubs::instance_.sim_object_data_ret_ = nullptr;
    }
};

TEST_F(PortTest, TestPortCreation) {
    // Test that passing a nullptr ConfObjectRef to the Port
    //  constructor throws an exception
    simics::ConfObjectRef null_ref(nullptr);

    EXPECT_THROW(
        {
            try {
                simics::Port<MockObject> port(null_ref);
            } catch (const std::invalid_argument &e) {
                // Verify the exception message
                EXPECT_STREQ(e.what(),
                    "ConfObjectRef passed to Port constructor is null");
                throw;
            }
        },
        std::invalid_argument);

    MockObject port1_obj {
        reinterpret_cast<conf_object_t *>(0xc0ffee), "foo.a_port"
    };
    MockObject parent_obj {
        reinterpret_cast<conf_object_t *>(uintptr_t{0xdeadbeef}),
        "foo"
    };
    Stubs::instance_.sim_port_object_parent_ret_ = parent_obj.obj().object();
    Stubs::instance_.sim_object_data_ret_ = port1_obj.obj().object();
    simics::Port<MockObject> port1 {port1_obj.obj()};

    EXPECT_TRUE((std::is_same<simics::Port<MockObject>::ParentType,
                              MockObject>::value));
    EXPECT_EQ(port1.parent(),
              static_cast<MockObject*>(&parent_obj.obj().as_conf_object()));
    EXPECT_EQ(port1.index(), -1);
    EXPECT_EQ(port1.name(), "a_port");

    // Test valid array-like name
    MockObject port2_obj {
        reinterpret_cast<conf_object_t *>(0xc0ffee), "foo.array[2]"
    };
    Stubs::instance_.sim_object_data_ret_ = port2_obj.obj().object();
    simics::Port<MockObject> port2 {port2_obj.obj()};

    EXPECT_EQ(port2.parent(),
              static_cast<MockObject*>(&parent_obj.obj().as_conf_object()));
    EXPECT_EQ(port2.index(), 2);
    EXPECT_EQ(port2.name(), "array[2]");

    // Test invalid formats
    MockObject port3_obj {
        reinterpret_cast<conf_object_t *>(0xc0ffee), "foo.a_port_array[c]"
    };
    simics::Port<MockObject> port3 {port3_obj.obj()};
    EXPECT_EQ(port3.index(), -1);

    MockObject port4_obj {
        reinterpret_cast<conf_object_t *>(0xc0ffee), "foo.a_port_array[5]["
    };
    simics::Port<MockObject> port4 {port4_obj.obj()};
    EXPECT_EQ(port4.index(), -1);

    MockObject port5_obj {
        reinterpret_cast<conf_object_t *>(0xc0ffee), "foo.a_port_array[-2]"
    };
    simics::Port<MockObject> port5 {port5_obj.obj()};
    EXPECT_EQ(port5.index(), -1);

    // Multi-array for port is not supported
    MockObject port6_obj {
        reinterpret_cast<conf_object_t *>(0xc0ffee),
            "foo.a_port_multiarray[2][2]"
    };
    simics::Port<MockObject> port6 {port6_obj.obj()};
    EXPECT_EQ(port6.index(), -1);

    // For port has no need to access the parent class members,
    // it can use ConfObject as TParent
    simics::Port<simics::ConfObject> port7 {port1_obj.obj()};
    EXPECT_EQ(port7.parent(),
              static_cast<simics::ConfObject *>(port1.parent()));
}

bool checkNotPort(const std::runtime_error &ex) {
    EXPECT_STREQ(ex.what(), "The object invalid_port is not a port object");
    return true;
}

TEST_F(PortTest, TestInvalidPort) {
    MockObject invalid_port_obj {
        reinterpret_cast<conf_object_t *>(0xc0ffee), "invalid_port"
    };
    Stubs::instance_.sim_object_data_ret_ = invalid_port_obj.obj().object();

    EXPECT_PRED_THROW(
        simics::Port<MockObject> invalid_port {invalid_port_obj.obj()},
        std::runtime_error, checkNotPort);
}
