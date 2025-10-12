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
#include <simics/cc-modeling-api.h>

using simics::Name;
using simics::Description;
using simics::Offset;
using simics::ByteSize;
using simics::InitValue;
using simics::Stride;
using simics::BitWidth;

//:: pre sample-device-c++/by_code {{
class SampleBank : public simics::PortBank<> {
  public:
    using PortBank::PortBank;

    class SampleRegister : public simics::BankRegister<> {
      public:
        using BankRegister::BankRegister;

        class SampleField : public simics::RegisterField<> {
          public:
            using RegisterField::RegisterField;

            // Override to print a log when being written
            void write(uint64_t value, uint64_t enabled_bits) override {
                SIM_LOG_INFO(3, bank_obj_ref(), 0, "Write to SampleField");
                simics::Field::write(value, enabled_bits);
            }
        };

        uint64_t read(uint64_t enabled_bits) override {
            SIM_LOG_INFO(3, bank_obj_ref(), 0, "Read from SampleRegister");
            return simics::Register::read(enabled_bits);
        }

      private:
        SampleField f0 {
            this, Name("f0"), Description("a sample field"),
            Offset(0), BitWidth(16)
        };
        simics::RegisterField<> f1 {
            this, Name("f1"), Description("a default field"),
            Offset(16), BitWidth(16)
        };
    };

  private:
    SampleRegister r0 {
        this, Name("r[0]"),
        Description("A register with init value 42"),
        Offset(0), ByteSize(4), InitValue(42)
    };
    SampleRegister r1 {
        this, Name("r[1]"),
        Description("A register with init value 42"),
        Offset(0x10), ByteSize(4), InitValue(42)
    };
};
// }}

class SampleBankByCode : public simics::MappableConfObject {
  public:
    using MappableConfObject::MappableConfObject;
    static void init_class(simics::ConfClass *cls);
};

//:: pre sample-device-c++/mapping_via_the_class {{
void SampleBankByCode::init_class(simics::ConfClass *cls) {
    cls->add(simics::make_bank_port<simics::SimpleBankPort<SampleBank>>(
                     cls->name() + ".SampleBank", "sample bank"), "bank.b[2]");
}
// }}

// coverity[global_init_order]
static simics::RegisterClassWithSimics<SampleBankByCode> init_bank_by_code {
    "sample_device_cxx_bank_by_code",
    "sample C++ device with a bank by code",
    "Sample C++ device with a bank by code"
};
