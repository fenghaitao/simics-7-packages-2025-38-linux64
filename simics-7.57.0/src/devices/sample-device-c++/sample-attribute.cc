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

#include <simics/cc-api.h>
#include <simics/c++/devs/signal.h>
#include <simics/c++/devs/memory-space.h>

#include <array>
#include <iostream>
#include <map>
#include <string>
#include <utility>
#include <vector>

// Define init_local to be our class' special init function. Needed to make
// documentation look correct (i.e. using init_local) but avoiding collision
// with other classes in the same module.
#define init_local init_sample_attribute_class_member_variable

//:: pre attribute_class_member_variable {{
class SampleAttributeClassMemberVariable : public simics::ConfObject {
  public:
    using ConfObject::ConfObject;

    static void init_class(simics::ConfClass *cls) {
        cls->add(simics::Attribute(
                         "flags", "[bb]", "Two boolean flags in an array",
                         ATTR_CLS_VAR(SampleAttributeClassMemberVariable,
                                      flags)));
    }

    std::array<bool, 2> flags {false, false};
};

static simics::RegisterClassWithSimics<SampleAttributeClassMemberVariable>
// coverity[global_init_order]
init_class_member_variable {
    "sample_device_cxx_attribute_class_member_variable",
    "sample C++ attr device use cls member variable",
    "Sample C++ attribute device use cls member variable"
};
// }}

//:: pre attribute_with_nested_stl_container {{
class SampleAttributeNestedStlContainer : public simics::ConfObject {
  public:
    using ConfObject::ConfObject;

    static void init_class(simics::ConfClass *cls) {
        cls->add(simics::Attribute(
                    "id_strs",
                    ATTR_TYPE_STR(SampleAttributeNestedStlContainer::id_strs),
                    "a map where each ID maps to a list of strings",
                    ATTR_CLS_VAR(SampleAttributeNestedStlContainer,
                                 id_strs)));
    }

    std::map<int, std::vector<std::string>> id_strs;
};
// }}

static simics::RegisterClassWithSimics<SampleAttributeNestedStlContainer>
// coverity[global_init_order]
init_nested_stl_container {
    "sample_device_cxx_attribute_nested_stl_container",
    "sample C++ attr device with nested STL container",
    "Sample C++ attribute device with nested STL container"
};

//:: pre attribute_class_member_method {{
class SampleAttributeClassMemberMethod : public simics::ConfObject {
  public:
    using ConfObject::ConfObject;

    static void init_class(simics::ConfClass *cls) {
        cls->add(simics::Attribute(
                         "value", "i", "A value.",
                         ATTR_GETTER(SampleAttributeClassMemberMethod,
                                     get_value),
                         ATTR_SETTER(SampleAttributeClassMemberMethod,
                                     set_value),
                         Sim_Attr_Required));
    }

    int get_value() const;
    void set_value(const int &v);

  private:
    int value {0};
};

// ...

int SampleAttributeClassMemberMethod::get_value() const {
    return value;
}

void SampleAttributeClassMemberMethod::set_value(const int &v) {
    if (v < 256) {
        value = v;
    } else {
        throw std::runtime_error("Too large value");
    }
}

static simics::RegisterClassWithSimics<SampleAttributeClassMemberMethod>
// coverity[global_init_order]
init_class_member_method {
    "sample_device_cxx_attribute_class_member_method",
    "sample C++ attr device use cls member method",
    "Sample C++ attribute device use cls member method"
};
// }}

//:: pre sample_attribute_global_method {{
class SampleAttributeGlobalMethod : public simics::ConfObject {
  public:
    using ConfObject::ConfObject;

    static void init_class(simics::ConfClass *cls);

    std::string name;
    size_t id {0};
};

// ...

std::pair<std::string, size_t> get_name_and_id(
        const SampleAttributeGlobalMethod &obj) {
    return {obj.name, obj.id};
}

void set_name_and_id(SampleAttributeGlobalMethod &obj,  // NOLINT
                     const std::pair<std::string, size_t> &name_and_id) {
    std::tie(obj.name, obj.id) = name_and_id;
}

void SampleAttributeGlobalMethod::init_class(simics::ConfClass *cls) {
    cls->add(simics::Attribute("name_and_id", "[si]", "A pair of a name and id",
                               ATTR_GETTER(get_name_and_id),
                               ATTR_SETTER(set_name_and_id)));
}

static simics::RegisterClassWithSimics<SampleAttributeGlobalMethod>
// coverity[global_init_order]
init_global_method {
    "sample_device_cxx_attribute_global_method",
    "sample C++ attr device use global method",
    "Sample C++ attribute device use global method"
};
// }}

//:: pre sample_attribute_custom_method {{
// The buffer class is used as an example to show how to register
// a custom type Simics attribute. It is not a reference
// implementation of how to write a custom buffer class.
// coverity[rule_of_three_violation:FALSE]
class buffer {
  public:
    buffer(const unsigned char *d, size_t size) {
        aux_.assign(d, d + size);
    }
    buffer(const buffer &other) {
        aux_.assign(other.data(), other.data() + other.size());
    }
    buffer& operator=(const buffer &other) = delete;
    virtual ~buffer() = default;

    const unsigned char *data() const { return aux_.data(); }
    int size() const { return aux_.size(); }

  private:
    std::vector<unsigned char> aux_;
};

class SampleAttributeCustomMethod : public simics::ConfObject {
  public:
    using ConfObject::ConfObject;
    static void init_class(simics::ConfClass *cls);

    buffer get_blob() const;
    void set_blob(const buffer &v);

  private:
    unsigned char blob_[1024] {};
};

buffer SampleAttributeCustomMethod::get_blob() const {
    return buffer(blob_, sizeof blob_);
}

void SampleAttributeCustomMethod::set_blob(const buffer &v) {
    if (v.size() == sizeof blob_) {
        memcpy(blob_, v.data(), v.size());
    } else {
        throw std::runtime_error { "Wrong size of data buffer" };
    }
}

namespace {
attr_value_t get_blob_helper(conf_object_t *obj) {
    auto *o = simics::from_obj<SampleAttributeCustomMethod>(obj);
    return SIM_make_attr_data(1024, o->get_blob().data());
}

set_error_t set_blob_helper(conf_object_t *obj, attr_value_t *val) {
    auto *o = simics::from_obj<SampleAttributeCustomMethod>(obj);
    try {
        o->set_blob(buffer(SIM_attr_data(*val), SIM_attr_data_size(*val)));
    } catch (const std::exception &e) {
        SIM_LOG_INFO(1, o->obj(), 0, "%s", e.what());
        return Sim_Set_Illegal_Value;
    }
    return Sim_Set_Ok;
}
}  // namespace

void SampleAttributeCustomMethod::init_class(simics::ConfClass *cls) {
    cls->add(simics::Attribute("blob", "d", "Some data",
                               &get_blob_helper, &set_blob_helper));
}

static simics::RegisterClassWithSimics<SampleAttributeCustomMethod>
// coverity[global_init_order]
init_custom_method {
    "sample_device_cxx_attribute_custom_method",
    "sample C++ attr device use custom method",
    "Sample C++ attribute device use custom method"
};
// }}

class SampleAttributePseudo : public simics::ConfObject {
  public:
    using ConfObject::ConfObject;
    static void init_class(simics::ConfClass *cls);

    void trigger_test(bool v);
};

void SampleAttributePseudo::trigger_test(bool trigger) {
    if (trigger) {
        SIM_LOG_INFO(1, obj(), 0, "Test triggered");
    }
}

void SampleAttributePseudo::init_class(simics::ConfClass *cls) {
    // Pseudo attribute for triggering some side effects
    cls->add(simics::Attribute(
                     "test_trigger", "b",
                     "When being set, trigger some action",
                     nullptr,
                     ATTR_SETTER(SampleAttributePseudo, trigger_test),
                     Sim_Attr_Pseudo));
}

// coverity[global_init_order]
static simics::RegisterClassWithSimics<SampleAttributePseudo> init_pseudo {
    "sample_device_cxx_attribute_pseudo",
    "sample C++ attr device with pseudo attribute",
    "Sample C++ attribute device with pseudo attribute"
};

//:: pre sample_attribute_specialized_converter {{
struct MyType {
    uint64_t ull;
    std::string message;
    simics::ConfObjectRef some_object;
};

class SampleAttributeSpecializedConverter : public simics::ConfObject {
  public:
    using ConfObject::ConfObject;
    static void init_class(simics::ConfClass *cls) {
        cls->add(simics::Attribute("my_type", "[iso|n]",
                                   "An attribute of MyType",
                                   ATTR_CLS_VAR(
                                           SampleAttributeSpecializedConverter,
                                           my_type)));
    }

    MyType my_type;
};

// Specialize the template converter
namespace simics {
template <>
inline MyType attr_to_std<MyType>(attr_value_t src) {
    MyType result;
    result.ull = attr_to_std<uint64>(SIM_attr_list_item(src, 0));
    result.message = attr_to_std<std::string>(SIM_attr_list_item(src, 1));
    result.some_object = attr_to_std<ConfObjectRef>(SIM_attr_list_item(src, 2));
    return result;
}

template <>
inline attr_value_t std_to_attr<MyType>(const MyType &src) {
    attr_value_t result = SIM_alloc_attr_list(3);
    SIM_attr_list_set_item(&result, 0, std_to_attr<uint64>(src.ull));
    SIM_attr_list_set_item(&result, 1, std_to_attr<std::string>(src.message));
    SIM_attr_list_set_item(&result, 2,
                           std_to_attr<ConfObjectRef>(src.some_object));
    return result;
}
}  // namespace simics

static simics::RegisterClassWithSimics<SampleAttributeSpecializedConverter>
// coverity[global_init_order]
init_specialized_converter {
    "sample_device_cxx_attribute_specialized_converter",
    "sample C++ attr device with specialized converter",
    "Sample C++ attribute device with specialized converter"
};
// }}

/**
 * @class SampleAttributeClassAttribute
 * @brief A class that represents a sample attribute with a static instance
 *        counter.
 *
 * This class keeps track of the number of created instances using a static
 * member variable.
 */
//:: pre SampleAttributeClassAttribute {{
class SampleAttributeClassAttribute : public simics::ConfObject {
  public:
    explicit SampleAttributeClassAttribute(simics::ConfObjectRef obj)
        : ConfObject(obj) {
        ++instance_count_;
    }
    virtual ~SampleAttributeClassAttribute() {
        --instance_count_;
    }

    static attr_value_t get_instance_count(conf_class_t *cls) {
        return simics::std_to_attr<int>(instance_count_);
    }

    static void init_class(simics::ConfClass *cls) {
        cls->add(simics::ClassAttribute("instance_count", "i",
                                        "Instance count of the class",
                                        get_instance_count, nullptr,
                                        Sim_Attr_Pseudo));
    }

  private:
    static int instance_count_;
};

int SampleAttributeClassAttribute::instance_count_ = 0;

static simics::RegisterClassWithSimics<SampleAttributeClassAttribute>
// coverity[global_init_order]
init_class_attribute {
    "sample_device_cxx_attribute_class_attribute",
    "sample C++ attr device with class attribute",
    "Sample C++ attribute device with class attribute"
};
// }}
