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

#include "sample_device.h"

void SampleDevice::init_class(simics::ConfClass *cls) {
    cls->add(simics::make_bank_port<SampleBankPortManual>(
        cls->name() + ".SampleBank", "sample bank"), "bank.b"
    );
}

void SampleDevice::objects_finalized() {
    io_regs = simics::from_obj<SampleBankPortManual>(
                SIM_object_descendant(obj(), "bank.b"));
    do_reg_bindings();
}


void SampleDevice::do_reg_bindings() {
    io_regs->bank.reg1.add_rule(
        [this]()->void {hello_world_callback();}
        , sme::stage::POST_WRITE, sme::type::NOTIFY
        , "REG1 POST_WRITE Notify Rule"
    );
}

void SampleDevice::hello_world_callback() {
    std::cout << "Hello World..." << std::endl;
}

extern "C" void init_local() {
    simics::make_class<SampleDevice>(
        // Simics class name
        "SampleDevice",
        // short description
        "sample C++ device",
        // class documentation
        "This is a sample Simics device written in C++.");
} 
