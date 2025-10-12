// -*- mode: C++; c-file-style: "virtutech-c++" -*-

/*
  © 2025 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include "simics/field.h"

#include <fmt/fmt/format.h>
#include <simics/base/notifier.h>  // SIM_notify

#include <bitset>
#include <cstddef>  // size_t
#include <cstdint>
#include <string>
#include <string_view>
#include <utility>  // move

#include "simics/log.h"
#include "simics/register-interface.h"

namespace simics {

Field::Field(MappableConfObject *dev_obj, const std::string &name)
    : HierarchicalObject(dev_obj, name) {
    set_iface();
    parent_ = dev_obj->get_iface<RegisterInterface>(parent_name());
}

Field::Field(RegisterInterface *parent, std::string_view field_name)
    : Field(parent->dev_obj(),
            parent->hierarchical_name() + SEPARATOR + field_name.data()) {
    parent_ = parent;
}

Field::Field(Field &&rhs)
    : HierarchicalObject(std::move(rhs)),
      bits_(std::move(rhs.bits_)),
      number_of_bits_(std::move(rhs.number_of_bits_)),
      offset_(std::move(rhs.offset_)) {
    rhs.number_of_bits_ = 0;
    rhs.offset_ = -1;
    set_iface();
}

Field &Field::operator=(Field &&rhs) {
    // check for self-assignment
    if (this == &rhs)
        return *this;

    HierarchicalObject::operator=(std::move(rhs));
    set_iface();
    bits_ = std::move(rhs.bits_);
    number_of_bits_ = rhs.number_of_bits_;
    rhs.number_of_bits_ = 0;
    offset_ = rhs.offset_;
    rhs.offset_ = -1;
    return *this;
}

std::string_view Field::name() const {
    return HierarchicalObject::name();
}

const std::string &Field::description() const {
    return HierarchicalObject::description();
}

unsigned Field::number_of_bits() const {
    return number_of_bits_;
}

void Field::init(Description desc, const bits_type &bits, int8_t offset) {
    if (number_of_bits_ != 0) {
        SIM_LOG_ERROR_STR(bank_obj_ref(), 0,
                          fmt::format("Re-init field ({}) is not allowed",
                                      hierarchical_name()));
        return;
    }
    set_description(desc);
    set_bits(bits);
    offset_ = offset;
    // When constructing a Field in the by data approach, its parent may
    // not be set yet.
    if (parent_ == nullptr) {
        parent_ = dev_obj()->get_iface<RegisterInterface>(parent_name());
    }
}

RegisterInterface *Field::parent() const {
    return parent_;
}

uint64_t Field::get() const {
    uint64_t result = 0;
    auto num_bytes = bits_.size();
    for (bits_type::size_type i = 0; i < num_bytes; ++i) {
        const auto &[ptr, mask] = bits_[i];
        result |= (static_cast<uint64_t>(*ptr & mask) << (8 * i));
    }
    return result >> (offset_ % 8);
}

void Field::set(uint64_t value) {
    bool changed = false;
    value <<= (offset_ % 8);
    for (const auto &[ptr, mask] : bits_) {
        if (!changed) {
            changed = (value & mask) != (*ptr & mask);
        }
        *ptr = (static_cast<uint8_t>(value) & mask) | (*ptr & ~mask);
        value >>= 8;
    }

    if (changed) {
        SIM_notify(bank_obj_ref(), Sim_Notify_Bank_Register_Value_Change);
    }
}

uint64_t Field::read(uint64_t enabled_bits) {
    return enabled_bits & get();
}

void Field::write(uint64_t value, uint64_t enabled_bits) {
    if (enabled_bits != 0) {
        set((enabled_bits & value) | (~enabled_bits & get()));
    }
}

size_t Field::offset() const {
    if (offset_ == -1) {
        throw std::runtime_error("Field offset has not been initialized");
    }
    return static_cast<size_t>(offset_);
}

void Field::set_bits(const bits_type &bits) {
    if (dev_obj()->finalized()) {
        SIM_LOG_ERROR_STR(bank_obj_ref(), 0,
                            fmt::format("Cannot set bits for field ({}) when"
                                        " device has finalized",
                                        hierarchical_name()));
        return;
    }
    bits_ = bits;
    std::size_t number_of_bits = 0;
    for (const auto &[_, bits_mask] : bits_) {
        number_of_bits += std::bitset<8>(bits_mask).count();
        if (number_of_bits > 64) {
            SIM_LOG_ERROR_STR(bank_obj_ref(), 0,
                              fmt::format("Cannot set bits for field ({})"
                                          " with more than 64 bits",
                                          hierarchical_name()));
            return;
        }
    }
    // Guaranteed number_of_bits <= 64
    number_of_bits_ = static_cast<std::uint8_t>(number_of_bits);
}

void Field::set_iface() {
    if (hierarchy_level() != Level::FIELD) {
        std::string err = "Field name (" + hierarchical_name() \
            + ") does not match the field level (bankA.registerB.fieldC)";
        SIM_LOG_CRITICAL_STR(bank_obj_ref(), 0, err);
        throw std::invalid_argument { err };
    }
    dev_obj()->set_iface<FieldInterface>(hierarchical_name(), this);
}

}  // namespace simics
