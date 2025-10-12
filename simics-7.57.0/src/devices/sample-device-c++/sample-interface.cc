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

// include Simics C++ Signal interface
#include <simics/c++/devs/signal.h>

//:: pre user_defined_interface {{
// This c++ file is generated from sample-interface.h by gen_cc_interface.py
#include "c++/sample-interface.h"
// }}

//:: pre sample_iface_decl {{
class SampleInterface : public simics::ConfObject,
                        public simics::iface::SignalInterface {
  public:
    using ConfObject::ConfObject;

    static void init_class(simics::ConfClass *cls);

    // simics::iface::SignalInterface
    void signal_raise() override;
    void signal_lower() override;

    bool signal_raised {false};
};
// }}

//:: pre sample_iface_impl {{
void SampleInterface::signal_raise() {
    signal_raised = true;
}

void SampleInterface::signal_lower() {
    signal_raised = false;
}

// }}

//:: pre sample_iface_reg {{
void SampleInterface::init_class(simics::ConfClass *cls) {
    cls->add(simics::Attribute("signal_raised", "b", "If signal is raised",
                               ATTR_CLS_VAR(SampleInterface, signal_raised)));

    cls->add(simics::iface::SignalInterface::Info());
}
// }}

class SampleUserInterface : public simics::ConfObject,
                            public simics::iface::SampleInterface {
  public:
    using ConfObject::ConfObject;

    static void init_class(simics::ConfClass *cls);

    // simics::iface::SampleInterface
    void simple_method(int arg) override;
    void object_method(conf_object_t *arg) override {}

    int simple_method_cnt {0};
};

void SampleUserInterface::simple_method(int arg) {
    ++simple_method_cnt;
}

void SampleUserInterface::init_class(simics::ConfClass *cls) {
    cls->add(simics::Attribute(
                 "simple_method_cnt", "i",
                 "Received simple_method method calls",
                 ATTR_CLS_VAR(SampleUserInterface, simple_method_cnt)));

    cls->add(simics::iface::SampleInterface::Info());
}

//:: pre sample_iface_with_custom_info {{
class SampleInterfaceWithCustomInfo : public SampleInterface {
  public:
    using SampleInterface::SampleInterface;
    using SampleInterface::signal_raise;
    using SampleInterface::signal_lower;

    static void init_class(simics::ConfClass* cls);

    static void signal_raise(conf_object_t *obj) {
        return simics::from_obj<SampleInterfaceWithCustomInfo>(
                obj)->signal_raise();
    }

    static void signal_lower(conf_object_t *obj) {
        return simics::from_obj<SampleInterfaceWithCustomInfo>(
                obj)->signal_lower();
    }

    class CustomSignalInfo : public simics::iface::SignalInterface::Info {
      public:
        const interface_t *cstruct() const override {
            static constexpr simics::iface::SignalInterface::ctype funcs {
                signal_raise,
                signal_lower,
            };
            return &funcs;
        }
    };
};
// }}

void SampleInterfaceWithCustomInfo::init_class(simics::ConfClass *cls) {
    cls->add(simics::Attribute("signal_raised", "b", "If signal is raised",
                               ATTR_CLS_VAR(SampleInterfaceWithCustomInfo,
                                            signal_raised)));

    cls->add(SampleInterfaceWithCustomInfo::CustomSignalInfo());
}

// coverity[global_init_order]
static simics::RegisterClassWithSimics<SampleInterface> init_interface {
    "sample_device_cxx_interface",
    "sample C++ device with an interface",
    "Sample C++ device with an interface"
};
static simics::RegisterClassWithSimics<SampleUserInterface>
// coverity[global_init_order]
init_user_interface {
    "sample_device_cxx_user_interface",
    "sample C++ device with a user interface",
    "Sample C++ device with a user interface"
};
static simics::RegisterClassWithSimics<SampleInterfaceWithCustomInfo>
// coverity[global_init_order]
init_interface_with_custom_info {
    "sample_device_cxx_interface_with_custom_info",
    "sample C++ interface device using custom info",
    "Sample C++ interface device using custom info"
};
