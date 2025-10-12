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

#include <simics/attr-value.h>
#include <simics/attribute-traits.h>

#include <gtest/gtest.h>
#include <simics/connect.h>

#include <climits>
#include <deque>
#include <initializer_list>
#include <list>
#include <map>
#include <set>
#include <string>
#include <tuple>
#include <type_traits>
#include <utility>
#include <vector>

#include "mock/stubs.h"
#include "mock/counted-int.h"

TEST(TestAttributeTraits, TestAttrIntegral) {
    attr_value_t attr;
    std::initializer_list<char> chars {CHAR_MIN, CHAR_MAX};
    for (char a_char : chars) {
        attr = simics::std_to_attr<>(a_char);
        EXPECT_EQ(SIM_attr_is_integer(attr), true);
        EXPECT_EQ(simics::attr_to_std<char>(attr), a_char);
    }

    std::initializer_list<signed char> signed_chars {SCHAR_MIN, SCHAR_MAX};
    for (signed char a_signed_char : signed_chars) {
        attr = simics::std_to_attr<>(a_signed_char);
        EXPECT_EQ(SIM_attr_is_int64(attr), true);
        EXPECT_EQ(simics::attr_to_std<signed char>(attr), a_signed_char);
    }

    unsigned char a_unsigned_char = UCHAR_MAX;
    attr = simics::std_to_attr<>(a_unsigned_char);
    EXPECT_EQ(SIM_attr_is_uint64(attr), true);
    EXPECT_EQ(simics::attr_to_std<unsigned char>(attr), a_unsigned_char);

    std::initializer_list<short> shorts {  // NOLINT(runtime/int)
        SHRT_MIN, SHRT_MAX};
    for (auto a_short : shorts) {
        attr = simics::std_to_attr<>(a_short);
        EXPECT_EQ(SIM_attr_is_int64(attr), true);
        EXPECT_EQ(simics::attr_to_std<short>(attr),  // NOLINT(runtime/int)
                  a_short);
    }

    unsigned short a_unsigned_short = USHRT_MAX;  // NOLINT(runtime/int)
    attr = simics::std_to_attr<>(a_unsigned_short);
    EXPECT_EQ(SIM_attr_is_uint64(attr), true);
    EXPECT_EQ(simics::attr_to_std<unsigned short>(attr),  // NOLINT(runtime/int)
              a_unsigned_short);

    std::initializer_list<int> ints {INT_MIN, INT_MAX};
    for (int a_int : ints) {
        attr = simics::std_to_attr<>(a_int);
        EXPECT_EQ(SIM_attr_is_int64(attr), true);
        EXPECT_EQ(simics::attr_to_std<int>(attr), a_int);
    }

    unsigned int a_unsigned_int = UINT_MAX;
    attr = simics::std_to_attr<>(a_unsigned_int);
    EXPECT_EQ(SIM_attr_is_uint64(attr), true);
    EXPECT_EQ(simics::attr_to_std<unsigned int>(attr), a_unsigned_int);

    std::initializer_list<long int> long_ints {  // NOLINT(runtime/int)
        LONG_MIN, LONG_MAX};
    for (auto a_long_int : long_ints) {
        attr = simics::std_to_attr<>(a_long_int);
        EXPECT_EQ(SIM_attr_is_int64(attr), true);
        EXPECT_EQ(simics::attr_to_std<long int>(attr),  // NOLINT(runtime/int)
                  a_long_int);
    }

    unsigned long int a_unsigned_long_int = ULONG_MAX;  // NOLINT(runtime/int)
    attr = simics::std_to_attr<>(a_unsigned_long_int);
    EXPECT_EQ(SIM_attr_is_uint64(attr), true);
    EXPECT_EQ(simics::attr_to_std<
              unsigned long int>(attr),  // NOLINT(runtime/int)
              a_unsigned_long_int);

    std::initializer_list<long long int>  // NOLINT(runtime/int)
        long_long_ints {LLONG_MIN, LLONG_MAX};
    for (auto a_long_long_int : long_long_ints) {
        attr = simics::std_to_attr<>(a_long_long_int);
        EXPECT_EQ(SIM_attr_is_int64(attr), true);
        EXPECT_EQ(simics::attr_to_std<
                  long long int>(attr),  // NOLINT(runtime/int)
                  a_long_long_int);
    }

    unsigned long long int a_unsigned_long_long_int =  // NOLINT(runtime/int)
        ULLONG_MAX;
    attr = simics::std_to_attr<>(a_unsigned_long_long_int);
    EXPECT_EQ(SIM_attr_is_uint64(attr), true);
    EXPECT_EQ(simics::attr_to_std<
              unsigned long long int>(attr),  // NOLINT(runtime/int)
              a_unsigned_long_long_int);

    // Test invalid type
    attr_value_t a_str_attr;
    a_str_attr.private_kind = Sim_Val_String;
    EXPECT_EQ(SIM_attr_is_integer(a_str_attr), false);
    EXPECT_THROW(simics::attr_to_std<int>(a_str_attr),
                 simics::detail::SetIllegalType);

    // Test invalid value
    auto a_unsigned_int_attr = simics::std_to_attr<>(a_unsigned_int);
    EXPECT_THROW(simics::attr_to_std<unsigned char>(a_unsigned_int_attr),
                 simics::detail::SetIllegalValue);
    auto a_int_attr = simics::std_to_attr<>(INT_MAX);
    EXPECT_THROW(simics::attr_to_std<char>(a_int_attr),
                 simics::detail::SetIllegalValue);
    a_int_attr = simics::std_to_attr<>(INT_MIN);
    EXPECT_THROW(simics::attr_to_std<char>(a_int_attr),
                 simics::detail::SetIllegalValue);
}

TEST(TestAttributeTraits, TestAttrFloat) {
    attr_value_t attr;
    float a_float = 1.5;
    attr = simics::std_to_attr<>(a_float);
    EXPECT_EQ(SIM_attr_is_floating(attr), true);
    EXPECT_EQ(simics::attr_to_std<float>(attr), a_float);

    double a_double = 12.435671123654328;
    attr = simics::std_to_attr<>(a_double);
    EXPECT_EQ(SIM_attr_is_floating(attr), true);
    EXPECT_EQ(simics::attr_to_std<double>(attr), a_double);

    // Test invalid type
    attr_value_t a_str_attr;
    a_str_attr.private_kind = Sim_Val_String;
    EXPECT_EQ(SIM_attr_is_floating(a_str_attr), false);
    EXPECT_THROW(simics::attr_to_std<float>(a_str_attr),
                 simics::detail::SetIllegalType);
    EXPECT_THROW(simics::attr_to_std<double>(a_str_attr),
                 simics::detail::SetIllegalType);
}

TEST(TestAttributeTraits, TestAttrObject) {
    simics::ConfObjectRef nil_obj;
    simics::AttrValue attr {simics::std_to_attr<>(nil_obj)};
    EXPECT_EQ(SIM_attr_is_nil(attr), true);
    EXPECT_EQ(simics::attr_to_std<simics::ConfObjectRef>(attr), nil_obj);

    auto conf_obj = reinterpret_cast<conf_object_t *>(uintptr_t{0xdeadbeef});
    Stubs::instance_.sim_object_name_[conf_obj] = "test";
    simics::ConfObjectRef a_obj {conf_obj};
    attr = simics::std_to_attr<>(a_obj);
    EXPECT_EQ(SIM_attr_is_object(attr), true);
    EXPECT_EQ(simics::attr_to_std<simics::ConfObjectRef>(attr), a_obj);

    a_obj.set_port_name("foo");
    attr = simics::std_to_attr<>(a_obj);
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    EXPECT_EQ(simics::attr_to_std<simics::ConfObjectRef>(attr), a_obj);

    // Test invalid type
    attr_value_t a_str_attr;
    a_str_attr.private_kind = Sim_Val_String;
    EXPECT_EQ(SIM_attr_is_object(a_str_attr), false);
    EXPECT_THROW(simics::attr_to_std<simics::ConfObjectRef>(a_str_attr),
                 simics::detail::SetIllegalType);
}

TEST(TestAttributeTraits, TestAttrString) {
    std::string empty_str = "";
    simics::AttrValue attr {simics::std_to_attr<>(empty_str)};
    EXPECT_EQ(SIM_attr_is_string(attr), true);
    EXPECT_EQ(simics::attr_to_std<std::string>(attr), empty_str);

    std::string a_str = "Hi! I am a string.";
    attr = simics::std_to_attr<>(a_str);
    EXPECT_EQ(SIM_attr_is_string(attr), true);
    EXPECT_EQ(simics::attr_to_std<std::string>(attr), a_str);

    const char *null_char_ptr = nullptr;
    attr = simics::std_to_attr<>(null_char_ptr);
    EXPECT_EQ(SIM_attr_is_nil(attr), true);
    EXPECT_EQ(simics::attr_to_std<const char *>(attr), null_char_ptr);

    const char *empty_char_ptr = "\n";
    attr = simics::std_to_attr<>(empty_char_ptr);
    EXPECT_EQ(SIM_attr_is_string(attr), true);
    EXPECT_STREQ(simics::attr_to_std<const char *>(attr), empty_char_ptr);

    const char *a_char_ptr = "Hi! I am a char.\n";
    attr = simics::std_to_attr<>(a_char_ptr);
    EXPECT_EQ(SIM_attr_is_string(attr), true);
    EXPECT_STREQ(simics::attr_to_std<const char *>(attr), a_char_ptr);

    // Test invalid type
    attr_value_t a_int_attr;
    a_int_attr.private_kind = Sim_Val_Integer;
    EXPECT_EQ(SIM_attr_is_string(a_int_attr), false);
    EXPECT_THROW(simics::attr_to_std<std::string>(a_int_attr),
                 simics::detail::SetIllegalType);
}

TEST(TestAttributeTraits, TestAttrBool) {
    for (bool a_bool : {true, false}) {
        simics::AttrValue attr {simics::std_to_attr<>(a_bool)};
        EXPECT_EQ(SIM_attr_is_boolean(attr), true);
        EXPECT_EQ(simics::attr_to_std<bool>(attr), a_bool);
    }

    // Test invalid type
    attr_value_t a_str_attr;
    a_str_attr.private_kind = Sim_Val_String;
    EXPECT_EQ(SIM_attr_is_boolean(a_str_attr), false);
    EXPECT_THROW(simics::attr_to_std<bool>(a_str_attr),
                 simics::detail::SetIllegalType);
}

TEST(TestAttributeTraits, TestAttrAttr) {
    attr_value_t attr;
    attr_value_t a_attr;
    a_attr.private_kind = Sim_Val_String;
    attr = simics::std_to_attr<>(a_attr);
    auto result = simics::attr_to_std<attr_value_t>(attr);
    constexpr bool is_same = std::is_same<decltype(a_attr),
                                          decltype(result)>::value;
    EXPECT_EQ(is_same, true);
    EXPECT_EQ(result.private_kind, a_attr.private_kind);
}

TEST(TestAttributeTraits, TestAttrData) {
    simics::detail::data_attribute empty_data;
    simics::AttrValue attr {simics::std_to_attr<>(empty_data)};
    EXPECT_EQ(SIM_attr_is_data(attr), true);
    EXPECT_EQ(simics::attr_to_std<simics::detail::data_attribute>(attr),
              empty_data);

    simics::detail::data_attribute a_data {1, 2, 3, 4, 5};
    attr = simics::std_to_attr<>(a_data);
    EXPECT_EQ(SIM_attr_is_data(attr), true);
    EXPECT_EQ(simics::attr_to_std<simics::detail::data_attribute>(attr),
              a_data);

    // Test invalid type
    attr_value_t a_str_attr;
    a_str_attr.private_kind = Sim_Val_String;
    EXPECT_EQ(SIM_attr_is_data(a_str_attr), false);
    EXPECT_THROW(
            simics::attr_to_std<simics::detail::data_attribute>(a_str_attr),
            simics::detail::SetIllegalType);
}

TEST(TestAttributeTraits, TestAttrContainer) {
    // Test empty container
    simics::AttrValue attr {simics::std_to_attr<>(std::vector<int>())};
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    EXPECT_EQ(SIM_attr_list_size(attr), 0);
    EXPECT_EQ(simics::attr_to_std<std::vector<int>>(attr).size(), 0);

    std::vector<int> a_int_vec {0xa, 0xb, 0xc};
    attr = simics::std_to_attr<>(a_int_vec);
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    EXPECT_EQ(simics::attr_to_std<std::vector<int>>(attr), a_int_vec);

    std::list<int> a_int_list {0xa, 0xb, 0xc};
    attr = simics::std_to_attr<>(a_int_list);
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    EXPECT_EQ(simics::attr_to_std<std::list<int>>(attr), a_int_list);

    std::pair<char, int> a_char_int_pair {0xa, 0xb};
    attr = simics::std_to_attr<>(a_char_int_pair);
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    auto pair_result = simics::attr_to_std<std::pair<char, int>>(attr);
    EXPECT_EQ(pair_result, a_char_int_pair);

    std::array<bool, 2> a_two_boolean_array {false, true};
    attr = simics::std_to_attr<>(a_two_boolean_array);
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    EXPECT_THROW((simics::attr_to_std<std::array<bool, 3>>(attr)),
                 simics::detail::SetIllegalType);
    auto array_result = simics::attr_to_std<std::array<bool, 2>>(attr);
    EXPECT_EQ(array_result, a_two_boolean_array);

    std::vector<std::vector<int>> a_int_vec_vec;
    a_int_vec_vec.push_back(a_int_vec);
    attr = simics::std_to_attr<>(a_int_vec_vec);
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    EXPECT_EQ(simics::attr_to_std<decltype(a_int_vec_vec)>(attr),
              a_int_vec_vec);

    std::pair<char, std::vector<int>> a_char_int_vec_pair {1, {2}};
    attr = simics::std_to_attr<>(a_char_int_vec_pair);
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    auto pair_vec_result = simics::attr_to_std<
        decltype(a_char_int_vec_pair)>(attr);
    EXPECT_EQ(pair_vec_result, a_char_int_vec_pair);

    std::map<int, bool> a_str_bool_map {
        {0, true}, {1, false},
    };
    attr = simics::std_to_attr<>(a_str_bool_map);
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    auto map_result = simics::attr_to_std<
        decltype(a_str_bool_map)>(attr);
    EXPECT_EQ(map_result, a_str_bool_map);

    std::array<simics::ConfObjectRef, 1> a_one_obj_array {nullptr};
    attr = simics::std_to_attr<>(a_one_obj_array);
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    auto array2_result = simics::attr_to_std<std::array<simics::ConfObjectRef,
                                                        1>>(attr);
    EXPECT_EQ(array2_result, a_one_obj_array);

    std::tuple<char, int, bool> a_char_int_bool_tuple {0xa, 2, true};
    attr = simics::std_to_attr<>(a_char_int_bool_tuple);
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    EXPECT_EQ(SIM_attr_list_size(attr), 3);
    auto tuple_result = simics::attr_to_std<std::tuple<char, int, bool>>(attr);
    EXPECT_EQ(tuple_result, a_char_int_bool_tuple);

    std::set<float> a_float_set {1.2f, 2.34f};
    attr = simics::std_to_attr<>(a_float_set);
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    EXPECT_EQ(SIM_attr_list_size(attr), 2);
    auto set_result = simics::attr_to_std<std::set<float>>(attr);
    EXPECT_EQ(set_result, a_float_set);

    // Test raw array
    int a_raw_array[5] {0, 1, 2, 3, 4};
    attr = simics::std_to_attr<>(a_raw_array);
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    // Cannot return a raw array, use std::array instead
    auto raw_array_result = simics::attr_to_std<std::array<int, 5>>(attr);
    for (std::size_t i = 0; i < 5; ++i) {
        EXPECT_EQ(raw_array_result[i], a_raw_array[i]);
    }

    // Test invalid type
    attr_value_t a_str_attr;
    a_str_attr.private_kind = Sim_Val_String;
    EXPECT_EQ(SIM_attr_is_list(a_str_attr), false);
    EXPECT_THROW(
            simics::attr_to_std<std::vector<std::vector<int>>>(a_str_attr),
            simics::detail::SetIllegalType);
}

TEST(TestAttributeTraits, TestAttrEnum) {
    attr_value_t attr;
    enum class Foo { a, b = 10 };

    Foo a_enum { Foo::b };
    attr = simics::std_to_attr<>(a_enum);
    EXPECT_EQ(SIM_attr_is_integer(attr), true);
    EXPECT_EQ(simics::attr_to_std<Foo>(attr), a_enum);

    // There is no validation on the enum. It is treated as its
    // underlying C++ type
    std::underlying_type_t<Foo> a_value = 100;
    EXPECT_EQ(a_value, 100);
    attr = simics::std_to_attr<>(a_value);
    EXPECT_EQ(simics::attr_to_std<Foo>(attr),
              static_cast<Foo>(a_value));
}

struct TestConnect : public simics::ConnectBase {
    bool set(const simics::ConfObjectRef &o) override {
        return true;
    }
};

TEST(TestAttributeTraits, TestAttrConnectBase) {
    simics::ConfObjectRef nil_obj;
    TestConnect connect;
    simics::AttrValue attr {simics::std_to_attr<>(connect)};
    EXPECT_EQ(SIM_attr_is_nil(attr), true);
    EXPECT_EQ(simics::attr_to_std<simics::ConfObjectRef>(attr), nil_obj);
    EXPECT_EQ(simics::attr_to_std<TestConnect>(attr), connect);

    std::array<TestConnect, 2> connects;
    attr = simics::std_to_attr<>(connects);
    EXPECT_EQ(SIM_attr_is_list(attr), true);
    auto array_result = simics::attr_to_std<std::array<TestConnect, 2>>(attr);
    EXPECT_EQ(array_result, connects);
}

// Test that the attr_from_std_helper does not make extra data copy
TEST(TestAttributeTraits, TestNoExtraCopy) {
    CountedInt::resetCounters();

    CountedInt ci;
    simics::detail::attr_from_std_helper<CountedInt>::f(ci);
    EXPECT_EQ(CountedInt::getCopyConstructorCalls(), 0);
    EXPECT_EQ(CountedInt::getCopyAssignmentCalls(), 0);

    std::array<CountedInt, 4> ci_array;
    simics::AttrValue attr {
        simics::detail::attr_from_std_helper<decltype(ci_array)>::f(ci_array)
    };
    EXPECT_EQ(CountedInt::getCopyConstructorCalls(), 0);
    EXPECT_EQ(CountedInt::getCopyAssignmentCalls(), 0);

    std::vector<CountedInt> ci_vector(4);
    attr = simics::detail::attr_from_std_helper<decltype(ci_vector)>::f(
            ci_vector);
    EXPECT_EQ(CountedInt::getCopyConstructorCalls(), 0);
    EXPECT_EQ(CountedInt::getCopyAssignmentCalls(), 0);

    std::list<CountedInt> ci_list(4);
    attr = simics::detail::attr_from_std_helper<decltype(ci_list)>::f(ci_list);
    EXPECT_EQ(CountedInt::getCopyConstructorCalls(), 0);
    EXPECT_EQ(CountedInt::getCopyAssignmentCalls(), 0);

    std::deque<CountedInt> ci_deque(4);
    attr = simics::detail::attr_from_std_helper<decltype(ci_deque)>::f(
            ci_deque);
    EXPECT_EQ(CountedInt::getCopyConstructorCalls(), 0);
    EXPECT_EQ(CountedInt::getCopyAssignmentCalls(), 0);

    std::pair<int, CountedInt> ci_pair{0, 0};
    attr = simics::detail::attr_from_std_helper<decltype(ci_pair)>::f(ci_pair);
    EXPECT_EQ(CountedInt::getCopyConstructorCalls(), 0);
    EXPECT_EQ(CountedInt::getCopyAssignmentCalls(), 0);

    std::map<int, CountedInt> ci_map;
    ci_map.emplace(0, 4);
    attr = simics::detail::attr_from_std_helper<decltype(ci_map)>::f(ci_map);
    EXPECT_EQ(CountedInt::getCopyConstructorCalls(), 0);
    EXPECT_EQ(CountedInt::getCopyAssignmentCalls(), 0);

    std::tuple<int, CountedInt> ci_tuple {0, 4};
    attr = simics::detail::attr_from_std_helper<decltype(ci_tuple)>::f(
            ci_tuple);
    EXPECT_EQ(CountedInt::getCopyConstructorCalls(), 0);
    EXPECT_EQ(CountedInt::getCopyAssignmentCalls(), 0);
}
