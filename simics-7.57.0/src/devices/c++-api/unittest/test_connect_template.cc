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

#include <simics/connect-templates.h>

#include <gtest/gtest.h>

#include <string>
#include <vector>

#include "mock/gtest_extensions.h"  // EXPECT_PRED_THROW
#include "mock/mock-object.h"
#include "mock/stubs.h"

namespace {
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
}  // namespace

// Test cases for Connect
class ConnectTemplateTest : public ::testing::Test {
  protected:
    ConnectTemplateTest() {}

    void SetUp() override {
        Stubs::instance_.sim_c_get_port_interface_map_.clear();
        sim_log_info_cnt_ = Stubs::instance_.sim_log_info_cnt_;
        sim_log_critical_cnt_ = Stubs::instance_.sim_log_critical_cnt_;
    }

    void TearDown() override {
        Stubs::instance_.sim_c_get_port_interface_map_.clear();
        Stubs::instance_.sim_log_info_cnt_ = 0;
        Stubs::instance_.sim_log_critical_cnt_ = 0;
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
    size_t sim_log_critical_cnt_;
};

TEST_F(ConnectTemplateTest, TestConnectToDescendant) {
    Stubs::instance_.sim_c_get_port_interface_map_["fake1"]
        = fake_iface1_;
    MockObject device_obj {
        new conf_object_t
    };

    simics::ConnectToDescendant<FakeInterface1> con1 {
        &device_obj,
        "port.test_descendant"
    };
    // Port is not registered yet
    EXPECT_EQ(Stubs::instance_.sim_log_critical_cnt_, ++sim_log_critical_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_critical_,
                      "Port port.test_descendant is not registered yet");

    Stubs::instance_.sim_class_port_ret_ = reinterpret_cast<conf_class_t *>(
            0xc0ffee);
    simics::ConnectToDescendant<FakeInterface1> con2 {
        &device_obj,
        "port.test_descendant"
    };
    // Port object not found
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, ++sim_log_info_cnt_);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
                      "Descendant object port.test_descendant not found");

    Stubs::instance_.sim_object_descendant_ret_ = reinterpret_cast<
        conf_object_t *>(0xdead);
    simics::ConnectToDescendant<FakeInterface1> con3 {
        &device_obj,
        "port.test_descendant"
    };
    EXPECT_EQ(con3.get().object(), Stubs::instance_.sim_object_descendant_ret_);

    delete device_obj.obj();
}

bool checkError(const std::exception &ex) {
    EXPECT_STREQ(ex.what(), "Interface not found");
    return true;
}

TEST(TestConnectTemplate, TestMapTarget) {
    MockConfObject device {reinterpret_cast<conf_object_t *>(0xc0ffee), "dev"};
    Stubs::instance_.sim_object_name_[device.obj().object()] = "dev";

    // test CTOR & DTOR of MapTarget
    auto free_target_cnt_before = Stubs::instance_.sim_free_map_target_cnt_;
    {
        simics::MapTarget mt{device.obj()};
        EXPECT_EQ(mt.map_target(), nullptr);
    }
    EXPECT_EQ(Stubs::instance_.sim_free_map_target_cnt_,
              ++free_target_cnt_before);

    simics::MapTarget mt{device.obj()};

    auto log_info_cnt_before = Stubs::instance_.sim_log_info_cnt_;
    auto log_error_cnt_before = Stubs::instance_.sim_log_error_cnt_;

    // map_target is not set
    EXPECT_EQ(mt.issue(nullptr, 0x1000), Sim_PE_IO_Not_Taken);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, ++log_info_cnt_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_, "null transaction is terminated");

    transaction_t t;
    EXPECT_EQ(mt.issue(&t, 0x1000), Sim_PE_IO_Not_Taken);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, ++log_info_cnt_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
              "map_target not set, transaction terminated");

    simics::ConfObjectRef null_obj {nullptr};
    EXPECT_EQ(mt.set_map_target(null_obj), true);
    EXPECT_EQ(mt.map_target(), nullptr);

    Stubs::instance_.sim_last_error_ret_ = "Interface not found";
    auto conf_obj = reinterpret_cast<conf_object_t *>(
            uintptr_t{0xdeadbeef});
    Stubs::instance_.sim_object_name_[conf_obj] = "test";
    simics::ConfObjectRef a_obj {conf_obj};
    EXPECT_PRED_THROW(mt.set_map_target(a_obj),
                      simics::detail::SetInterfaceNotFound,
                      checkError);
    EXPECT_EQ(mt.map_target(), nullptr);
    Stubs::instance_.sim_last_error_ret_ = "";

    Stubs::instance_.new_map_target_ret_ = reinterpret_cast<map_target_t *>(
        0xc0ffee);
    EXPECT_EQ(mt.set_map_target(a_obj), true);
    EXPECT_EQ(mt.map_target(), Stubs::instance_.new_map_target_ret_);

    Stubs::instance_.sim_transaction_is_read_ = true;
    Stubs::instance_.sim_transaction_size_ = 2;
    mt.issue(&t, 0x1000);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, ++log_info_cnt_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_, "read 2 bytes @0x1000 in dev");

    Stubs::instance_.issue_transaction_ret_ = Sim_PE_IO_Not_Taken;
    mt.issue(&t, 0x1000);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, ++log_info_cnt_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
              "failed to read 2 bytes @0x1000 in dev");

    mt.read(0x1000, 16);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, ++log_error_cnt_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "size must be less than or equal to 8");

    mt.read(0x1000, 2);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, ++log_info_cnt_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_,
              "failed to read 2 bytes @0x1000 in dev");

    Stubs::instance_.issue_transaction_ret_ = Sim_PE_No_Exception;
    mt.read(0x1000, 2);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, ++log_info_cnt_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_, "read 2 bytes @0x1000 in dev");

    std::vector<uint8_t> b(2);
    mt.read_bytes(0x1000, 2, b.data());
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, ++log_info_cnt_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_, "read 2 bytes @0x1000 in dev");

    Stubs::instance_.sim_transaction_is_read_ = false;
    mt.write(0x1000, 12, 0xdeadbeef);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, ++log_error_cnt_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "size must be less than or equal to 8");

    Stubs::instance_.sim_transaction_size_ = 4;
    mt.write(0x1000, 4, 0xdeadbeef);
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, ++log_info_cnt_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_, "write 4 bytes @0x1000 in dev");

    b.resize(4);
    mt.write_bytes(0x1000, 4, b.data());
    EXPECT_EQ(Stubs::instance_.sim_log_info_cnt_, ++log_info_cnt_before);
    EXPECT_EQ(Stubs::instance_.SIM_log_info_, "write 4 bytes @0x1000 in dev");

    mt.set_map_target(null_obj);
    EXPECT_EQ(mt.map_target(), nullptr);
}

TEST(TestConnectTemplate, TestMapTargetConnect) {
    MockConfObject device {reinterpret_cast<conf_object_t *>(0xc0ffee), "dev"};
    Stubs::instance_.sim_object_name_[device.obj().object()] = "dev";
    simics::MapTargetConnect mpc{device.obj()};

    auto conf_obj = reinterpret_cast<conf_object_t *>(
            uintptr_t{0xdeadbeef});
    Stubs::instance_.sim_object_name_[conf_obj] = "test";
    simics::ConfObjectRef a_obj {conf_obj};
    Stubs::instance_.new_map_target_ret_ = reinterpret_cast<map_target_t *>(
        0xc0ffee);
    EXPECT_EQ(mpc.set_map_target(a_obj), true);
    EXPECT_EQ(mpc.map_target(), Stubs::instance_.new_map_target_ret_);
}
