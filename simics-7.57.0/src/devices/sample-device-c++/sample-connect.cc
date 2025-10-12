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

//:: pre sample_connect {{
#include <simics/cc-api.h>
#include <simics/c++/devs/signal.h>
#include <simics/c++/devs/interrupt.h>

class SampleConnect : public simics::ConfObject {
  public:
    using ConfObject::ConfObject;

    // use the connect after all objects are finalized
    void objects_finalized() override;

    static void init_class(simics::ConfClass *cls);

    simics::Connect<simics::iface::SimpleInterruptInterface,
                    simics::iface::SignalInterface> irq_dev {
        simics::ConnectConfig::optional<simics::iface::SignalInterface>()
    };
};
// }}

//:: pre sample_connect_attribute {{
void SampleConnect::init_class(simics::ConfClass *cls) {
    cls->add(simics::Attribute("irq_dev", "o|n",
                               "IRQ device",
                               ATTR_CLS_VAR(SampleConnect, irq_dev)));
}
// }}

//:: pre sample_connect_use_signal {{
void SampleConnect::objects_finalized() {
    if (irq_dev) {
        if (irq_dev.iface<simics::iface::SignalInterface>().get_iface()) {
            irq_dev.iface<simics::iface::SignalInterface>().signal_raise();
        } else {
            irq_dev.iface().interrupt(0);
        }
    }
}
// }}

#include <simics/c++/devs/memory-space.h>

//:: pre SampleConnectToDescendant {{
class SampleConnectToDescendant : public simics::ConfObject {
  public:
    using ConfObject::ConfObject;
    static constexpr const char * PORT_MEMORY_SPACE = "port.memory_space";
    static void init_class(simics::ConfClass *cls);

    simics::ConnectToDescendant<
        simics::iface::MemorySpaceInterface> target_mem_space {
        this, PORT_MEMORY_SPACE
    };
};

void SampleConnectToDescendant::init_class(simics::ConfClass *cls) {
    // Register the port object as default target memory space
    SIM_register_port(*cls, PORT_MEMORY_SPACE,
                      SIM_get_class("memory-space"),
                      "Target memory space as descendant");
    // It can also be optionally connected to other memory-space
    cls->add(simics::Attribute("target_mem_space", "o|n",
                               "Target port to a memory space",
                               ATTR_CLS_VAR(SampleConnectToDescendant,
                                            target_mem_space)));
}
// }}

//:: pre SampleConnectMapTarget {{
class SampleConnectMapTarget : public simics::ConfObject {
  public:
    using ConfObject::ConfObject;

    static void init_class(simics::ConfClass *cls) {
        cls->add(simics::Attribute("map_target", "o|n",
                                   "Map Target",
                                   ATTR_CLS_VAR(SampleConnectMapTarget,
                                                map_target)));
    }

    simics::MapTargetConnect map_target {this->obj()};
};
// }}

// coverity[global_init_order]
static simics::RegisterClassWithSimics<SampleConnect> init_connect {
    "sample_device_cxx_connect",
    "sample C++ device with a connect",
    "Sample C++ device with a connect"
};
static simics::RegisterClassWithSimics<SampleConnectToDescendant>
// coverity[global_init_order]
init_connect_to_descendant {
    "sample_device_cxx_connect_to_descendant",
    "sample C++ device with a ConnectToDescendant",
    "Sample C++ device with a ConnectToDescendant"
};
static simics::RegisterClassWithSimics<SampleConnectMapTarget>
// coverity[global_init_order]
init_connect_map_target {
    "sample_device_cxx_connect_map_target",
    "sample C++ device with a MapTargetConnect",
    "Sample C++ device with a MapTargetConnect"
};
