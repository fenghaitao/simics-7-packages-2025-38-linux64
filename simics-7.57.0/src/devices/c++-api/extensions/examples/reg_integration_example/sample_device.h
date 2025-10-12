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

//-*- C++ -*-

#ifndef CPP_API_EXTENSIONS_EXAMPLES_REG_INTEGRATION_EXAMPLE_SAMPLE_DEVICE_H
#define CPP_API_EXTENSIONS_EXAMPLES_REG_INTEGRATION_EXAMPLE_SAMPLE_DEVICE_H

#include <simics/cc-api.h>
#include <simics/c++/model-iface/transaction.h>

#include "regs.h"

class SampleBankPortManual;

class SampleDevice : public simics::MappableConfObject {
  public:
    explicit SampleDevice(simics::ConfObjectRef o)
        : simics::MappableConfObject(o) {
        // initialize
    }

    static void init_class(simics::ConfClass *cls);

    void objects_finalized() override;

    void do_reg_bindings();

    void add_io_regs_bank(simics::ConfClass* cls);

    void hello_world_callback();

    SampleBankPortManual* io_regs;
};


class SampleBankPortManual : public simics::BankPort<SampleDevice> {
  public:
    using BankPort<SampleDevice>::BankPort;

  public:
    SampleBank bank {this, simics::Description("a user defined bank")};
};

#endif

