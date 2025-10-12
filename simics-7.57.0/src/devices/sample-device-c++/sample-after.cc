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
#include <string>

//:: pre SampleAfter {{

// Log on sim object. Used from global function since no other Simics
// objects can be used there.
void logOnSim(const std::string &msg) {
    static auto sim_obj = SIM_get_object("sim");
    SIM_LOG_INFO_STR(1, sim_obj, 0, msg);
}

void twoStrsArgumentGlobalFunction(std::string s1, std::string s2) {
    logOnSim("Hello, I am twoStrsArgumentGlobalFunction(" + \
             s1 + ", " + s2 + ")");
}

class SampleAfter : public simics::ConfObject,
                    public simics::EnableAfterCall<SampleAfter> {
  public:
    explicit SampleAfter(simics::ConfObjectRef obj)
        : ConfObject(obj), simics::EnableAfterCall<SampleAfter>(this) {
    }

    void cancel_after(bool trigger) {
        if (trigger) {
            // cancel all suspended method calls associated with
            // this object
            cancel_all();
        }
    }

    void oneUint64ArgumentClassFunction(uint64_t a) {
        logOnSim("Hello, I am oneUint64ArgumentClassFunction("
                 + std::to_string(a) + ")");
    }

    void finalize() override {
        if (SIM_is_restoring_state(obj())) {
            return;
        }

        AFTER_CALL(this, 1.0, &twoStrsArgumentGlobalFunction,
                   std::string("abc"), std::string("def"));
        AFTER_CALL(this, 2.0, &SampleAfter::oneUint64ArgumentClassFunction,
                   obj(), one_uint64_);
    }

    static void init_class(simics::ConfClass *cls);

  private:
    uint64_t one_uint64_ {0xdeadbeef};
};

void SampleAfter::init_class(simics::ConfClass *cls) {
    // Registering functions for later after call invocation
    REGISTER_AFTER_CALL(&twoStrsArgumentGlobalFunction);
    REGISTER_AFTER_CALL(&SampleAfter::oneUint64ArgumentClassFunction);

    // Register the after event on SampleAfter with default name "after_event"
    cls->add(SampleAfter::afterEventInfo());

    cls->add(simics::Attribute(
                     "cancel_after", "b",
                     "When being set, cancel all after callbacks",
                     nullptr,
                     ATTR_SETTER(SampleAfter, cancel_after),
                     Sim_Attr_Pseudo));
}
// }}

// coverity[global_init_order]
static simics::RegisterClassWithSimics<SampleAfter> init_after {
    "sample_device_cxx_after", "sample C++ after device", "No description"
};
