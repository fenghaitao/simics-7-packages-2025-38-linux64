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

class SampleAfterBank : public simics::PortBank<> {
  public:
    using PortBank::PortBank;

    class SampleRegister : public simics::BankRegister<> {
      public:
        using BankRegister::BankRegister;

        class SampleField : public simics::RegisterField<> {
          public:
            using RegisterField::RegisterField;

            // Override to have delayed clear after 1.0 second
            void write(uint64_t value, uint64_t enabled_bits) override {
                const char *msg = "Write to SampleField";
                SIM_LOG_INFO(3, bank_obj_ref(), 0, "%s", msg);
                simics::Field::write(value, enabled_bits);
                simics::ConfObjectRef obj = dev_obj()->obj();
                // After call from inside the field
                AFTER_CALL(dev_obj(), 1.0,
                           &SampleAfterBank::SampleRegister::SampleField::clear,
                           obj, hierarchical_name());
            }

            void clear() {
                SIM_LOG_INFO(1, bank_obj_ref(), 0,
                    "Call to clear at field level of field %s",
                    hierarchical_name().c_str());
                set(0x0);
            }
        };

        uint64_t read(uint64_t enabled_bits) override {
            const char *msg = "Read from SampleRegister";
            SIM_LOG_INFO(3, bank_obj_ref(), 0, "%s", msg);
            return simics::Register::read(enabled_bits);
        }

        void write_full(uint64_t value) {
            SIM_LOG_INFO(1, bank_obj_ref(), 0,
                "Call to write at reg level of reg %s with value 0x%llx",
                hierarchical_name().c_str(), static_cast<uint64>(value));
            simics::BankRegister<>::write(value, 0xffffffff);
        }

        SampleField f0 {
            this, Name("f0"), Description("an user defined field"),
            Offset(0), BitWidth(16)
        };
        simics::RegisterField<> f1 {
            this, Name("f1"), Description("a default field"),
            Offset(16), BitWidth(16)
        };
    };

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

class SampleAfterBankDevice
    : public simics::MappableConfObject,
      public simics::EnableAfterCall<SampleAfterBankDevice> {
  public:
    explicit SampleAfterBankDevice(simics::ConfObjectRef obj)
        : MappableConfObject(obj), EnableAfterCall(this) {}

    void finalize() override {
        if (SIM_is_restoring_state(obj())) {
            return;
        }

        // After call from inside the device
        AFTER_CALL(this, 1.0, &SampleAfterBank::SampleRegister::write_full,
                   obj(), "b[0].r[1]", (uint64_t)0xdeadbeef);
    }

    static void init_class(simics::ConfClass *cls);
};

void SampleAfterBankDevice::init_class(simics::ConfClass *cls) {
    REGISTER_REG_BANK_AFTER_CALL(
            &SampleAfterBank::SampleRegister::SampleField::clear);
    REGISTER_REG_BANK_AFTER_CALL(
            &SampleAfterBank::SampleRegister::write_full);

    cls->add(simics::make_bank_port<simics::SimpleBankPort<SampleAfterBank>>(
                     cls->name() + ".SampleAfterBank", "sample bank"),
             "bank.b[2]");
    cls->add(SampleAfterBankDevice::afterEventInfo("test_after_bank_event"));
}

// coverity[global_init_order]
static simics::RegisterClassWithSimics<SampleAfterBankDevice> init_after_bank {
    "sample_device_cxx_after_bank",
    "sample C++ after device with a bank",
    "Sample C++ after device with a bank"
};
