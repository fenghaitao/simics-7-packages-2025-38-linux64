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

//:: pre port_use_confobject {{
// An example class derived from ConfObject, designed to be used as a port
// object for SamplePortDeviceUseConfObject
class SamplePortUseConfObject : public simics::ConfObject,
                                public simics::iface::SignalInterface {
  public:
    using ConfObject::ConfObject;

    static void init_class(simics::ConfClass *cls) {
        cls->add(simics::iface::SignalInterface::Info());
        cls->add(simics::Attribute(
                         "raised", "b",
                         "Return if signal is raised or not",
                         ATTR_GETTER(SamplePortUseConfObject, raised_),
                         nullptr,
                         Sim_Attr_Pseudo));
    }

    // simics::iface::SignalInterface
    void signal_raise() override {raised_ = true;}
    void signal_lower() override {raised_ = false;}

  private:
    bool raised_ {false};
};

class SamplePortDeviceUseConfObject : public simics::ConfObject {
  public:
    using ConfObject::ConfObject;

    static void init_class(simics::ConfClass *cls) {
        auto port = simics::make_class<SamplePortUseConfObject>(
                cls->name() + ".sample", "sample C++ port", "");
        // Register port class with the device class
        cls->add(port, "port.sample");
    }
};

static simics::RegisterClassWithSimics<SamplePortDeviceUseConfObject>
// coverity[global_init_order]
init_port_use_confobject {
    "sample_device_cxx_port_use_confobject",
    "a C++ test device",
    "No description"
};
// }}

//:: pre port_use_port {{
class SamplePortDeviceUsePort : public simics::ConfObject {
  public:
    using ConfObject::ConfObject;

    static void init_class(simics::ConfClass *cls) {
        auto port = simics::make_class<SamplePort>(
                cls->name() + ".sample", "sample C++ port", "");
        port->add(simics::iface::SignalInterface::Info());

        // Registers a port class with an array-like naming convention.
        // Upon device creation, two port objects are instantiated with names:
        // <dev_name>.port.sample[0] and <dev_name>.port.sample[1].
        cls->add(port, "port.sample[2]");

        cls->add(simics::Attribute("state", "i", "A value",
                                   ATTR_CLS_VAR(SamplePortDeviceUsePort,
                                                state)));
    }

    // Define a C++ port class which implements the signal interface
    class SamplePort : public simics::Port<SamplePortDeviceUsePort>,
                       public simics::iface::SignalInterface {
      public:
        using Port<SamplePortDeviceUsePort>::Port;

        // simics::iface::SignalInterface
        void signal_raise() override;
        void signal_lower() override;
    };

  private:
    // An integer simulates the signal state, each bit represents one signal
    int state {0};
};

void SamplePortDeviceUsePort::SamplePort::signal_raise() {
    // method index() returns the index of the port object array
    if (index() == 0) {
        // method parent() returns pointer to the parent C++ class
        parent()->state |= 1;
    } else {
        parent()->state |= 2;
    }
}

void SamplePortDeviceUsePort::SamplePort::signal_lower() {
    if (index() == 0) {
        parent()->state &= 2;
    } else {
        parent()->state &= 1;
    }
}

static simics::RegisterClassWithSimics<SamplePortDeviceUsePort>
// coverity[global_init_order]
init_port_use_port {
    "sample_device_cxx_port_use_port",
    "a C++ test device",
    "No description"
};
// }}
