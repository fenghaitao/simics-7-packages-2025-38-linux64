// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
 * sample-notifier-c++ -- sample C++ device subscribing to and publishing
   notifiers

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
#include <simics/c++/devs/signal.h>

// The notifier callback function is invoked when reset
void on_notify_reset(conf_object_t *obj,
                     conf_object_t *notifier, void *data);

class SampleNotifier : public simics::ConfObject,
                       public simics::iface::SignalInterface {
  public:
    explicit SampleNotifier(simics::ConfObjectRef o)
        : simics::ConfObject(o) {
        // Add a notifier callback for reset
        auto *handle = SIM_add_notifier(
                o, notifier_, o, &on_notify_reset, nullptr);
        if (handle == nullptr) {
            throw std::runtime_error {
                "the notifier type is not supported by the object"
            };
        }
    }

    static void init_class(simics::ConfClass *cls);

    // simics::iface::SignalInterface
    void signal_raise() override;
    void signal_lower() override;

    int notifier_count_ {0};

  private:
    // register custom notifier types
    notifier_type_t notifier_ {SIM_notifier_type("sample-notifier-reset")};
};

// Simulate the device is being reset and notify all subscribers about it
void SampleNotifier::signal_raise() {
    SIM_LOG_INFO(1, obj(), 0, "Hey, I'm being reset");
    SIM_notify(obj(), notifier_);
}

void SampleNotifier::signal_lower() {}

void on_notify_reset(conf_object_t *obj,
                     conf_object_t *notifier, void *data) {
    auto *o = simics::from_obj<SampleNotifier>(obj);
    // Increase count each time when notified
    ++o->notifier_count_;
    SIM_LOG_INFO(1, obj, 0, "Hey, I know you are reset now");
}

void SampleNotifier::init_class(simics::ConfClass *cls) {
    SIM_register_notifier(
        *cls, SIM_notifier_type("sample-notifier-reset"),
        "Notifier that is triggered after the device was reset");
    cls->add(simics::Attribute("notifier_count", "i", "A count for notifier",
                               ATTR_CLS_VAR(SampleNotifier, notifier_count_)));
    cls->add(simics::iface::SignalInterface::Info());
}

extern "C" void init_local() {
    simics::make_class<SampleNotifier>(
            "sample_notifier_cc",
            "sample C++ device",
            "This is a sample Simics device written in C++.");
}
