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

#include <simics/connect.h>

#include <gtest/gtest.h>

#include <string>

#include "mock/mock-object.h"
#include "mock/stubs.h"

using simics::Connect;
using simics::ConnectBase;

namespace {
// Simple mock class for ConnectBase
class MockConnectBase : public ConnectBase {
  public:
    bool set(const simics::ConfObjectRef &o) override {
        obj_ = o;
        return true;
    }
};

class FakeInterface1 {
  public:
    using ctype = void;

    class Info {
      public:
        std::string name() { return "fake1"; }
    };

    class ToC {
      public:
        ToC() : obj_(nullptr), iface_(nullptr) {}
        ToC(conf_object_t *obj, const FakeInterface1::ctype *iface)
            : obj_(obj), iface_(iface) {}

        const FakeInterface1::ctype *get_iface() const {
            return iface_;
        }

      private:
        conf_object_t *obj_;
        const FakeInterface1::ctype *iface_;
    };
};

class FakeInterface2 {
  public:
    using ctype = int;

    class Info {
      public:
        std::string name() { return "fake2"; }
    };

    class ToC {
      public:
        ToC() : obj_(nullptr), iface_(nullptr) {}
        ToC(conf_object_t *obj, const FakeInterface2::ctype *iface)
            : obj_(obj), iface_(iface) {}

        const FakeInterface2::ctype *get_iface() const {
            return iface_;
        }

      private:
        conf_object_t *obj_;
        const FakeInterface2::ctype *iface_;
    };
};

/// A class derived from simics::Connect in order to test the protected
/// methods
class TestConnect : public Connect<FakeInterface1> {
  public:
    using Connect<FakeInterface1>::Connect;
    using Connect<FakeInterface1>::dev;
    using Connect<FakeInterface1>::device;
};
}  // namespace

// Test cases for Connect
class ConnectTest : public ::testing::Test {
  protected:
    ConnectTest() {}

    void SetUp() override {
        Stubs::instance_.sim_c_get_port_interface_map_.clear();
        sim_log_info_cnt_ = Stubs::instance_.sim_log_info_cnt_;
    }

    void TearDown() override {
        Stubs::instance_.sim_c_get_port_interface_map_.clear();
        Stubs::instance_.sim_log_info_cnt_ = 0;
    }

    MockObject mock_obj {
        reinterpret_cast<conf_object_t *>(0x1234)
    };
    void *fake_iface1_ {
        reinterpret_cast<void *>(0xdead)
    };
    void *fake_iface2_ {
        reinterpret_cast<void *>(0xbeef)
    };
    size_t sim_log_info_cnt_;
};

TEST(TestConnect, TestConnectGetSet) {
    MockConnectBase connect;
    EXPECT_EQ(connect.get().object(), nullptr);

    simics::ConfObjectRef conf_obj {
        reinterpret_cast<conf_object_t *>(0x1234)
    };
    connect.set(conf_obj);
    EXPECT_EQ(connect.get().object(), conf_obj.object());
}

TEST_F(ConnectTest, TestConnectSingleInterface) {
    Connect<FakeInterface1> obj;
    obj.set(mock_obj.obj());
    // Get interface from nullptr should fail
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, ++sim_log_info_cnt_);

    obj.set(mock_obj.obj());
    // Set to same invalid object again should trigger the info again
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, ++sim_log_info_cnt_);

    Stubs::instance_.sim_c_get_port_interface_map_["fake1"] = fake_iface1_;
    obj.set(mock_obj.obj());
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, sim_log_info_cnt_);
    EXPECT_EQ(obj.get(), mock_obj.obj());
    auto iface = obj.iface().get_iface();
    EXPECT_EQ(iface, fake_iface1_);
}

TEST_F(ConnectTest, TestConnectWithPortName) {
    Connect<FakeInterface1> obj;
    auto target_obj {mock_obj.obj()};
    target_obj.set_port_name("foo");
    Stubs::instance_.sim_c_get_port_interface_map_["foo.fake1"]
        = fake_iface1_;

    obj.set(target_obj);
    EXPECT_EQ(obj.get(), target_obj);
    EXPECT_EQ(obj.iface().get_iface(), fake_iface1_);
}

TEST_F(ConnectTest, TestConnectMultipleInterface) {
    Connect<FakeInterface2, FakeInterface1> obj;
    auto conf_obj {mock_obj.obj()};
    Stubs::instance_.sim_c_get_port_interface_map_["fake1"]
        = fake_iface1_;
    Stubs::instance_.sim_c_get_port_interface_map_["fake2"]
        = fake_iface2_;

    obj.set(conf_obj);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, sim_log_info_cnt_);
    EXPECT_EQ(obj.get(), conf_obj);
    EXPECT_EQ(obj.iface<FakeInterface1>().get_iface(), fake_iface1_);
    EXPECT_EQ(obj.iface<FakeInterface2>().get_iface(), fake_iface2_);

    // Change the interface pointer, check if reset to same conf_obj
    // updates the interface pointer
    sim_log_info_cnt_ = Stubs::instance_.sim_log_info_cnt_;
    simics::ConfObjectRef null_conf_obj { nullptr };

    obj.set(null_conf_obj);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, sim_log_info_cnt_);
    EXPECT_EQ(obj.get(), null_conf_obj);
    EXPECT_EQ(obj.iface<FakeInterface1>().get_iface(), nullptr);
    EXPECT_EQ(obj.iface<FakeInterface2>().get_iface(), nullptr);

    obj.set(conf_obj);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, sim_log_info_cnt_);
    EXPECT_EQ(obj.get(), conf_obj);
    EXPECT_EQ(obj.iface<FakeInterface1>().get_iface(), fake_iface1_);
    EXPECT_EQ(obj.iface<FakeInterface2>().get_iface(), fake_iface2_);
}

TEST_F(ConnectTest, TestConnectOptionalInterface1) {
    Connect<FakeInterface2, FakeInterface1> obj {
        // Mark the FakeInterface2 as optional
        simics::ConnectConfig::optional<FakeInterface2>()
    };

    auto conf_obj {mock_obj.obj()};
    Stubs::instance_.sim_c_get_port_interface_map_["fake1"]
        = fake_iface1_;

    EXPECT_EQ(obj.set(conf_obj), true);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, sim_log_info_cnt_);
    EXPECT_EQ(obj.get(), conf_obj);
    EXPECT_EQ(obj.iface<FakeInterface1>().get_iface(), fake_iface1_);
    // Since optional, it can be nullptr
    EXPECT_EQ(obj.iface<FakeInterface2>().get_iface(), nullptr);
}

TEST_F(ConnectTest, TestConnectOptionalInterface2) {
    Connect<FakeInterface2, FakeInterface1> obj {
        // Mark the FakeInterface1 as optional
        simics::ConnectConfig::optional<FakeInterface1>()
    };

    auto conf_obj {mock_obj.obj()};
    Stubs::instance_.sim_c_get_port_interface_map_["fake1"]
        = fake_iface1_;
    Stubs::instance_.sim_c_get_port_interface_map_["fake2"]
        = fake_iface2_;

    EXPECT_EQ(obj.set(conf_obj), true);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, sim_log_info_cnt_);
    EXPECT_EQ(obj.get(), conf_obj);
    // Optional, but actually contains valid interface
    EXPECT_EQ(obj.iface<FakeInterface1>().get_iface(), fake_iface1_);
    EXPECT_EQ(obj.iface<FakeInterface2>().get_iface(), fake_iface2_);
}

TEST_F(ConnectTest, TestConnectOptionalInterface3) {
    Connect<FakeInterface2, FakeInterface1> obj {
        // Mark all interfaces as optional
        simics::ConnectConfig::optional<FakeInterface1, FakeInterface2>()
    };

    auto conf_obj {mock_obj.obj()};

    EXPECT_EQ(obj.set(conf_obj), true);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, sim_log_info_cnt_);
    EXPECT_EQ(obj.get(), conf_obj);
    EXPECT_EQ(obj.iface<FakeInterface1>().get_iface(), nullptr);
    EXPECT_EQ(obj.iface<FakeInterface2>().get_iface(), nullptr);
}

TEST_F(ConnectTest, TestConnectWithDeviceObj) {
    MockObject device_obj {
        reinterpret_cast<conf_object_t *>(0xc0ffee)
    };

    Connect<FakeInterface1> con1 {device_obj.obj()};
    auto conf_obj {mock_obj.obj()};

    con1.set(conf_obj);
    // Get interface from nullptr should fail
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, ++sim_log_info_cnt_);

    Connect<FakeInterface2, FakeInterface1> con2 {
        device_obj.obj(),
        // Mark all interfaces as optional
        simics::ConnectConfig::optional<FakeInterface1, FakeInterface2>()
    };

    EXPECT_EQ(con2.set(conf_obj), true);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, sim_log_info_cnt_);
}

TEST_F(ConnectTest, TestProtectedMethods) {
    auto obj = mock_obj.obj().object();
    TestConnect connect {mock_obj.obj()};
    EXPECT_EQ(connect.dev(), obj);
    EXPECT_EQ(connect.device(), obj);
}
