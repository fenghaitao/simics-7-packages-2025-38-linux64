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

#include <simics/conf-object.h>

#include <gtest/gtest.h>
#include <cstdint>
#include <string>

#include "mock/stubs.h"

using simics::ConfObjectRef;
using simics::ConfObject;
using simics::from_obj;

// Test cases for ConfObjectRef
class ConfObjectRefTest : public ::testing::Test {
  protected:
    conf_object_t mock_conf_object;
    const std::string mock_interface_name = "interface_name";
    interface_t *mock_interface {
        reinterpret_cast<interface_t*>(uintptr_t{0xdeadbeef})
    };
    ConfObjectRef conf_object_ref;

    ConfObjectRefTest() : conf_object_ref(&mock_conf_object) {}

    void SetUp() override {
        Stubs::instance_.sim_c_get_port_interface_map_.clear();
        Stubs::instance_.sim_c_get_port_interface_map_[mock_interface_name] = \
            mock_interface;
        Stubs::instance_.sim_object_name_.clear();
        Stubs::instance_.sim_object_name_[&mock_conf_object] = "object_name";
        Stubs::instance_.sim_port_object_parent_ret_ = &mock_conf_object;
        sim_log_warning_cnt_ = Stubs::instance_.sim_log_warning_cnt_;
    }

    void TearDown() override {
        Stubs::instance_.sim_require_object_obj_ = nullptr;
        Stubs::instance_.sim_object_is_configured_obj_ = nullptr;
        Stubs::instance_.sim_object_is_configured_ret_ = false;
        Stubs::instance_.sim_c_get_port_interface_map_.clear();
        Stubs::instance_.sim_object_data_ret_ = nullptr;
        Stubs::instance_.sim_object_name_.clear();
        Stubs::instance_.sim_port_object_parent_ret_ = nullptr;
    }

    size_t sim_log_warning_cnt_;
};

TEST_F(ConfObjectRefTest, Constructor) {
    // Default CTOR
    ConfObjectRef ref_default;

    // CTOR with conf_object_t *
    ConfObjectRef ref(&mock_conf_object);
    EXPECT_EQ(ref.object(), &mock_conf_object);
}

TEST_F(ConfObjectRefTest, EqualityOperator) {
    ConfObjectRef ref1(&mock_conf_object);
    ConfObjectRef ref2(&mock_conf_object);
    EXPECT_EQ(ref1, ref2);

    ref1.set_port_name("port1");
    ref2.set_port_name("port2");
    EXPECT_NE(ref1, ref2);
}

TEST_F(ConfObjectRefTest, ObjectPtr) {
    EXPECT_EQ(conf_object_ref.object(), &mock_conf_object);
    conf_object_t* obj_ptr = conf_object_ref;
    EXPECT_EQ(obj_ptr, &mock_conf_object);
}

TEST_F(ConfObjectRefTest, PortName) {
    std::string name = "port_name";
    conf_object_ref.set_port_name(name);
    EXPECT_EQ(conf_object_ref.port_name(), name);
}

TEST_F(ConfObjectRefTest, Data) {
    Stubs::instance_.sim_object_data_ret_ = reinterpret_cast<void *>(0xc0ffee);
    EXPECT_EQ(conf_object_ref.data(), Stubs::instance_.sim_object_data_ret_);
}

TEST_F(ConfObjectRefTest, Name) {
    EXPECT_EQ(conf_object_ref.name(), "object_name");

    // the name may change if the object is moved to another hierarchical
    // location
    Stubs::instance_.sim_object_name_[&mock_conf_object] = "new_object_name";
    EXPECT_EQ(conf_object_ref.name(), "new_object_name");
}

TEST_F(ConfObjectRefTest, Require) {
    conf_object_ref.require();
    EXPECT_EQ(Stubs::instance_.sim_require_object_obj_, &mock_conf_object);
}

TEST_F(ConfObjectRefTest, Configured) {
    Stubs::instance_.sim_object_is_configured_ret_ = true;
    EXPECT_EQ(conf_object_ref.configured(), true);
    EXPECT_EQ(Stubs::instance_.sim_object_is_configured_obj_,
              &mock_conf_object);
}

TEST_F(ConfObjectRefTest, PortObjParent) {
    EXPECT_EQ(conf_object_ref.port_obj_parent(), &mock_conf_object);
}

TEST_F(ConfObjectRefTest, GetInterface) {
    EXPECT_EQ(conf_object_ref.get_interface(mock_interface_name),
              mock_interface);
}

TEST_F(ConfObjectRefTest, AsConfObject) {
    ConfObject obj(conf_object_ref);
    Stubs::instance_.sim_object_data_ret_ = reinterpret_cast<void *>(&obj);
    EXPECT_EQ(&conf_object_ref.as_conf_object(), &obj);

    Stubs::instance_.sim_object_data_ret_ = nullptr;
    EXPECT_THROW(conf_object_ref.as_conf_object(), std::runtime_error);
}

TEST_F(ConfObjectRefTest, GroupId) {
    // Temporarily disable deprecation warnings
    #if defined(__GNUC__) || defined(__GNUG__)
    #pragma GCC diagnostic push
    #pragma GCC diagnostic ignored "-Wdeprecated-declarations"
    #elif defined(_MSC_VER)
    #pragma warning(push)
    #pragma warning(disable: 4996)
    #endif

    conf_object_ref.group_id("xxx");
    EXPECT_EQ(sim_log_warning_cnt_ + 1, Stubs::instance_.sim_log_warning_cnt_);

    // Re-enable deprecation warnings
    #if defined(__GNUC__) || defined(__GNUG__)
    #pragma GCC diagnostic pop
    #elif defined(_MSC_VER)
    #pragma warning(pop)
    #endif
}

// Test cases for ConfObject
class ConfObjectTest : public ::testing::Test {
  protected:
    ConfObjectRef mock_conf_object_ref;
    ConfObject conf_object;

    ConfObjectTest() : conf_object(mock_conf_object_ref) {}

    void SetUp() override {
    }

    void TearDown() override {
        Stubs::instance_.sim_object_is_configured_obj_ = nullptr;
        Stubs::instance_.sim_object_is_configured_ret_ = false;
    }
};

TEST_F(ConfObjectTest, Constructor) {
    // CTOR with ConfObjectRef
    ConfObject obj(mock_conf_object_ref);
    EXPECT_EQ(obj.obj(), mock_conf_object_ref);
}

TEST_F(ConfObjectTest, Finalized) {
    Stubs::instance_.sim_object_is_configured_ret_ = false;
    EXPECT_EQ(conf_object.finalized(),
              Stubs::instance_.sim_object_is_configured_ret_);
    Stubs::instance_.sim_object_is_configured_ret_ = true;
    EXPECT_EQ(conf_object.finalized(),
              Stubs::instance_.sim_object_is_configured_ret_);
}

TEST_F(ConfObjectTest, Finalize) {
    conf_object.finalize();
    EXPECT_EQ(Stubs::instance_.sim_object_is_configured_obj_,
              mock_conf_object_ref.object());
}

TEST_F(ConfObjectTest, ObjectsFinalized) {
    conf_object.objects_finalized();
    EXPECT_EQ(Stubs::instance_.sim_object_is_configured_obj_,
              mock_conf_object_ref.object());
}

// Some base class
class TestFromObjBase {
  public:
    TestFromObjBase() = default;
    virtual ~TestFromObjBase() = default;
};

class TestFromObjDerived1 : public ConfObject, public TestFromObjBase {
  public:
    explicit TestFromObjDerived1(ConfObjectRef obj) : ConfObject(obj) {}
};

class TestFromObjDerived2 : public TestFromObjBase, public ConfObject {
  public:
    explicit TestFromObjDerived2(ConfObjectRef obj) : ConfObject(obj) {}
};

class FromObjTest : public ::testing::Test {
  protected:
    void SetUp() override {
        // Reset stubs
        Stubs::instance_.sim_object_data_ret_ = nullptr;
    }

    void TearDown() override {
        // Clean up
        Stubs::instance_.sim_object_data_ret_ = nullptr;
    }
};

TEST_F(FromObjTest, DerivedAsFirstBaseClass) {
    TestFromObjDerived1 derived1(nullptr);
    Stubs::instance_.sim_object_data_ret_ = static_cast<ConfObject*>(&derived1);

    TestFromObjDerived1 *result = from_obj<TestFromObjDerived1>(nullptr);
    EXPECT_EQ(result, &derived1);
}

// This ensures that ConfObject does not need to be the first base class.
// Invalid conversions, such as a direct cast from void* to T* in from_obj,
// could result in incorrect behavior.
TEST_F(FromObjTest, DerivedAsSecondBaseClass) {
    TestFromObjDerived2 derived2(nullptr);
    Stubs::instance_.sim_object_data_ret_ = static_cast<ConfObject*>(&derived2);

    TestFromObjDerived2* result = from_obj<TestFromObjDerived2>(nullptr);
    EXPECT_EQ(result, &derived2);
}
