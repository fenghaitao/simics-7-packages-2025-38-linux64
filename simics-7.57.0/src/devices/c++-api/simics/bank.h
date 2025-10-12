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

#ifndef SIMICS_BANK_H
#define SIMICS_BANK_H

#include <map>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include "simics/hierarchical-object.h"
#include "simics/bank-interface.h"
#include "simics/bank-issue-callbacks-interface.h"
#include "simics/register-interface.h"
#include "simics/type/bank-access.h"
#include "simics/type/bank-type.h"  // bank_memory_t
#include "simics/type/common-types.h"  // Description, Offset, ByteSize

namespace simics {

class MappableConfObject;

enum class Inquiry : bool {
    Inquiry = true,
    NonInquiry = false
};

/**
 * @brief Base class to represent a Simics register bank
 *
 * Bank with default behavior which allows access to any offset, without any
 * side-effects. Registers and fields don't have to be mapped as all reads
 * return zero and all writes are ignored.
 */
class Bank : public BankInterface,
             public HierarchicalObject {
  public:
    /// @param name is the bank name alone, e.g., b0
    Bank(MappableConfObject *dev_obj, const std::string &name);

    /// @param byte_order represents the byte endianness
    Bank(MappableConfObject *dev_obj, const std::string &name,
         ByteOrder byte_order);

    // No duplication
    Bank(const Bank&) = delete;
    Bank& operator=(const Bank&) = delete;

    Bank(Bank &&rhs);
    Bank& operator=(Bank&& rhs);

    virtual ~Bank() = default;

    // BankInterface
    std::string_view name() const override {
        return HierarchicalObject::name();
    }
    MappableConfObject *dev_obj() const override {
        return HierarchicalObject::dev_obj();
    }
    const std::string &description() const override {
        return HierarchicalObject::description();
    }
    void set_description(Description desc) override {
        HierarchicalObject::set_description(desc);
    }
    void add_register(const register_t &reg) override;
    void add_register(std::string_view name, Description desc,
                      Offset offset, ByteSize number_of_bytes,
                      InitValue init_value,
                      const std::vector<field_t> &fields) override;
    unsigned number_of_registers() const override;
    std::pair<size_t, RegisterInterface *> register_at_index(
            unsigned index) const override;
    const std::map<size_t,
                   RegisterInterface *> &mapped_registers() const override;
    void set_callbacks(BankIssueCallbacksInterface *callbacks) override {
        callbacks_ = callbacks;
    }
    ByteOrder get_byte_order() const override {return byte_order_;}
    void set_miss_pattern(uint8_t miss_pattern) override {
        miss_pattern_ = miss_pattern;
    }
    exception_type_t transaction_access(transaction_t *t,
                                        uint64_t offset) override;

  protected:
    // Read/Get implementation
    virtual std::vector<uint8_t> read(
            uint64_t offset, size_t size,
            Inquiry inquiry = Inquiry::NonInquiry) const;
    // Write/Set implementation
    virtual void write(uint64_t offset, const std::vector<uint8_t> &value,
                       size_t size,
                       Inquiry inquiry = Inquiry::NonInquiry) const;

    virtual void unmapped_read(size_t offset, size_t size) const;
    virtual void unmapped_write(size_t offset, size_t size) const;

    /// Allocate memory for this bank by name
    void allocate_bank_memory(std::string_view name);

  private:
    // Handle the bank instrumentation and forward the access to mapped
    // registers
    void read_access(BankAccess &access,  // NOLINT
                     std::vector<uint8_t> &bytes) const;  // NOLINT
    void write_access(BankAccess &access,  // NOLINT
                      std::vector<uint8_t> &bytes) const;  // NOLINT

    // Return if the input range overlaps with the existing range
    bool has_range_overlap(uint64_t offset, size_t size) const;

    /// Associate the hierarchical name with the current BankInterface
    void set_iface();

    // Little endianness is by default used
    ByteOrder byte_order_ {ByteOrder::LE};

    // Each missed byte in a miss read is set to this value
    std::optional<uint8_t> miss_pattern_;

    // Map associates offset to the corresponding register interface
    std::map<size_t, RegisterInterface *> regs_;

    // @internal: Keep track of heap allocated register objects
    std::vector<std::unique_ptr<RegisterInterface>> newd_regs_;

    // @internal: Used to issue a specific type of callbacks
    const BankIssueCallbacksInterface *callbacks_ {nullptr};

    /// Points to the memory holding the bank content.
    /// Expected to be set by the allocate_bank_memory method.
    bank_memory_t *allocated_memory_ {nullptr};
};

}  // namespace simics

#endif
