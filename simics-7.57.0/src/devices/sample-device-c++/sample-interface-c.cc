// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2025 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include <simics/cc-api.h>

// include Simics C Signal interface
#include <simics/devs/signal.h>

//:: pre sample_iface_c {{
class SampleInterfaceC : public simics::ConfObject {
  public:
    using ConfObject::ConfObject;

    static void init_class(simics::ConfClass *cls);

    bool signal_raised {false};
};

static void signal_raise(conf_object_t *obj) {
    simics::from_obj<SampleInterfaceC>(obj)->signal_raised = true;
}

static void signal_lower(conf_object_t *obj) {
    simics::from_obj<SampleInterfaceC>(obj)->signal_raised = false;
}

void SampleInterfaceC::init_class(simics::ConfClass *cls) {
    cls->add(simics::Attribute("signal_raised", "b", "If signal is raised",
                               ATTR_CLS_VAR(SampleInterfaceC, signal_raised)));

    static const signal_interface_t signal_interface = {
        signal_raise,
        signal_lower
    };
    SIM_REGISTER_INTERFACE(*cls, signal, &signal_interface);
}
// }}

// coverity[global_init_order]
static simics::RegisterClassWithSimics<SampleInterfaceC> init_after_bank {
    "sample_device_cxx_interface_c",
    "sample C++ device with a C interface",
    "Sample C++ device with a C interface"
};
