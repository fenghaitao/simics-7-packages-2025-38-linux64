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

#ifndef SAMPLE_DEVICE_CPP_REGISTER_AS_DATA_H
#define SAMPLE_DEVICE_CPP_REGISTER_AS_DATA_H

#include <simics/type/bank-type.h>
#include <initializer_list>

const std::initializer_list<simics::bank_t> register_as_data {
    {"b[2]", "sample bank array of size 2", {
            {"r[2 stride 16]", "register always reads 42",
                0, 4, 42, {
                    {"f0", "a sample field", 0, 16},
                    {"f1", "a default field", 16, 16},
                }},
        }
    }
};

#endif
