// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2023 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include <simics/detail/conf-object-util.h>

#include <gtest/gtest.h>

#include <algorithm>
#include <chrono>  // NOLINT [build/c++11]
#include <typeindex>
#include <unordered_map>

#include "mock/mock-object.h"

class FakeInterface {
    void fake_interface_call() {}
};

class TestObject : public MockConfObject, public FakeInterface {
  public:
    using MockConfObject::MockConfObject;
};

TEST(TestGetInterface, TestGetInterfaceWithDeletion) {
    TestObject a {nullptr, "TestObjectA"};
    Stubs::instance_.sim_object_data_ret_ = &a;

    auto *interface = simics::detail::get_interface<FakeInterface>(
            a.obj().object());
    EXPECT_EQ(interface, dynamic_cast<FakeInterface*>(&a));
}

// this explains why we used the dynamic_cast directly in the utility.h
class IfaceBase {
  public:
    virtual ~IfaceBase() = default;
};

class TestGetInterfacePerf : public IfaceBase {
  public:
    TestGetInterfacePerf() {
        auto *iface = dynamic_cast<IfaceBase*>(this);
        m_[std::type_index(typeid(IfaceBase))] = reinterpret_cast<void*>(iface);
    }

    template <typename IFACE>
    IFACE *get_by_dynamic_cast() {
        return dynamic_cast<IFACE *>(this);
    }

    template <typename IFACE>
    IFACE *get_by_using_unordered_map() {
        return reinterpret_cast<IFACE *>(m_.find(typeid(IFACE))->second);
    }

    template <typename IFACE>
    IFACE *get_by_using_static_map() {
        static std::unordered_map<std::type_index, IFACE *> m;
        auto it = m.find(typeid(IFACE));
        if (it != m.end()) {
            return it->second;
        } else {
            auto *iface = dynamic_cast<IFACE*>(this);
            m[std::type_index(typeid(IFACE))] = iface;
            return iface;
        }
    }

    template <typename IFACE>
    IFACE *get_by_using_last_type_iface() {
        auto this_type = std::type_index(typeid(IFACE));
        if (this_type == last_type_) {
            return reinterpret_cast<IFACE *>(last_iface_);
        }
        last_type_ = this_type;
        auto *this_iface = dynamic_cast<IFACE *>(this);
        last_iface_ = reinterpret_cast<void *>(this_iface);
        return this_iface;
    }

    std::unordered_map<std::type_index, void *> m_;
    std::type_index last_type_ {typeid(void)};
    void *last_iface_ {nullptr};
};

// We wanted to know if the dynamic_cast as problematic and we put this
// test here to keep track of the implementation. Now we have deployed it
// and it's being used so perhaps not as useful anymore.
TEST(TestGetInterface, DISABLED_TestWhyGetInterfaceUseDynamicCast) {
    TestGetInterfacePerf t;
    auto *expected = dynamic_cast<IfaceBase *>(&t);
    IfaceBase *result = nullptr;

    auto start = std::chrono::high_resolution_clock::now();
    for (unsigned i = 0; i < 100000; ++i) {
        result = t.get_by_dynamic_cast<IfaceBase>();
    }
    auto stop = std::chrono::high_resolution_clock::now();
    EXPECT_EQ(result, expected);
    auto duration = std::chrono::duration_cast<std::chrono::microseconds>(
            stop - start);
    auto ms_using_dynamic_cast = duration.count();

    start = std::chrono::high_resolution_clock::now();
    for (unsigned i = 0; i < 100000; ++i) {
        result = t.get_by_using_unordered_map<IfaceBase>();
    }
    stop = std::chrono::high_resolution_clock::now();
    EXPECT_EQ(result, expected);
    duration = std::chrono::duration_cast<std::chrono::microseconds>(
            stop - start);
    auto ms_using_class_member_unordered_map = duration.count();

    start = std::chrono::high_resolution_clock::now();
    for (unsigned i = 0; i < 100000; ++i) {
        result = t.get_by_using_static_map<IfaceBase>();
    }
    stop = std::chrono::high_resolution_clock::now();
    EXPECT_EQ(result, expected);
    duration = std::chrono::duration_cast<std::chrono::microseconds>(
            stop - start);
    auto ms_using_static_unordered_map = duration.count();

    start = std::chrono::high_resolution_clock::now();
    for (unsigned i = 0; i < 100000; ++i) {
        result = t.get_by_using_last_type_iface<IfaceBase>();
    }
    stop = std::chrono::high_resolution_clock::now();
    EXPECT_EQ(result, expected);
    duration = std::chrono::duration_cast<std::chrono::microseconds>(
            stop - start);
    auto ms_using_last_type_iface = duration.count();

    auto ms_min = std::min({ms_using_dynamic_cast,
            ms_using_class_member_unordered_map,
            ms_using_static_unordered_map,
            ms_using_last_type_iface});
    // In most cases, ms_min equals to ms_using_dynamic_cast
    // but rarely not the case. Increase the threshold to 3%
    EXPECT_LE((double)ms_using_dynamic_cast, (double)ms_min * 1.03);
}
