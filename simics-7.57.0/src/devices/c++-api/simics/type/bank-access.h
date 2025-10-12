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

#ifndef SIMICS_TYPE_BANK_ACCESS_H
#define SIMICS_TYPE_BANK_ACCESS_H

#include <simics/base/transaction.h>
#include <simics/base/types.h>  // conf_object_t

#include <cstdint>

// Same struct as defined in dmllib.h
typedef struct bank_access {
    conf_object_t *bank;
    bool *inquiry;
    uint64_t *offset;
    uint64_t size;

    uint64_t *value;
    bool *success;
    bool *suppress;
    conf_object_t *initiator;
} bank_access_t;

namespace simics {

/*
 * Type mainly used for bank instrumentation
 */
struct BankAccess {
    BankAccess(conf_object_t *bank, transaction_t *t, uint64_t offset)
        : bank(bank),
          initiator(SIM_transaction_initiator(t)),
          inquiry(SIM_transaction_is_inquiry(t)),
          offset(offset),
          size(SIM_transaction_size(t)) {}

    BankAccess(conf_object_t *bank, conf_object_t *ini, bool inquiry,
               uint64_t offset, uint64_t size)
        : bank(bank),
          initiator(ini),
          inquiry(inquiry),
          offset(offset),
          size(size) {}

    bank_access_t c_struct() {
        return {bank, &inquiry, &offset, size, &value,
                &success, &suppress, initiator};
    }

    conf_object_t *bank;
    conf_object_t *initiator;
    bool inquiry;
    uint64_t offset;
    uint64_t size;
    uint64_t value {0};
    bool success {true};
    bool suppress {false};
};

}  // namespace simics

#endif
