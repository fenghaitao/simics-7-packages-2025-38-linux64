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

#include "simics/bank.h"

#include <simics/base/log.h>  // SIM_LOG_XXX

#include <algorithm>  // min
#include <cassert>
#include <iterator>  // advance
#include <limits>
#include <map>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include "simics/log.h"
#include "simics/register.h"
#include "simics/type/bank-access.h"
#include "simics/type/register-type.h"  // register_memory_t
#include "simics/utility.h"  // overlap_range

namespace simics {

static uint64_t uint64_from_bytes(std::vector<uint8_t>::const_iterator it,
                                  size_t size, ByteOrder byte_order) {
    assert(size <= 8);
    uint64_t ret = 0;
    for (size_t i = 0; i < size; ++i) {
        ret <<= 8;
        auto calculated_index = \
            static_cast<std::vector<uint8_t>::difference_type>(
                byte_order == ByteOrder::LE ? size - i - 1 : i);
        ret |= *(it + calculated_index);
    }
    return ret;
}

static void uint64_to_bytes(uint64_t value, size_t size, ByteOrder byte_order,
                            std::vector<uint8_t>::iterator it) {
    assert(size <= 8);
    for (size_t i = 0; i < size; ++i) {
        auto calculated_index = \
            static_cast<std::vector<uint8_t>::difference_type>(
                byte_order == ByteOrder::LE ? i : size - i - 1);
        *(it + calculated_index) = value & 0xff;
        value >>= 8;
    }
}

Bank::Bank(MappableConfObject *dev_obj, const std::string &name)
    : HierarchicalObject(dev_obj, name) {
    set_iface();
    allocate_bank_memory(this->name());
}

Bank::Bank(MappableConfObject *dev_obj, const std::string &name,
           ByteOrder byte_order)
    : Bank(dev_obj, name) {
    byte_order_ = byte_order;
}

Bank::Bank(Bank &&rhs)
    : HierarchicalObject(std::move(rhs)),
      byte_order_(rhs.byte_order_),
      regs_(std::move(rhs.regs_)),
      newd_regs_(std::move(rhs.newd_regs_)),
      callbacks_(rhs.callbacks_),
      allocated_memory_(rhs.allocated_memory_) {
    set_iface();
    rhs.callbacks_ = nullptr;
    rhs.allocated_memory_ = nullptr;
}

Bank &Bank::operator=(Bank&& rhs) {
    // check for self-assignment
    if (this == &rhs)
        return *this;

    HierarchicalObject::operator=(std::move(rhs));
    set_iface();
    byte_order_ = rhs.byte_order_;
    regs_ = std::move(rhs.regs_);
    newd_regs_ = std::move(rhs.newd_regs_);
    callbacks_ = rhs.callbacks_;
    rhs.callbacks_ = nullptr;
    allocated_memory_ = rhs.allocated_memory_;
    rhs.allocated_memory_ = nullptr;
    return *this;
}

void Bank::add_register(const register_t &reg) {
    if (dev_obj()->finalized()) {
        SIM_LOG_ERROR(bank_obj_ref(), 0,
                      "Cannot add registers for bank (%s) when device has"
                      " finalized",
                      hierarchical_name().c_str());
        return;
    }

    const auto &[name, desc, offset, number_of_bytes, init_value, fields] = reg;
    if (name.array_str().empty()) {
        add_register(name, desc, offset, number_of_bytes, init_value, fields);
    } else {
        for (const auto &[_name, _offset]
                 : name.arrayNamesToOffsets(number_of_bytes)) {
            add_register(_name, desc, offset + _offset, number_of_bytes,
                         init_value, fields);
        }
    }
}

void Bank::add_register(std::string_view name, Description desc,
                        Offset offset, ByteSize number_of_bytes,
                        InitValue init_value,
                        const std::vector<field_t> &fields) {
    // Cannot use fmt otherwise coverity would report error
    SIM_LOG_INFO(4, bank_obj_ref(), 0,
                 "Adding register (%s) at offset 0x%zx with size %zd",
                 name.data(), size_t{offset}, size_t{number_of_bytes});

    if (name.empty()) {
        SIM_LOG_ERROR(bank_obj_ref(), 0,
                      "Cannot add a register with empty name");
        return;
    }

    if (number_of_bytes > 8 || number_of_bytes == 0) {
        SIM_LOG_ERROR(bank_obj_ref(), 0,
                      "Cannot add a register with unsupported size (%zd)",
                      size_t{number_of_bytes});
        return;
    }

    // Check for offset overlap
    if (has_range_overlap(offset, number_of_bytes)) {
        SIM_LOG_ERROR(bank_obj_ref(), 0,
                      "Cannot add register(%s): offset overlapped"
                      " with existing registers on the bank",
                      name.data());
        return;
    }

    std::string reg_name {bank_name()};
    reg_name.append(1, SEPARATOR).append(name);
    regs_[offset] = dev_obj()->get_iface<RegisterInterface>(reg_name);
    if (regs_[offset] == nullptr) {
        newd_regs_.push_back(std::make_unique<Register>(dev_obj(), reg_name));
        regs_[offset] = newd_regs_.back().get();
        SIM_LOG_INFO(3, bank_obj_ref(), 0, "Created default register %s",
                     reg_name.c_str());
    } else if (regs_[offset]->number_of_bytes() == 0) {
        SIM_LOG_INFO(3, bank_obj_ref(), 0, "Used user defined register %s",
                     reg_name.c_str());
        if (!regs_[offset]->is_mapped()) {
            return;
        }
    } else {
        regs_.erase(offset);
        SIM_LOG_ERROR(bank_obj_ref(), 0,
                      "Cannot add register(%s): name duplicated"
                      " with existing registers on the bank",
                      name.data());
        return;
    }

    // bytePointers represents a vector of pointers to individual bytes
    register_memory_t bytePointers(number_of_bytes);
    for (size_t index = 0; index < number_of_bytes; ++index) {
        // Get register's memory storage from bank's allocated_memory_
        bytePointers[index] = &((*allocated_memory_)[offset + index]);
    }
    regs_[offset]->set_byte_pointers(bytePointers);
    regs_[offset]->init(desc, static_cast<unsigned>(number_of_bytes),
                        init_value);

    // Add all fields
    for (const auto &field : fields) {
        regs_[offset]->parse_field(field);
    }
}

unsigned Bank::number_of_registers() const {
    auto size = regs_.size();
    unsigned max_size = (std::numeric_limits<unsigned int>::max)();
    if (size > max_size) {
        SIM_LOG_INFO(2, bank_obj_ref(), 0,
                     "The number of registers exceeds the maximum"
                     " supported value (0x%x)", max_size);
        return max_size;
    }
    return static_cast<unsigned>(size);
}

std::pair<size_t, RegisterInterface *> Bank::register_at_index(
        unsigned index) const {
    if (index >= number_of_registers()) {
        SIM_LOG_ERROR(bank_obj_ref(), 0,
                      "Invalid register with id %d", index);
        return {0, nullptr};
    }
    auto it = regs_.cbegin();
    std::advance(it, index);
    return *it;
}

const std::map<size_t, RegisterInterface *> &Bank::mapped_registers() const {
    return regs_;
}

exception_type_t Bank::transaction_access(transaction_t *t, uint64_t offset) {
    unsigned size = SIM_transaction_size(t);
    if (size == 0) {
        SIM_LOG_SPEC_VIOLATION(1, bank_obj_ref(), 0,
                               "0 byte transaction ignored");
        return Sim_PE_IO_Not_Taken;
    }

    BankAccess access {bank_obj_ref(), t, offset};
    std::vector<uint8_t> bytes(size);
    if (SIM_transaction_is_write(t)) {
        SIM_get_transaction_bytes(t, {bytes.data(), size});
        write_access(access, bytes);
    } else {
        read_access(access, bytes);
        SIM_set_transaction_bytes(t, {bytes.data(), size});
    }

    return access.success ? Sim_PE_No_Exception : Sim_PE_IO_Not_Taken;
}

void Bank::read_access(BankAccess &access, std::vector<uint8_t> &value) const {
    if (callbacks_ && !access.inquiry) {
        callbacks_->issue_callbacks(&access, CallbackType::BR);
    }

    SIM_LOG_INFO(4, bank_obj_ref(), Register_Read,
                 "%s %zd bytes from offset 0x%zx",
                 access.inquiry ? "Get" : "Read",
                 size_t{access.size}, size_t{access.offset});

    try {
        value = read(access.offset, access.size,
                     static_cast<Inquiry>(access.inquiry));
    } catch (const std::exception &e) {
        SIM_LOG_SPEC_VIOLATION(1, bank_obj_ref(), Register_Read_Exception,
                               "%s", e.what());
        access.success = false;
    }

    if (callbacks_ && !access.inquiry) {
        auto actual_size = access.size;
        if (actual_size > 8) {
            // SIMICS-20451
            SIM_LOG_INFO(3, bank_obj_ref(), Register_Read,
                         "Bank instrumentation can support maximum 8 bytes,"
                         " thus only the first 8 bytes are operated");
            actual_size = 8;
        }
        auto original_value = uint64_from_bytes(value.cbegin(), actual_size,
                                                byte_order_);
        access.value = original_value;
        callbacks_->issue_callbacks(&access, CallbackType::AR);
        if (access.value != original_value) {
            uint64_to_bytes(access.value, actual_size, byte_order_,
                            value.begin());
        }
    }
}

void Bank::write_access(BankAccess &access, std::vector<uint8_t> &value) const {
    assert(value.size() == access.size);

    if (callbacks_ && !access.inquiry) {
        auto actual_size = access.size;
        if (actual_size > 8) {
            // SIMICS-20451
            SIM_LOG_INFO(3, bank_obj_ref(), Register_Write,
                         "Bank instrumentation can support maximum 8 bytes,"
                         " thus only the first 8 bytes are operated");
            actual_size = 8;
        }
        auto original_value = uint64_from_bytes(value.cbegin(), actual_size,
                                                byte_order_);
        access.value = original_value;
        callbacks_->issue_callbacks(&access, CallbackType::BW);
        if (access.value != original_value) {
            uint64_to_bytes(access.value, actual_size, byte_order_,
                            value.begin());
        }
    }

    SIM_LOG_INFO(4, bank_obj_ref(), Register_Write,
                 "%s %zd bytes to offset 0x%zx",
                 access.inquiry ? "Set" : "Write",
                 size_t{access.size}, size_t{access.offset});

    try {
        write(access.offset, value, access.size,
              static_cast<Inquiry>(access.inquiry));
    } catch (const std::exception &e) {
        SIM_LOG_SPEC_VIOLATION(1, bank_obj_ref(), Register_Write_Exception,
                               "%s", e.what());
        access.success = false;
    }

    if (callbacks_ && !access.inquiry) {
        callbacks_->issue_callbacks(&access, CallbackType::AW);
    }
}

bool Bank::has_range_overlap(uint64_t offset, size_t size) const {
    // [offset, offset+size) is the new range to check
    if (regs_.empty())
        return false;

    uint64_t new_start = offset;
    uint64_t new_end = offset + size;

    // Find the first register with an offset not less than the given offset
    auto it_low = regs_.lower_bound(offset);

    // Case 1: Overlap with register starting at or after offset
    if (it_low != regs_.end()) {
        uint64_t reg_start = it_low->first;
        RegisterInterface* reg_iface = it_low->second;
        uint64_t reg_end = reg_start + reg_iface->number_of_bytes();
        // If the register starts before new_end, there is overlap
        if (reg_start < new_end && reg_end > new_start) {
            return true;
        }
    }

    // Case 2: Overlap with register before offset (previous register)
    if (it_low != regs_.begin()) {
        auto it_prev = std::prev(it_low);
        uint64_t reg_start = it_prev->first;
        RegisterInterface* reg_iface = it_prev->second;
        uint64_t reg_end = reg_start + reg_iface->number_of_bytes();
        // If the previous register ends after new_start, there is overlap
        if (reg_end > new_start) {
            return true;
        }
    }

    // Case 3: No overlap
    return false;
}

std::vector<uint8_t> Bank::read(uint64_t offset, size_t size,
                                Inquiry inquiry) const {
    // default read value
    std::vector<uint8_t> bytes(size,
                               miss_pattern_.has_value() ?
                               miss_pattern_.value() : 0);

    // Counter of unmapped bytes
    size_t unmapped_bytes_cnt = size;
    // The end range of [offset, offset + size)
    uint64_t end_range = offset + size;
    // The first_reg points to the first item in the map with a key
    // less than or equal to offset
    auto first_reg = regs_.upper_bound(offset);
    if (first_reg != regs_.begin()) {
        --first_reg;
    }
    for (auto it = first_reg; it != regs_.end() && it->first < end_range;
         ++it) {
        auto[reg_offset, reg_iface] = *it;
        size_t reg_size = reg_iface->number_of_bytes();
        size_t reg_end_range = reg_offset + reg_size;
        auto[overlap_start, overlap_end] = overlap_range(
                offset, end_range,
                reg_offset, reg_end_range);
        size_t bytes_to_read = overlap_end - overlap_start;

        // Register has no overlap with the access
        if (bytes_to_read == 0) {
            continue;
        }

        size_t bits_shift = (overlap_start - reg_offset) * 8;
        uint64_t bits_mask = (std::numeric_limits<uint64_t>::max)();
        if (bytes_to_read < 8)
            bits_mask = (1ULL << bytes_to_read * 8) - 1;
        bits_mask <<= bits_shift;

        uint64_t reg_val = 0;
        if (inquiry == Inquiry::Inquiry) {
            reg_val = reg_iface->get() & bits_mask;
        } else {
            reg_val = reg_iface->read(bits_mask) & bits_mask;
        }
        reg_val >>= bits_shift;

        uint64_to_bytes(reg_val, bytes_to_read, byte_order_,
                        bytes.begin() + \
                        static_cast<std::vector<uint8_t>::difference_type>(
                            overlap_start - offset));

        unmapped_bytes_cnt -= bytes_to_read;
    }

    if (inquiry == Inquiry::NonInquiry
        && !miss_pattern_.has_value() && unmapped_bytes_cnt != 0) {
        unmapped_read(offset, size);
    }

    return bytes;
}

void Bank::write(uint64_t offset, const std::vector<uint8_t> &value,
                 size_t size, Inquiry inquiry) const {
    if (size > value.size()) {
        throw std::invalid_argument {
            "Expected size(" + std::to_string(size) \
                + ") is larger than value's size("  \
                + std::to_string(value.size()) + ")"
        };
    }

    // The number of unmapped bytes
    size_t unmapped_bytes_cnt = size;
    // The end range of [offset, offset + size)
    uint64_t end_range = offset + size;
    // The first_reg points to the first item in the map with a key
    // less than or equal to offset
    auto first_reg = regs_.upper_bound(offset);
    if (first_reg != regs_.begin()) {
        --first_reg;
    }
    for (auto it = first_reg; it != regs_.end() && it->first < end_range;
         ++it) {
        auto[reg_offset, reg_iface] = *it;
        size_t reg_size = reg_iface->number_of_bytes();
        size_t reg_end_range = reg_offset + reg_size;
        auto[overlap_start, overlap_end] = overlap_range(
                offset, end_range,
                reg_offset, reg_end_range);
        size_t bytes_to_write = overlap_end - overlap_start;

        // Register has no overlap with the access
        if (bytes_to_write == 0) {
            continue;
        }

        auto write_value = uint64_from_bytes(
                value.cbegin() + \
                static_cast<std::vector<uint8_t>::difference_type>(
                    overlap_start - offset),
                bytes_to_write, byte_order_);
        size_t bits_shift = (overlap_start - reg_offset) * 8;
        write_value <<= bits_shift;

        uint64_t bits_mask = (std::numeric_limits<uint64_t>::max)();
        if (bytes_to_write < 8)
            bits_mask = (1ULL << bytes_to_write * 8) - 1;
        bits_mask <<= bits_shift;

        if (inquiry == Inquiry::Inquiry) {
            reg_iface->set(write_value | (reg_iface->get() & ~bits_mask));
        } else {
            reg_iface->write(write_value, bits_mask);
        }
        unmapped_bytes_cnt -= bytes_to_write;
    }

    if (inquiry == Inquiry::NonInquiry && unmapped_bytes_cnt != 0) {
        unmapped_write(offset, size);
    }
}

void Bank::unmapped_read(size_t offset, size_t size) const {
    throw std::runtime_error {
        "Read " + std::to_string(size) + " bytes at offset " \
            + std::to_string(offset) + " outside registers or misaligned"
    };
}

void Bank::unmapped_write(size_t offset, size_t size) const {
    throw std::runtime_error {
        "Write " + std::to_string(size) + " bytes at offset " \
            + std::to_string(offset) + " outside registers or misaligned"
    };
}

void Bank::allocate_bank_memory(std::string_view name) {
    // memory not yet allocated
    if (allocated_memory_ == nullptr) {
        allocated_memory_ = dev_obj()->get_bank_memory(name);
        return;
    }

    // empty memory can be re-allocated to a shared memory
    if (allocated_memory_->empty()) {
        // Shared memory's name begins with "_". This prevents a normal
        // bank's memory being shared with other banks.
        allocated_memory_ = dev_obj()->get_bank_memory(
                std::string("_") + name.data());
        return;
    }

    SIM_LOG_SPEC_VIOLATION(
            1, bank_obj_ref(), 0,
            "Cannot reset an allocated non-empty bank memory, ignored");
}

void Bank::set_iface() {
    if (hierarchy_level() != Level::BANK) {
        std::string err = "Bank name (" + hierarchical_name() \
            + ") does not match the bank level (bankA)";
        SIM_LOG_CRITICAL_STR(bank_obj_ref(), 0, err);
        throw std::invalid_argument { err };
    }
    dev_obj()->set_iface<BankInterface>(hierarchical_name(), this);
}

}  // namespace simics
