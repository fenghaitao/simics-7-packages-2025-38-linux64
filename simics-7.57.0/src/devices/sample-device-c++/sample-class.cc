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

// Define init_local to be our class' special init function. Needed to make
// documentation look correct (i.e. with init_local) but avoiding collision
// with other classes in the same module.
#define init_local init_sample_class_with_init_class

//:: pre SampleClass/definition {{
#include <simics/cc-api.h>

class SampleClass : public simics::ConfObject {
  public:
    using ConfObject::ConfObject;

    // This static method is invoked from simics::make_class
    static void init_class(simics::ConfClass *cls) {
        // register the class properties like attribute, port, event,
        // interface and logging settings
    }
};
// }}

//:: pre SampleClassWithInitClass/init_local {{
extern "C" void init_local() {
    simics::make_class<SampleClass>(
        // Simics class name
        "sample_device_cxx_class_with_init_class",
        // short description
        "sample C++ class device with init_class",
        // class documentation
        "This is a sample Simics device written in C++.");
}
// }}

#undef init_local
#define init_local init_sample_class_without_init_class

//:: pre SampleClassWithoutInitClass/init_local {{
extern "C" void init_local() {
    auto cls = simics::make_class<SampleClass>(
        "sample_device_cxx_class_without_init_class",
        "sample C++ class device without init_class",
        "This is a sample Simics device written in C++.");

    // use cls to register the class properties like attribute, port,
    // event, interface and logging settings
}
// }}

//:: pre SampleClassWithoutInitLocal {{
// coverity[global_init_order]
static simics::RegisterClassWithSimics<SampleClass> init {
    "sample_device_cxx_class_without_init_local",
    "sample C++ class device without init_local",
    "This is a sample Simics device written in C++."
};
// }}
