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

// This file simulates generated register code

#ifndef CPP_API_EXTENSIONS_EXAMPLES_REG_INTEGRATION_EXAMPLE_REGS_H
#define CPP_API_EXTENSIONS_EXAMPLES_REG_INTEGRATION_EXAMPLE_REGS_H

// Simics includes
#include <simics/cc-api.h>
#include <simics/cc-modeling-api.h>

// Supplemental API includes
#include "sme/sme.h"

class GeneratedRegisterDevice : public simics::MappableConfObject {
public:
    explicit GeneratedRegisterDevice(simics::ConfObjectRef o)
        : simics::MappableConfObject(o) {
    }
    static void init_class(simics::ConfClass *cls);
    void add_io_regs_bank(simics::ConfClass* cls);
};

class SampleBank : public simics::PortBank<> {
public:
    using PortBank::PortBank;

    void resetAllRegisters() {
        unsigned numOfRegs = number_of_registers();
        for (unsigned i = 0; i < numOfRegs; ++i) {
            std::pair<size_t, simics::RegisterInterface *> reg_pair = register_at_index(i);
            reg_pair.second->reset();
        }
    }

    class REG1 : public simics::BankRegister<sme::reg<simics::Register> > {
        public:
        using BankRegister::BankRegister;
                                            
            class FIELD1 : public simics::RegisterField<sme::field<simics::Field> > {
                public:
                using RegisterField::RegisterField;
            };
                                            
            class FIELD2 : public simics::RegisterField<sme::field<simics::Field> > {
                public:
                using RegisterField::RegisterField;
            };
                                            
        public:
        FIELD1 FIELD1 {                                
            this, simics::Name("FIELD1"),                 
            simics::Description("FIELD1"),
            simics::Offset(32), 
            simics::BitWidth(32)
        };
        FIELD2 FIELD2 {                                
            this, simics::Name("FIELD2"),                 
            simics::Description("FIELD2"),
            simics::Offset(0), 
            simics::BitWidth(32)
        }; 
    };

    REG1 reg1 {
        this, simics::Name("REG1"),
        simics::Description("REG1"),
        simics::Offset(0xf4c),
        simics::ByteSize(8),
        simics::InitValue(0x0)
    };

};


class SampleBankPort : public simics::BankPort<GeneratedRegisterDevice> {
  public:
    using BankPort<GeneratedRegisterDevice>::BankPort;

  private:
    SampleBank bank {this, simics::Description("a user defined bank")};
};

#endif

