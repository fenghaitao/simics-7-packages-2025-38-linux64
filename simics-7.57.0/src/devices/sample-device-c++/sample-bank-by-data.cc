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

//:: pre sample-device-c++/with_register_as_data {{
#include <simics/cc-api.h>
#include <simics/cc-modeling-api.h>
#include "data-importer.h"

class SampleBankByData : public simics::MappableConfObject,
                         public DataImporter {
  public:
    explicit SampleBankByData(simics::ConfObjectRef obj)
        : MappableConfObject(obj),
          DataImporter(this) {}

    static void init_class(simics::ConfClass *cls) {
        DataImporter::import_data<SampleBankByData>(cls);
    }
};

// coverity[global_init_order]
static simics::RegisterClassWithSimics<SampleBankByData> init_bank_by_data {
    "sample_device_cxx_bank_by_data",
    "sample C++ device with a bank by data",
    "Sample C++ device with a bank by data"
};
// }}
