// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2023 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include <simics/cc-api.h>

//:: pre SampleEvent {{
class SampleEvent : public simics::ConfObject {
  public:
    using ConfObject::ConfObject;

    void finalize() override {
        // Post the user_event after 1 second
        user_event.post(1.0);
    }

    class UserTimeEvent : public simics::TimeEvent<SampleEvent> {
      public:
        explicit UserTimeEvent(simics::ConfObject *obj)
            : TimeEvent(obj, "user_event") {}

        // Callback method invoked when the event is triggered
        void callback(lang_void *data = nullptr) override {
            dev_->some_side_effects();
        }
    };

    void some_side_effects() {
        // Implementation of side effects goes here
    }

    static void init_class(simics::ConfClass *cls) {
        // Registering the event with a callback
        cls->add(simics::EventInfo("user_event",
                                   EVENT_CALLBACK(SampleEvent,
                                                  user_event)));
    }

    // Instance of UserTimeEvent initialized with this object
    UserTimeEvent user_event {this};
};
// }}

// coverity[global_init_order]
static simics::RegisterClassWithSimics<SampleEvent> init_event {
    "sample_device_cxx_event",
    "sample C++ device with an event",
    "Sample C++ device with an event"
};
