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

#ifndef SAMPLE_DMA_DEVICE_CPP_REGISTER_AS_DATA_H
#define SAMPLE_DMA_DEVICE_CPP_REGISTER_AS_DATA_H

#include <simics/type/bank-type.h>

const simics::bank_t data {
    "regs", "DMA register bank", {
        {"control", "Control register",
            0, 4, 0, {
                {"EN", "Enable DMA", 31, 1},
                {"SWT", "Software Transfer Trigger", 30, 1},
                {"ECI", "Enable Completion Interrupt", 29, 1},
                {"TC", "Transfer complete", 28, 1},
                {"SG", "Scatter-gather list input", 27, 1},
                {"ERR", "DMA transfer error", 26, 1},
                {"TS", "Transfer size (32-bit words)", 0, 16},
                    },
            },
        {"source", "Source address",
            4, 4, 0, {}},
        {"dest", "Destination address",
            8, 4, 0, {}},
    },
};

#endif
