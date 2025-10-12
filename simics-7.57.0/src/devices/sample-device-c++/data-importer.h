// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2022 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

// These lines have been generated ; changes will be overwritten by
// the generator

#ifndef SAMPLE_DEVICE_CPP_DATA_IMPORTER_H
#define SAMPLE_DEVICE_CPP_DATA_IMPORTER_H

//:: pre sample-device-c++/data_importer {{
#include <simics/cc-modeling-api.h>

#include "register-as-data.h"

class SampleRegister : public simics::Register {
  public:
    using Register::Register;

    class SampleField : public simics::Field {
      public:
        using Field::Field;

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
    SampleField f0 {dev_obj(), hierarchical_name() + ".f0"};
};

class DataImporter {
  public:
    explicit DataImporter(simics::MappableConfObject *obj)
        : obj_(obj) {}

    template <typename T>
    static void import_data(simics::ConfClass *cls) {
        simics::create_hierarchy_from_register_data<T>(cls, register_as_data);
    }

  private:
    simics::MappableConfObject *obj_;
    SampleRegister b0_r0 {obj_, "b[0].r[0]"};
    SampleRegister b0_r1 {obj_, "b[0].r[1]"};
    SampleRegister b1_r0 {obj_, "b[1].r[0]"};
    SampleRegister b1_r1 {obj_, "b[1].r[1]"};
};
// }}
#endif
