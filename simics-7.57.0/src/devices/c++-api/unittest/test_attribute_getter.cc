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

#include <simics/detail/attribute-getter.h>
#include <simics/attr-value.h>

#include <gtest/gtest.h>

#include "mock/stubs.h"

namespace test_attribute_getter {

class BaseObject : public simics::ConfObject {
  public:
    using ConfObject::ConfObject;
    int member_func() { return member_func_ret_; }
    int member_func_const() const { return member_func_const_ret_; }
    virtual int virtual_func() { return virtual_func_ret_; }

    int member_variable {0xa};

  private:
    const int member_func_ret_ {0xdead};
    const int member_func_const_ret_ {0xbeef};
    const int virtual_func_ret_ {0xc0ffee};
};

class DerivedObject : public BaseObject {
  public:
    explicit DerivedObject(const simics::ConfObjectRef &obj)
        : BaseObject(obj) {
        member_variable = 0xb;
    }

    int virtual_func() override { return 0xff; }
};

int &func_takes_obj_ref1(BaseObject &obj) {  // NOLINT(runtime/references)
    return obj.member_variable;
}

int func_takes_obj_ref2(BaseObject &obj) {  // NOLINT(runtime/references)
    return obj.member_variable + 1;
}

}  // namespace test_attribute_getter

using test_attribute_getter::BaseObject;
using test_attribute_getter::DerivedObject;
using test_attribute_getter::func_takes_obj_ref1;
using test_attribute_getter::func_takes_obj_ref2;

TEST(TestAttributeGetter, TestClassMemberFunctionPtr) {
    auto *obj = new conf_object_t;

    // Test attribute getter on BaseObject
    BaseObject base(obj);
    Stubs::instance_.sim_object_data_ret_ = &base;

    // typename T = int, typename O = BaseObject, typename C = BaseObject
    using base_member_func_t = simics::detail::attr_getter_helper_dual<
        decltype(&BaseObject::member_func), BaseObject>;
    simics::AttrValue value {
        base_member_func_t::template f<&BaseObject::member_func>(obj)
    };
    EXPECT_EQ(SIM_attr_integer(value), 0xdead);

    using base_member_func_ct = simics::detail::attr_getter_helper_dual<
        decltype(&BaseObject::member_func_const), BaseObject>;
    value = base_member_func_ct::template f<
        &BaseObject::member_func_const>(obj);
    EXPECT_EQ(SIM_attr_integer(value), 0xbeef);

    // Test attribute getter on derived class of BaseObject
    DerivedObject derived(obj);
    Stubs::instance_.sim_object_data_ret_ = &derived;

    // typename T = int, typename O = BaseObject, typename C = DerivedObject
    using derived_member_func_t1 = simics::detail::attr_getter_helper_dual<
        decltype(&BaseObject::member_func), DerivedObject>;
    value = derived_member_func_t1::template f<&BaseObject::member_func>(obj);
    EXPECT_EQ(SIM_attr_integer(value), 0xdead);

    using derived_member_func_ct1 = simics::detail::attr_getter_helper_dual<
        decltype(&BaseObject::member_func_const), DerivedObject>;
    value = derived_member_func_ct1::template f<
        &BaseObject::member_func_const>(obj);
    EXPECT_EQ(SIM_attr_integer(value), 0xbeef);

    // typename T = int, typename O = DerivedObject, typename C = DerivedObject
    using derived_member_func_t2 = simics::detail::attr_getter_helper_dual<
        decltype(&DerivedObject::member_func), DerivedObject>;
    value = derived_member_func_t2::template f<
        &DerivedObject::member_func>(obj);
    EXPECT_EQ(SIM_attr_integer(value), 0xdead);

    using derived_member_func_ct2 = simics::detail::attr_getter_helper_dual<
        decltype(&DerivedObject::member_func_const), DerivedObject>;
    value = derived_member_func_ct2::template f<
        &DerivedObject::member_func_const>(obj);
    EXPECT_EQ(SIM_attr_integer(value), 0xbeef);

    // typename T = int, typename O = DerivedObject, typename C = BaseObject
    using derived_member_func_t3 = simics::detail::attr_getter_helper_dual<
        decltype(&DerivedObject::member_func), BaseObject>;
    value = derived_member_func_t3::template f<
        &DerivedObject::member_func>(obj);
    EXPECT_EQ(SIM_attr_integer(value), 0xdead);

    using derived_member_func_ct3 = simics::detail::attr_getter_helper_dual<
        decltype(&DerivedObject::member_func_const), BaseObject>;
    value = derived_member_func_ct3::template f<
        &DerivedObject::member_func_const>(obj);
    EXPECT_EQ(SIM_attr_integer(value), 0xbeef);

    delete obj;
    Stubs::instance_.sim_object_data_ret_ = nullptr;
}

TEST(TestAttributeGetter, TestClassMemberVariablePtr) {
    auto *obj = new conf_object_t;

    // Test attribute getter on BaseObject
    BaseObject base(obj);
    Stubs::instance_.sim_object_data_ret_ = &base;

    // typename T = int, typename O = BaseObject, typename C = BaseObject
    using base_member_variable_t = simics::detail::attr_getter_helper_dual<
        decltype(&BaseObject::member_variable), BaseObject>;
    simics::AttrValue value {
        base_member_variable_t::template f<
            &BaseObject::member_variable>(obj)
    };
    EXPECT_EQ(SIM_attr_integer(value), 0xa);

    // Test attribute getter on derived class of BaseObject
    DerivedObject derived(obj);
    Stubs::instance_.sim_object_data_ret_ = &derived;

    // typename T = int, typename O = BaseObject, typename C = DerivedObject
    using derived_member_variable_t1 = simics::detail::attr_getter_helper_dual<
        decltype(&BaseObject::member_variable), DerivedObject>;
    value = derived_member_variable_t1::template f<
        &BaseObject::member_variable>(obj);
    EXPECT_EQ(SIM_attr_integer(value), 0xb);

    // typename T = int, typename O = DerivedObject, typename C = DerivedObject
    using derived_member_variable_t2 = simics::detail::attr_getter_helper_dual<
        decltype(&DerivedObject::member_variable), DerivedObject>;
    value = derived_member_variable_t2::template f<
        &DerivedObject::member_variable>(obj);
    EXPECT_EQ(SIM_attr_integer(value), 0xb);

    // typename T = int, typename O = DerivedObject, typename C = BaseObject
    using derived_member_variable_t3 = simics::detail::attr_getter_helper_dual<
        decltype(&DerivedObject::member_variable), BaseObject>;
    value = derived_member_variable_t3::template f<
        &DerivedObject::member_variable>(obj);
    EXPECT_EQ(SIM_attr_integer(value), 0xb);

    delete obj;
    Stubs::instance_.sim_object_data_ret_ = nullptr;
}

TEST(TestAttributeGetter, TestFunctionWithObjectReference) {
    auto *obj = new conf_object_t;

    // Test attribute getter on BaseObject
    BaseObject base(obj);
    Stubs::instance_.sim_object_data_ret_ = &base;

    simics::AttrValue value {
        simics::detail::attr_getter_helper<
            decltype(&func_takes_obj_ref1)>::template f<
                &func_takes_obj_ref1>(obj)
    };
    EXPECT_EQ(SIM_attr_integer(value), 0xa);

    value = simics::detail::attr_getter_helper<
        decltype(&func_takes_obj_ref2)>::template f<
            &func_takes_obj_ref2>(obj);
    EXPECT_EQ(SIM_attr_integer(value), 0xb);

    // Test attribute getter on derived class of BaseObject
    DerivedObject derived(obj);
    Stubs::instance_.sim_object_data_ret_ = &derived;

    value = simics::detail::attr_getter_helper<
        decltype(&func_takes_obj_ref1)>::template f<
            &func_takes_obj_ref1>(obj);
    EXPECT_EQ(SIM_attr_integer(value), 0xb);

    value = simics::detail::attr_getter_helper<
        decltype(&func_takes_obj_ref2)>::template f<
            &func_takes_obj_ref2>(obj);
    EXPECT_EQ(SIM_attr_integer(value), 0xc);

    delete obj;
    Stubs::instance_.sim_object_data_ret_ = nullptr;
}
