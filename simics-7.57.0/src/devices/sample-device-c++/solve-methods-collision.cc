// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2010 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include <simics/device-api.h>
#include <simics/cc-api.h>

//:: pre solve_methods_collision {{
extern "C" {
SIM_INTERFACE(one) {
    void (*iface_fun)(conf_object_t*);
};
SIM_INTERFACE(another) {
    void (*iface_fun)(conf_object_t*);
};
}

namespace simics {
namespace iface {

class OneInterface {
  public:
    // Function override and implemented by user
    virtual void iface_fun() = 0;
};

class AnotherInterface {
  public:
    // Function override and implemented by user
    virtual void iface_fun() = 0;
};

}  // namespace iface
}  // namespace simics

class ImplementOne : public simics::iface::OneInterface {
    void iface_fun() override {
        // This is implementation for OneInterface
    }
};

class ImplementAnother : public simics::iface::AnotherInterface {
    void iface_fun() override {
        // This is implementation for AnotherInterface
    }
};

class MethodsCollision : public simics::ConfObject,
                         public ImplementOne,
                         public ImplementAnother {
  public:
    explicit MethodsCollision(simics::ConfObjectRef o)
        : simics::ConfObject(o) { }
};

// }}
