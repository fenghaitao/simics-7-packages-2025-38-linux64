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

#ifndef SIMICS_BANK_INTERFACE_H
#define SIMICS_BANK_INTERFACE_H

#include <simics/base/memory.h>  // exception_type_t
#include <simics/base/transaction.h>  // transaction_t

#include <cstdint>
#include <map>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include "simics/type/register-type.h"

namespace simics {

enum class ByteOrder {
    BE, LE,
};

class MappableConfObject;
class RegisterInterface;
class BankIssueCallbacksInterface;

/**
 * @brief An interface implemented by a Simics bank.
 *
 * This interface defines the operations and properties of a Simics bank,
 * which is a container for registers and associated metadata.
 */
class BankInterface {
  public:
    virtual ~BankInterface() = default;

    /**
     * @brief Get the name of the bank without level delimiters.
     *
     * @return A string view representing the bank name.
     */
    virtual std::string_view name() const = 0;

    /**
     * @brief Get the device object.
     *
     * @return A pointer to the MappableConfObject.
     */
    virtual MappableConfObject *dev_obj() const = 0;

    /**
     * @brief Get the description of the bank.
     *
     * @return A reference to the string containing the bank description.
     */
    virtual const std::string &description() const = 0;

    /**
     * @brief Set the description for the bank.
     *
     * @param desc A string view containing the new description for the bank.
     */
    virtual void set_description(Description desc) = 0;

    /**
     * @brief Parse a register name and add register to the bank.
     *
     * @param reg The register data to be added to the bank.
     */
    virtual void add_register(const register_t &reg) = 0;

    /**
     * @brief Add a register to the bank.
     *
     * @param name The name of the register.
     * @param desc The description of the register.
     * @param offset The offset of the register within the bank.
     * @param number_of_bytes The size of the register in bytes.
     * @param init_value The initial value of the register.
     * @param fields A vector of fields associated with the register.
     */
    virtual void add_register(std::string_view name, Description desc,
                              Offset offset, ByteSize number_of_bytes,
                              InitValue init_value,
                              const std::vector<field_t> &fields) = 0;

    /**
     * @brief Get the number of registers in the bank.
     */
    virtual unsigned number_of_registers() const = 0;

    /**
     * @brief Get the register at a specific index.
     *
     * @param index The index of the register.
     * 
     * @return register offset and interface with an index into a
     * sorted registers by their offsets on the bank. {0, nullptr}
     * is returned for an outbound access.
     */
    virtual std::pair<size_t, RegisterInterface *> register_at_index(
            unsigned index) const = 0;

    /**
     * @brief Get all mapped registers on the bank ordered by offset.
     */
    virtual const std::map<size_t, RegisterInterface *> &
    mapped_registers() const = 0;

    /**
     * @brief Set the callbacks for bank issues.
     */
    virtual void set_callbacks(BankIssueCallbacksInterface *callbacks) = 0;

    /**
     * @brief Get the byte order of the bank.
     */
    virtual ByteOrder get_byte_order() const = 0;

    /**
     * @brief Set the miss pattern for the bank.
     */
    virtual void set_miss_pattern(uint8_t miss_pattern) = 0;

    /**
     * @brief Entry point for a memory access from the transaction interface.
     *
     * This function handles memory access requests by extracting the necessary
     * information from the transaction object, invoking the appropriate access
     * methods (read or write), and updating the transaction object accordingly.
     *
     * @param offset The memory offset relative to the bank.
     * @return Sim_PE_No_Exception if the access succeeded, or
     *         SIM_PE_IO_Not_Taken if the access was not handled.
     */
    virtual exception_type_t transaction_access(transaction_t *t,
                                                uint64_t offset) = 0;
};

}  // namespace simics

#endif
