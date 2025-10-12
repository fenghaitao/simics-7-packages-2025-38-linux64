/*
  sample-device-mixed.cc - sample code for a mixed DML/C/C++ Simics device

  © 2010 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include "sample-device-mixed.h"

uint64 calculate_value_in_cc(uint64 v) {
    return v + 4712;
}

uint64 calculate_value_in_cc(float v) {
    return v + 4713;
}

class MyClass {
  public:
    virtual ~MyClass() = default;

    // Call myinterface on obj
    virtual void foo(conf_object_t *obj) {
        auto *iface = static_cast<const myinterface_interface_t*>(
        SIM_c_get_interface(obj, "myinterface"));
        
        ASSERT(iface);
        iface->one(obj);
        iface->two(obj, 4712);
    }
};

/*
 * Function wrapper to call C++ functions from DML
 */
// Wrapper for overloaded function
uint64 calculate_value_in_cc_int(uint64 v) { return calculate_value_in_cc(v); }
uint64 calculate_value_in_cc_float(float v) { return calculate_value_in_cc(v); }

// Wrapper for class member function
lang_void *create_myclass() {
    return new MyClass;
}
void free_myclass(lang_void *c) {
    delete static_cast<MyClass*>(c);
}
void myclass_foo(lang_void *c, conf_object_t *obj) {
    static_cast<MyClass*>(c)->foo(obj);
}
