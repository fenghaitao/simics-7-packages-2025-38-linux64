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

#include <simics/conf-class.h>

#include <gtest/gtest.h>
#include <simics/object-factory-interface.h>

#include <iostream>
#include <memory>
#include <string>
#include <type_traits>  // is_trivially_constructible
#include <utility>  // move
#include <vector>

#include "mock/gtest_extensions.h"  // EXPECT_PRED_THROW
#include "mock/mock-object.h"
#include "mock/stubs.h"

using simics::ConfClass;
using simics::ConfClassPtr;

void resetClassInfo(class_info_t *info) {
    info->alloc = nullptr;
    info->init = nullptr;
    info->finalize = nullptr;
    info->objects_finalized = nullptr;
    info->deinit = nullptr;
    info->dealloc = nullptr;
    info->description = nullptr;
    info->short_desc = nullptr;
    info->kind = Sim_Class_Kind_Pseudo;
}

class ConfClassTest : public ::testing::Test {
  protected:
    void SetUp() override {
        // Reset stubs
        Stubs::instance_.sim_create_class_name_ = "";
        resetClassInfo(&Stubs::instance_.sim_create_class_class_info_);
        Stubs::instance_.a_conf_class_ = reinterpret_cast<conf_class_t*>(
                uintptr_t{0xdeadbeef});
        sim_create_class_cnt_ = Stubs::instance_.sim_create_class_cnt_;
        sim_set_class_data_cnt_ = Stubs::instance_.sim_set_class_data_cnt_;
        vt_set_constructor_data_cnt_ = \
            Stubs::instance_.vt_set_constructor_data_cnt_;
        sim_log_info_cnt_ = Stubs::instance_.sim_log_info_cnt_;
        sim_log_error_cnt_ = Stubs::instance_.sim_log_error_cnt_;
        sim_log_warning_cnt_ = Stubs::instance_.sim_log_warning_cnt_;
        sim_log_unimplemented_cnt_ = \
            Stubs::instance_.sim_log_unimplemented_cnt_;
        sim_register_interface_cnt_ = \
            Stubs::instance_.sim_register_interface_cnt_;
        Stubs::instance_.sim_register_interface_ret_ = 0;
        Stubs::instance_.sim_register_port_port_cls_ = nullptr;
        sim_register_port_cnt_ = Stubs::instance_.sim_register_port_cnt_;
        sim_register_attribute_cnt_ = \
            Stubs::instance_.sim_register_attribute_cnt_;
        sim_register_class_attribute_cnt_ = \
            Stubs::instance_.sim_register_class_attribute_cnt_;
        sim_register_event_cnt_ = Stubs::instance_.sim_register_event_cnt_;
        Stubs::instance_.sim_register_event_ret_ = \
            reinterpret_cast<event_class_t *>(uintptr_t{0xdeadbeef});
        sim_log_register_groups_cnt_ = \
            Stubs::instance_.sim_log_register_groups_cnt_;
        Stubs::instance_.sim_get_class_data_ret_ = nullptr;
    }

    void TearDown() override {
        // Clean up
        Stubs::instance_.sim_create_class_name_ = "";
        resetClassInfo(&Stubs::instance_.sim_create_class_class_info_);
        Stubs::instance_.a_conf_class_ = nullptr;
        Stubs::instance_.sim_register_interface_ret_ = 0;
        Stubs::instance_.sim_register_event_ret_ = nullptr;
        Stubs::instance_.sim_get_class_data_ret_ = nullptr;
    }

    size_t sim_create_class_cnt_;
    size_t sim_set_class_data_cnt_;
    size_t vt_set_constructor_data_cnt_;
    size_t sim_log_info_cnt_;
    size_t sim_log_error_cnt_;
    size_t sim_log_warning_cnt_;
    size_t sim_log_unimplemented_cnt_;
    size_t sim_register_interface_cnt_;
    size_t sim_register_port_cnt_;
    size_t sim_register_attribute_cnt_;
    size_t sim_register_class_attribute_cnt_;
    size_t sim_register_event_cnt_;
    size_t sim_log_register_groups_cnt_;
};

class FakeObjectFactory : public simics::ObjectFactoryInterface {
  public:
    FakeObjectFactory() : create_called_(false), clone_called_(false) {}

    virtual ~FakeObjectFactory() {
        if (cloned_ptr_) {
            delete cloned_ptr_;
        }
    }

    /**
     * @brief Creates a ConfObject instance from a conf_object_t pointer.
     *
     * This function simulates the creation of a ConfObject instance and
     * sets the create_called_ flag to true. It can be configured to throw
     * exceptions for testing purposes.
     *
     * @param obj Pointer to a conf_object_t instance.
     * @return Pointer to a newly created ConfObject instance (nullptr in this fake implementation).
     */
    simics::ConfObject *create(conf_object_t *obj) const override {
        create_called_ = true;
        if (throw_std_exception_) {
            throw std::runtime_error("Test std::exception");
        }
        if (throw_unknown_exception_) {
            throw "Test unknown exception";
        }
        return nullptr;
    }

    /**
     * @brief Clones the current FakeObjectFactory instance.
     *
     * This function simulates the cloning of the FakeObjectFactory instance
     * and sets the clone_called_ flag to true.
     *
     * @return Pointer to a cloned FakeObjectFactory instance.
     */
    ObjectFactoryInterface *clone() const override {
        clone_called_ = true;
        cloned_ptr_ = new FakeObjectFactory(*this);
        return cloned_ptr_;
    }

    bool create_called() const {
        return create_called_;
    }

    bool clone_called() const {
        return clone_called_;
    }

    void set_throw_std_exception(bool value) {
        throw_std_exception_ = value;
    }

    void set_throw_unknown_exception(bool value) {
        throw_unknown_exception_ = value;
    }

  private:
    mutable bool create_called_;
    mutable bool clone_called_;
    mutable ObjectFactoryInterface *cloned_ptr_ = nullptr;
    bool throw_std_exception_ = false;
    bool throw_unknown_exception_ = false;
};

TEST(TestConfClass, TestDeletedConstructor) {
    // Default constructor deleted
    EXPECT_FALSE(std::is_trivially_constructible<ConfClass>::value);

    // Copy constructor deleted
    EXPECT_FALSE((std::is_trivially_constructible<
                  ConfClass, const ConfClass&>::value));

    // Construct from conf_class_t is prohibited
    EXPECT_FALSE((std::is_trivially_constructible<
                  ConfClass, conf_class_t*>::value));
}

TEST_F(ConfClassTest, TestCreateSuccess) {
    FakeObjectFactory object_factory;
    std::string name { "TestCreateSuccess_name" };
    std::string short_desc { "TestCreateSuccess_short_desc" };
    std::string description { "TestCreateSuccess_description" };

    auto ret = ConfClass::createInstance(name, short_desc, description,
                                         Sim_Class_Kind_Vanilla,
                                         object_factory);

    EXPECT_NE(ret, nullptr);
    EXPECT_EQ(ret->name(), name);
    EXPECT_EQ(ret->description(), description);

    EXPECT_EQ(Stubs::instance_.sim_create_class_cnt_,
              sim_create_class_cnt_ + 1);
    EXPECT_EQ(Stubs::instance_.sim_set_class_data_cnt_,
              sim_set_class_data_cnt_ + 1);
    EXPECT_EQ(Stubs::instance_.vt_set_constructor_data_cnt_,
              vt_set_constructor_data_cnt_ + 1);

    EXPECT_EQ(Stubs::instance_.sim_create_class_name_, name);
    EXPECT_EQ(Stubs::instance_.sim_create_class_class_info_.short_desc,
              short_desc);
    EXPECT_EQ(Stubs::instance_.sim_create_class_class_info_.description,
              description);
    EXPECT_EQ(Stubs::instance_.sim_create_class_class_info_.kind,
              Sim_Class_Kind_Vanilla);

    EXPECT_FALSE(object_factory.create_called());
    EXPECT_TRUE(object_factory.clone_called());
}

bool checkFailedCreatingClass(const std::exception &ex) {
    EXPECT_STREQ(ex.what(), "Failed to create class name");
    return true;
}

TEST(TestConfClass, TestCreateThrow) {
    FakeObjectFactory object_factory;
    size_t sim_create_class_cnt = Stubs::instance_.sim_create_class_cnt_;
    // When the return value is nullptr, exception is thrown
    Stubs::instance_.a_conf_class_ = nullptr;

    EXPECT_PRED_THROW(
            ConfClass::createInstance("name", "short_desc", "description",
                                      Sim_Class_Kind_Vanilla, object_factory),
            std::runtime_error, checkFailedCreatingClass);

    EXPECT_EQ(Stubs::instance_.sim_create_class_cnt_,
              sim_create_class_cnt + 1);
    EXPECT_FALSE(object_factory.create_called());
    EXPECT_FALSE(object_factory.clone_called());
}

TEST_F(ConfClassTest, TestInit) {
    auto fake_obj_factory = FakeObjectFactory();
    ConfClass::createInstance("TestInit", "test init", "test init",
                              Sim_Class_Kind_Vanilla, fake_obj_factory);
    auto obj = std::make_unique<conf_object_t>();
    Stubs::instance_.sim_get_class_data_ret_ = &fake_obj_factory;

    EXPECT_EQ(fake_obj_factory.create_called(), false);
    Stubs::instance_.sim_create_class_class_info_.init(obj.get());
    EXPECT_EQ(fake_obj_factory.create_called(), true);

    // Test exception handling
    fake_obj_factory.set_throw_std_exception(true);
    EXPECT_EQ(sim_log_info_cnt_, Stubs::instance_.sim_log_info_cnt_);
    Stubs::instance_.sim_create_class_class_info_.init(obj.get());
    EXPECT_EQ(++sim_log_info_cnt_, Stubs::instance_.sim_log_info_cnt_);

    fake_obj_factory.set_throw_std_exception(false);
    fake_obj_factory.set_throw_unknown_exception(true);
    EXPECT_EQ(sim_log_info_cnt_, Stubs::instance_.sim_log_info_cnt_);
    Stubs::instance_.sim_create_class_class_info_.init(obj.get());
    EXPECT_EQ(++sim_log_info_cnt_, Stubs::instance_.sim_log_info_cnt_);
}

TEST_F(ConfClassTest, TestDeinit) {
    ConfClass::createInstance("TestDeinit", "test deinit", "test deinit",
                              Sim_Class_Kind_Vanilla, FakeObjectFactory());

    auto *obj = new MockConfObject {
        reinterpret_cast<conf_object_t*>(uintptr_t{0xdeadbeef}),
        "MockConfObject"};
    Stubs::instance_.sim_object_data_ret_ = obj;
    // deinit will delete the obj pointer but hard to verify it
    Stubs::instance_.sim_create_class_class_info_.deinit(nullptr);
}

class MockConfObjectWithFinalize : public MockConfObject {
  public:
    MockConfObjectWithFinalize(conf_object_t *obj, const std::string &name)
        : MockConfObject(obj, name) {
        Stubs::instance_.sim_object_data_ret_ = this;
    }

    virtual ~MockConfObjectWithFinalize() {
        Stubs::instance_.sim_object_data_ret_ = nullptr;
    }

    void finalize() override {
        finalize_called_ = true;
    }

    void objects_finalized() override {
        objects_finalized_called_ = true;
    }

    bool finalize_called_ { false };
    bool objects_finalized_called_ { false };
};

TEST_F(ConfClassTest, TestFinalize) {
    ConfClass::createInstance("TestFinalize", "test finalize", "test finalize",
                              Sim_Class_Kind_Vanilla, FakeObjectFactory());
    MockConfObjectWithFinalize obj {
        reinterpret_cast<conf_object_t*>(uintptr_t{0xdeadbeef}),
        "MockConfObject"};
    EXPECT_EQ(obj.finalize_called_, false);
    Stubs::instance_.sim_create_class_class_info_.finalize(obj.obj());
    EXPECT_EQ(obj.finalize_called_, true);
}

TEST_F(ConfClassTest, TestObjectsFinalized) {
    ConfClass::createInstance("TestObjectsFinalized", "test objects finalize",
                              "test objects finalized",
                              Sim_Class_Kind_Vanilla, FakeObjectFactory());
    MockConfObjectWithFinalize obj {
        reinterpret_cast<conf_object_t*>(uintptr_t{0xdeadbeef}),
        "MockConfObject"};
    EXPECT_EQ(obj.objects_finalized_called_, false);
    Stubs::instance_.sim_create_class_class_info_.objects_finalized(obj.obj());
    EXPECT_EQ(obj.objects_finalized_called_, true);
}

class noInitClass {};

class hasInitClass {
  public:
    static void init_class(simics::ConfClass *cls) {
        init_class_called_ = true;
        init_class_cls_ = cls;
    }

    static bool init_class_called_;
    static simics::ConfClass *init_class_cls_;
};
bool hasInitClass::init_class_called_ { false };
simics::ConfClass *hasInitClass::init_class_cls_ { nullptr };

TEST(TestConfClass, TestInitClass) {
    hasInitClass::init_class_called_ = false;
    hasInitClass::init_class_cls_ = nullptr;

    simics::ConfClass *cls = reinterpret_cast<simics::ConfClass*>(
            uintptr_t{0xdeadbeef});

    simics::detail::init_class<noInitClass>(cls);
    EXPECT_FALSE(hasInitClass::init_class_called_);
    EXPECT_EQ(hasInitClass::init_class_cls_, nullptr);

    simics::detail::init_class<hasInitClass>(cls);
    EXPECT_TRUE(hasInitClass::init_class_called_);
    EXPECT_EQ(hasInitClass::init_class_cls_, cls);
}

TEST(TestConfClass, TestMakeClassWithT) {
    std::string name { "TestMakeClassWithT_name" };
    std::string short_desc { "TestMakeClassWithT_short_desc" };
    std::string description { "TestMakeClassWithT_description" };
    Stubs::instance_.a_conf_class_ = reinterpret_cast<conf_class_t*>(
            uintptr_t{0xdeadbeef});
    size_t sim_create_class_cnt = Stubs::instance_.sim_create_class_cnt_;
    size_t instance_cnt = MockObject::instance_cnt_;
    size_t init_class_cnt = MockObject::init_class_cnt_;

    auto ret = simics::make_class<MockObject>(name, short_desc, description);

    EXPECT_EQ(Stubs::instance_.sim_create_class_cnt_,
              sim_create_class_cnt + 1);
    // No instance created in make_class
    EXPECT_EQ(MockObject::instance_cnt_, instance_cnt);

    EXPECT_EQ(MockObject::init_class_cnt_, init_class_cnt + 1);
    EXPECT_EQ(static_cast<conf_class_t*>(*ret),
              Stubs::instance_.a_conf_class_);
}

TEST(TestConfClass, TestMakeClassWithTArg) {
    Stubs::instance_.a_conf_class_ = reinterpret_cast<conf_class_t*>(
            0xc0ffee);
    size_t sim_create_class_cnt = Stubs::instance_.sim_create_class_cnt_;
    size_t instance_cnt = MockObjectWithArg::instance_cnt_;
    size_t init_class_cnt = MockObjectWithArg::init_class_cnt_;

    std::string name { "TestMakeClassWithTArg_name" };
    std::string short_desc { "TestMakeClassWithTArg_short_desc" };
    std::string description { "TestMakeClassWithTArg_description" };
    void *arg = nullptr;

    auto ret = simics::make_class<MockObjectWithArg, void>(name, short_desc,
                                                           description, arg);

    EXPECT_EQ(Stubs::instance_.sim_create_class_cnt_,
              sim_create_class_cnt + 1);
    // No instance created in make_class
    EXPECT_EQ(MockObjectWithArg::instance_cnt_, instance_cnt);

    EXPECT_EQ(MockObjectWithArg::init_class_cnt_, init_class_cnt + 1);
    EXPECT_EQ(static_cast<conf_class_t*>(*ret),
              Stubs::instance_.a_conf_class_);
}

TEST(TestConfClass, TestRegisterClassTWithSimics) {
    std::string name {"TestRegisterClassTWithSimics_name"};
    std::string short_desc {"TestRegisterClassTWithSimics_short_desc"};
    std::string description {"TestRegisterClassTWithSimics_description"};
    Stubs::instance_.a_conf_class_ = reinterpret_cast<conf_class_t*>(
            uintptr_t{0xdeadbeef});
    size_t sim_create_class_cnt = Stubs::instance_.sim_create_class_cnt_;
    size_t instance_cnt = MockObject::instance_cnt_;
    size_t init_class_cnt = MockObject::init_class_cnt_;

    simics::RegisterClassWithSimics<MockObject>(name, short_desc, description);

    EXPECT_EQ(Stubs::instance_.sim_create_class_cnt_,
              sim_create_class_cnt + 1);
    // No instance should be created
    EXPECT_EQ(MockObject::instance_cnt_, instance_cnt);

    EXPECT_EQ(MockObject::init_class_cnt_, init_class_cnt + 1);
}

TEST(TestConfClass, TestRegisterClassTWithSimicsWithArg) {
    Stubs::instance_.a_conf_class_ = reinterpret_cast<conf_class_t*>(
            0xc0ffee);
    size_t sim_create_class_cnt = Stubs::instance_.sim_create_class_cnt_;
    size_t instance_cnt = MockObjectWithArg::instance_cnt_;
    size_t init_class_cnt = MockObjectWithArg::init_class_cnt_;

    std::string name {"TestRegisterClassTWithSimicsWithArg_name"};
    std::string short_desc {"TestRegisterClassTWithSimicsWithArg_short_desc"};
    std::string description {
        "TestRegisterClassTWithSimicsWithArg_description"
    };
    void *arg = nullptr;

    simics::RegisterClassWithSimics<MockObjectWithArg, void>(name, short_desc,
                                                             description, arg);

    EXPECT_EQ(Stubs::instance_.sim_create_class_cnt_,
              sim_create_class_cnt + 1);
    // No instance created in make_class
    EXPECT_EQ(MockObjectWithArg::instance_cnt_, instance_cnt);

    EXPECT_EQ(MockObjectWithArg::init_class_cnt_, init_class_cnt + 1);
}

class FakeInterfaceInfo : public simics::iface::InterfaceInfo {
  public:
    FakeInterfaceInfo(const std::string &name, const interface_t *iface)
        : simics::iface::InterfaceInfo(),
        name_(name), iface_(iface) {}

    std::string name() const override {
        return name_;
    }

    const interface_t *cstruct() const override {
        return iface_;
    }

  private:
    std::string name_;
    const interface_t *iface_;
};

TEST_F(ConfClassTest, TestAddInterface) {
    FakeObjectFactory object_factory;

    {
        auto conf_class = ConfClass::createInstance("test_add_iface",
                                                    "short_desc",
                                                    "description",
                                                    Sim_Class_Kind_Vanilla,
                                                    object_factory);
        // nullptr cstruct
        FakeInterfaceInfo iface_info("test_iface", nullptr);
        conf_class->add(iface_info);
        EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
                  sim_log_error_cnt_ + 1);
        EXPECT_EQ(Stubs::instance_.SIM_log_error_,
                  "Invalid InterfaceInfo (cstruct() returns NULL)");
    }

    const interface_t *iface {
        reinterpret_cast<const interface_t*>(uintptr_t{0xdeadbeef})
    };
    {
        auto conf_class = ConfClass::createInstance("test_add_iface",
                                                    "short_desc",
                                                    "description",
                                                    Sim_Class_Kind_Vanilla,
                                                    object_factory);
        // normal cstruct
        FakeInterfaceInfo iface_info("test_iface", iface);
        conf_class->add(iface_info);
        // No registration of interface here
        EXPECT_EQ(Stubs::instance_.sim_register_interface_cnt_,
                  sim_register_interface_cnt_);
    }
    // Registration is delayed till here
    EXPECT_EQ(Stubs::instance_.sim_register_interface_cnt_,
              ++sim_register_interface_cnt_);

    {
        auto conf_class = ConfClass::createInstance("test_add_iface",
                                                    "short_desc",
                                                    "description",
                                                    Sim_Class_Kind_Vanilla,
                                                    object_factory);
        // fail to register
        Stubs::instance_.sim_register_interface_ret_ = 1;
        FakeInterfaceInfo iface_info("test_iface", iface);
        conf_class->add(iface_info);
        EXPECT_EQ(Stubs::instance_.sim_register_interface_cnt_,
                  sim_register_interface_cnt_);
        // No registration of interface here
        EXPECT_EQ(Stubs::instance_.sim_register_interface_cnt_,
                  sim_register_interface_cnt_);
    }
    // Registration is delayed till here
    EXPECT_EQ(Stubs::instance_.sim_register_interface_cnt_,
              ++sim_register_interface_cnt_);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_,
              sim_log_error_cnt_ + 2);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_,
              "Failed to add info for interface 'test_iface': ");

    const interface_t *iface2 {
        reinterpret_cast<const interface_t*>(uintptr_t{0xc0ffee})
    };
    {
        // Test InterfaceInfo can be overwritten
        auto conf_class = ConfClass::createInstance("test_add_iface",
                                                    "short_desc",
                                                    "description",
                                                    Sim_Class_Kind_Vanilla,
                                                    object_factory);
        // normal cstruct
        FakeInterfaceInfo iface_info("test_iface", iface);
        conf_class->add(iface_info);
        // No registration of interface here
        EXPECT_EQ(Stubs::instance_.sim_register_interface_cnt_,
                  sim_register_interface_cnt_);
        // Overwrite it

        FakeInterfaceInfo iface_info2("test_iface", iface2);
        conf_class->add(iface_info2);
    }
    EXPECT_EQ(Stubs::instance_.sim_register_interface_cnt_,
              ++sim_register_interface_cnt_);
    EXPECT_EQ(Stubs::instance_.sim_register_interface_map_.size(), 1);
    auto it = Stubs::instance_.sim_register_interface_map_.find("test_iface");
    EXPECT_NE(it, Stubs::instance_.sim_register_interface_map_.end());
    EXPECT_EQ(it->second, iface2);
}

TEST_F(ConfClassTest, TestAddPort) {
    FakeObjectFactory object_factory;
    auto conf_class = ConfClass::createInstance("test_add_port_class",
                                                "short_desc", "description",
                                                Sim_Class_Kind_Vanilla,
                                                object_factory);
    auto port = ConfClass::createInstance("test_add_port_port", "short_desc",
                                          "description", Sim_Class_Kind_Vanilla,
                                          object_factory);

    {
        sim_register_port_cnt_ = Stubs::instance_.sim_register_port_cnt_;
        // normal port name
        conf_class->add(port, "test_port");
        EXPECT_EQ(Stubs::instance_.sim_register_port_cnt_,
                  sim_register_port_cnt_ + 1);
        EXPECT_EQ(Stubs::instance_.sim_register_port_port_cls_,
                  *port.get());
        EXPECT_STREQ(Stubs::instance_.sim_register_port_name_.c_str(),
                     "test_port");
    }

    {
        sim_register_port_cnt_ = Stubs::instance_.sim_register_port_cnt_;
        // expand port array
        conf_class->add(port, "test_port_array[3]");
        EXPECT_EQ(Stubs::instance_.sim_register_port_cnt_,
                  sim_register_port_cnt_ + 3);
        // the last port name
        EXPECT_STREQ(Stubs::instance_.sim_register_port_name_.c_str(),
                     "test_port_array[2]");
    }

    {
        sim_register_port_cnt_ = Stubs::instance_.sim_register_port_cnt_;
        // no expand for invalid array-like name
        conf_class->add(port, "an_invalid_array[x]");
        EXPECT_EQ(Stubs::instance_.sim_register_port_cnt_,
                  sim_register_port_cnt_ + 1);
    }

    {
        // multidimensional array is not supported
        sim_register_port_cnt_ = Stubs::instance_.sim_register_port_cnt_;
        conf_class->add(port, "a_port_multi_array[3][2]");
        // Unexpandable name will be used as it is
        EXPECT_EQ(Stubs::instance_.sim_register_port_cnt_,
                  sim_register_port_cnt_ + 1);
    }

    {
        // array inside a namespace
        sim_register_port_cnt_ = Stubs::instance_.sim_register_port_cnt_;
        conf_class->add(port, "port.a_port_array[3]");
        EXPECT_EQ(Stubs::instance_.sim_register_port_cnt_,
                  sim_register_port_cnt_ + 3);
        // the last port name
        EXPECT_STREQ(Stubs::instance_.sim_register_port_name_.c_str(),
                     "port.a_port_array[2]");
    }
}

bool checkTooManyLogGroups(const std::exception &ex) {
    EXPECT_STREQ(ex.what(),
        "Maximum number of 63 user-defined log groups exceeded");
    return true;
}

TEST_F(ConfClassTest, TestAddLogGroup) {
    auto conf_class = ConfClass::createInstance("test_add_log_group",
                                                "short_desc",
                                                "description",
                                                Sim_Class_Kind_Vanilla,
                                                FakeObjectFactory());

    // Test nullptr are ignored
    conf_class->add(nullptr);
    EXPECT_EQ(Stubs::instance_.sim_log_register_groups_cnt_,
              sim_log_register_groups_cnt_);

    // Test adding log group with const char *
    const char * const log_group1[] { "A", 0, };
    std::vector<std::string> expect {"A"};
    conf_class->add(log_group1);
    EXPECT_EQ(conf_class->log_groups(), expect);

    // Test call it again
    const char * const log_group2[] { "B", "C", 0, };
    expect.push_back("B");
    expect.push_back("C");
    conf_class->add(log_group2);
    EXPECT_EQ(conf_class->log_groups(), expect);

    // Log group is not registered yet
    EXPECT_EQ(Stubs::instance_.sim_log_register_groups_cnt_,
              sim_log_register_groups_cnt_);

    // Test adding log group with initializer_list/LogGroups
    conf_class->add({"D", "E"});
    expect.push_back("D");
    expect.push_back("E");
    EXPECT_EQ(conf_class->log_groups(), expect);

    // Test call it again
    conf_class->add(simics::LogGroups{"F"});
    expect.push_back("F");
    EXPECT_EQ(conf_class->log_groups(), expect);

    // Log group is not registered yet
    EXPECT_EQ(Stubs::instance_.sim_log_register_groups_cnt_,
              sim_log_register_groups_cnt_);

    // Adding to 63 log groups
    conf_class->add({"G1", "G2", "G3", "G4", "G5", "G6",
                     "G7", "G8", "G9", "G10", "G11", "G12",
                     "G13", "G14", "G15", "G16", "G17", "G18",
                     "G19", "G20", "G21", "G22", "G23", "G24",
                     "G25", "G26", "G27", "G28", "G29", "G30",
                     "G31", "G32", "G33", "G34", "G35", "G36",
                     "G37", "G38", "G39", "G40", "G41", "G42",
                     "G43", "G44", "G45", "G46", "G47", "G48",
                     "G49", "G50", "G51", "G52", "G53", "G54",
                     "G55", "G56", "G57"});

    // Test adding too many log groups
    EXPECT_PRED_THROW(
        conf_class->add({"G58", "G59"}),
        std::runtime_error, checkTooManyLogGroups);
    const char * const log_group3[] { "G58", "G59", 0, };
    EXPECT_PRED_THROW(
        conf_class->add(log_group3),
        std::runtime_error, checkTooManyLogGroups);
}

TEST_F(ConfClassTest, TestAddAttribute) {
    FakeObjectFactory object_factory;
    auto conf_class = ConfClass::createInstance("test_add_attr", "short_desc",
                                                "description",
                                                Sim_Class_Kind_Vanilla,
                                                object_factory);

    simics::Attribute attr("test_attr", "i", "desc", nullptr, nullptr);
    conf_class->add(attr);
    // Verify that the attribute was added (mock verification)
    EXPECT_EQ(Stubs::instance_.sim_register_attribute_cnt_, 1);
}

TEST_F(ConfClassTest, TestAddClassAttribute) {
    FakeObjectFactory object_factory;
    auto conf_class = ConfClass::createInstance("test_add_class_attr",
                                                "short_desc",
                                                "description",
                                                Sim_Class_Kind_Vanilla,
                                                object_factory);

    simics::ClassAttribute class_attr("test_class_attr", "i", "desc",
                                      nullptr, nullptr, Sim_Attr_Pseudo);
    conf_class->add(class_attr);
    // Verify that the class attribute was added (mock verification)
    EXPECT_EQ(Stubs::instance_.sim_register_class_attribute_cnt_, 1);
}

bool checkFailedRegisteringEvent(const std::exception &ex) {
    EXPECT_STREQ(ex.what(), "Failed to register event test_event");
    return true;
}

TEST_F(ConfClassTest, TestAddEvent) {
    FakeObjectFactory object_factory;
    auto conf_class = ConfClass::createInstance("test_add_event", "short_desc",
                                                "description",
                                                Sim_Class_Kind_Vanilla,
                                                object_factory);

    event_class_t *ev_class = reinterpret_cast<event_class_t*>(
            uintptr_t{0xdead});
    simics::EventInfo event1("test_event", Sim_EC_No_Flags, &ev_class,
                             reinterpret_cast<simics::ev_callback>(0xbeef),
                             nullptr, nullptr, nullptr, nullptr);
    conf_class->add(std::move(event1));
    // Verify that the event was added (mock verification)
    EXPECT_EQ(Stubs::instance_.sim_register_event_cnt_, 1);

    simics::EventInfo event2("test_event", Sim_EC_Notsaved, &ev_class,
                             reinterpret_cast<simics::ev_callback>(0xbeef),
                             nullptr, nullptr, nullptr, nullptr);
    Stubs::instance_.sim_register_event_ret_ = nullptr;
    EXPECT_PRED_THROW(
        conf_class->add(std::move(event2)),
        std::runtime_error, checkFailedRegisteringEvent);
    // Verify that the event was added (mock verification)
    EXPECT_EQ(Stubs::instance_.sim_register_event_cnt_, 2);
}

TEST_F(ConfClassTest, TestRegisterLogGroups) {
    FakeObjectFactory factory;
    ConfClassPtr conf_class = ConfClass::createInstance(
        "TestClass", "Test Short Description", "Test Description",
        Sim_Class_Kind_Vanilla, factory);

    const char *log_groups[] {"group1", "group2", nullptr};
    conf_class->add(log_groups);

    // Simulate error during registration
    Stubs::instance_.sim_clear_exception_ret_ = SimExc_IllegalValue;

    EXPECT_EQ(sim_log_error_cnt_, Stubs::instance_.sim_log_error_cnt_);
    // The destructor of ConfClass will call register_log_groups
    // Verify that the log groups are registered correctly
    conf_class.reset();

    EXPECT_EQ(Stubs::instance_.sim_log_register_groups_cnt_,
              sim_log_register_groups_cnt_ + 1);
    EXPECT_EQ(sim_log_error_cnt_ + 1, Stubs::instance_.sim_log_error_cnt_);
}

TEST_F(ConfClassTest, TestGetGroupId) {
    FakeObjectFactory object_factory;

    // Need to wrap following code to trigger the ~ConfClass()
    {
        auto conf_class = ConfClass::createInstance("test_get_group_id",
                                                    "short_desc", "description",
                                                    Sim_Class_Kind_Vanilla,
                                                    object_factory);
        conf_class->add({"First", "Second", "Third"});
    }

    EXPECT_EQ(Stubs::instance_.sim_log_register_groups_cnt_,
              sim_log_register_groups_cnt_ + 1);
    EXPECT_EQ(ConfClass::getGroupId(Stubs::instance_.a_conf_class_, "First"),
              1);
    EXPECT_EQ(ConfClass::getGroupId(Stubs::instance_.a_conf_class_, "Second"),
              2);
    EXPECT_EQ(ConfClass::getGroupId(Stubs::instance_.a_conf_class_, "Third"),
              4);

    // Invalid group id
    EXPECT_EQ(ConfClass::getGroupId(Stubs::instance_.a_conf_class_, "Forth"),
              0);
    EXPECT_EQ(Stubs::instance_.sim_log_error_cnt_, sim_log_error_cnt_ + 1);
    EXPECT_EQ(Stubs::instance_.SIM_log_error_, "Undefined log group Forth");
}

TEST_F(ConfClassTest, TestGroupId) {
    FakeObjectFactory object_factory;

    // Need to wrap following code to trigger the ~ConfClass()
    {
        auto conf_class = ConfClass::createInstance("test_group_id",
                                                    "short_desc", "description",
                                                    Sim_Class_Kind_Vanilla,
                                                    object_factory);
        conf_class->add({"First", "Second", "Third"});
    }

    conf_object_t dummy_obj;
    dummy_obj.sobj.isa = reinterpret_cast<sclass_t *>(
            Stubs::instance_.a_conf_class_);
    // Define a dummy obj()
    auto obj = [&dummy_obj]() -> conf_object_t* {
        return &dummy_obj;
    };
    EXPECT_EQ(GROUP_ID(First), 1);
    EXPECT_EQ(GROUP_ID(Second), 2);
    EXPECT_EQ(GROUP_ID(Third), 4);
    EXPECT_EQ(GROUP_ID(Forth), 0);
    EXPECT_EQ(GROUP_ID(&dummy_obj, First), 1);
    EXPECT_EQ(GROUP_ID(&dummy_obj, Second), 2);
    EXPECT_EQ(GROUP_ID(&dummy_obj, Third), 4);
    EXPECT_EQ(GROUP_ID(&dummy_obj, Forth), 0);
}
