// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2021 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef SIMICS_BANK_TEMPLATES_H
#define SIMICS_BANK_TEMPLATES_H

#include <cstdint>
#include <string>
#include <string_view>

#include "simics/bank.h"
#include "simics/bank-port-interface.h"
#include "simics/type/common-types.h"

namespace simics {

// Helper class to create and initialize a bank on a port
template <typename TBank = Bank, typename... Args>
class PortBank : public TBank {
    static_assert(std::is_base_of<Bank, TBank>::value,
                  "TBank must be derived from Bank");
  public:
    PortBank(BankPortInterface *port_iface, Description desc, Args... args)
        : TBank(port_iface->dev_obj(), port_iface->bank_name().data(),
                args ...) {
        port_iface->set_bank({port_iface->bank_name().data(), desc, {}});
    }
};

class BigEndianBank : public Bank {
  public:
    BigEndianBank(MappableConfObject *dev_obj, const std::string &name)
        : Bank(dev_obj, name, ByteOrder::BE) {}
};

// Each missed byte in a missed read is set to miss_pattern
class MissPatternBank : public Bank {
  public:
    MissPatternBank(MappableConfObject *dev_obj, const std::string &name,
                    uint8_t miss_pattern = 0)
        : Bank(dev_obj, name) {
        set_miss_pattern(miss_pattern);
    }
};

/**
 * Normally a bank allocates memory from the device object using the
 * name of the bank as the key. SharedMemoryBank supports using any string
 * when allocating the bank memory. It can be used when multiple banks
 * are sharing the same bank memory.
 */
class SharedMemoryBank : public Bank {
  public:
    /// @param name_of_bank_memory the name of the bank memory
    SharedMemoryBank(MappableConfObject *dev_obj, const std::string &name,
                     std::string_view name_of_bank_memory)
        : Bank(dev_obj, name) {
        allocate_bank_memory(name_of_bank_memory);
    }
};

}  // namespace simics

#endif
