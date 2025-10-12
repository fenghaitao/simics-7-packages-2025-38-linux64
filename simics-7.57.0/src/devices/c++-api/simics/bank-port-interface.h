// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2023 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef SIMICS_BANK_PORT_INTERFACE_H
#define SIMICS_BANK_PORT_INTERFACE_H

#include <string_view>

#include "simics/type/bank-type.h"

namespace simics {

class BankInterface;
class MappableConfObject;

/*
 * An interface implemented by a Simics bank port
 */
class BankPortInterface {
  public:
    virtual ~BankPortInterface() = default;

    // @return the bank name on the port
    virtual std::string_view bank_name() const = 0;

    // @return the interface of the bank on the port
    virtual const BankInterface *bank_iface() const = 0;

    // @return the device object holds the port
    virtual MappableConfObject *dev_obj() const = 0;

    // @return if the port contains one bank
    virtual bool validate_bank_iface() const = 0;

    // set the bank on the port, can only be called once
    virtual void set_bank(const bank_t &bank) = 0;
};

}  // namespace simics
#endif
