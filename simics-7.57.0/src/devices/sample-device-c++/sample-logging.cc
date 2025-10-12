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

class SampleLogging : public simics::ConfObject,
                      public simics::iface::SignalInterface {
  public:
    explicit SampleLogging(simics::ConfObjectRef o)
        : simics::ConfObject(o) {
        // Can directly use group_id 1
        SIM_LOG_INFO(1, o, 1, "Constructing SampleLogging");
    }

    static void init_class(simics::ConfClass *cls);

    // simics::iface::SignalInterface
    void signal_raise() override;
    void signal_lower() override;

  private:
    int level {0};
};

void SampleLogging::signal_raise() {
    ++level;
    // Or use the GROUP_ID macro
    //:: pre SampleLogging/SIM_LOG_INFO/GROUP_ID {{
    SIM_LOG_INFO(1, obj(), GROUP_ID(Signal), "Raising signal (new level: %d)",
                 level);
    // }}
}

void SampleLogging::signal_lower() {
    --level;
    //:: pre SampleLogging/SIM_LOG_INFO_STR/GROUP_ID {{
    SIM_LOG_INFO_STR(1, obj(), GROUP_ID(Signal),
                     fmt::format("Lowering signal (new level: {})", level));
    // }}
}

//:: pre SampleLogging/register_log_groups {{
void SampleLogging::init_class(simics::ConfClass *cls) {
    simics::LogGroups lg {"CTOR", "Signal"};
    cls->add(lg);
// }}
    cls->add(simics::iface::SignalInterface::Info());
}

// coverity[global_init_order]
static simics::RegisterClassWithSimics<SampleLogging> init_after_bank {
    "sample_device_cxx_logging",
    "sample C++ device with logging example",
    "Sample C++ device with logging example"
};
