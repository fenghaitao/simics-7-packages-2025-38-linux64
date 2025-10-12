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

#include "simics/hierarchical-object.h"

#include <fmt/fmt/format.h>
#include <simics/base/conf-object.h>  // SIM_marked_for_deletion
#include <simics/base/log.h>  // SIM_LOG_XXX

#include <algorithm>  // count
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>  // swap, move

#include "simics/log.h"

namespace simics {

HierarchicalObject::HierarchicalObject(MappableConfObject *dev_obj,
                                       const std::string &name)
    : dev_obj_(dev_obj), hierarchical_name_(name) {
    if (dev_obj == nullptr) {
        throw std::invalid_argument {
            "HierarchicalObject cannot be constructed from a NULL dev_obj"
        };
    }
    init();
}

HierarchicalObject::~HierarchicalObject() {
    if (bank_obj_ref_.configured()) {
        if (!SIM_marked_for_deletion(bank_obj_ref_)) {
            SIM_LOG_CRITICAL(bank_obj_ref_.object(), 0,
                             "Hierarchical object can't be deleted"
                             " during the simulation");
        }
    }
}

HierarchicalObject::HierarchicalObject(HierarchicalObject &&rhs) noexcept
    : dev_obj_(rhs.dev_obj_),
    hierarchical_name_(std::move(rhs.hierarchical_name_)),
    desc_(std::move(rhs.desc_)),
    bank_obj_ref_(rhs.bank_obj_ref_),
    level_(rhs.level_) {}

HierarchicalObject &HierarchicalObject::
operator=(HierarchicalObject&& rhs) noexcept {
    // check for self-assignment
    if (this == &rhs)
        return *this;

    HierarchicalObject temp(std::move(rhs));
    std::swap(dev_obj_, temp.dev_obj_);
    std::swap(hierarchical_name_, temp.hierarchical_name_);
    std::swap(desc_, temp.desc_);
    std::swap(bank_obj_ref_, temp.bank_obj_ref_);
    std::swap(level_, temp.level_);
    return *this;
}

const std::string &HierarchicalObject::hierarchical_name() const {
    return hierarchical_name_;
}

std::string_view HierarchicalObject::name() const {
    if (hierarchy_level() == Level::BANK) {
        return hierarchical_name();
    } else {
        return {hierarchical_name().data()                  \
                + hierarchical_name().rfind(SEPARATOR) + 1};
    }
}

const std::string &HierarchicalObject::description() const {
    return desc_;
}

void HierarchicalObject::set_description(Description desc) {
    desc_ = desc;
}

Level HierarchicalObject::hierarchy_level() const {
    return level_;
}

std::string_view HierarchicalObject::bank_name() const {
    if (hierarchy_level() == Level::BANK) {
        return name();
    } else {
        return {hierarchical_name().data(),
                hierarchical_name().find(SEPARATOR)};
    }
}

MappableConfObject *HierarchicalObject::dev_obj() const {
    return dev_obj_;
}

ConfObjectRef HierarchicalObject::bank_obj_ref() const {
    return bank_obj_ref_;
}

std::string_view HierarchicalObject::parent_name() const {
    if (hierarchy_level() == Level::BANK) {
        return {};
    } else {
        return {hierarchical_name().data(),
                hierarchical_name().rfind(SEPARATOR)};
    }
}

FieldInterface *HierarchicalObject::
lookup_field(const std::string &name) const {
    FieldInterface *field_interface = nullptr;
    if (!dev_obj_->finalized()) {
        SIM_LOG_ERROR(dev_obj_->obj(), 0,
                        "Look up field should be called after finalize"
                        " phase");
        return field_interface;
    }
    if (!is_valid_hierarchical_name(name)) {
        SIM_LOG_ERROR_STR(dev_obj_->obj(), 0,
                          fmt::format("Invalid field name: {}", name));
        return field_interface;
    }

    auto field_name_level = level_of_hierarchical_name(name);
    if (field_name_level == 0) {
        // With field name only like "f2"
        if (level_ == Level::REGISTER) {
                field_interface = dev_obj_->get_iface<FieldInterface>(
                    hierarchical_name_ + SEPARATOR + name);
        } else if (level_ == Level::FIELD) {
            field_interface = dev_obj_->get_iface<FieldInterface>(
                    hierarchical_name_.substr(0, hierarchical_name_.rfind(
                                                        SEPARATOR)) \
                    + SEPARATOR + name);
        } else {
            SIM_LOG_ERROR(dev_obj_->obj(), 0,
                            "Unable to lookup a field with field name only"
                            " in a bank");
            return field_interface;
        }
    } else if (field_name_level == 1) {
        // With field name only like "r1.f2"
        field_interface = dev_obj_->get_iface<FieldInterface>(
                std::string(bank_name()).append(1, SEPARATOR).append(name));
    } else {
        field_interface = dev_obj_->get_iface<FieldInterface>(name);
    }

    if (!field_interface) {
        SIM_LOG_ERROR_STR(dev_obj_->obj(), 0,
                            fmt::format("Lookup field failed: {}", name));
    }
    return field_interface;
}

RegisterInterface *HierarchicalObject::
lookup_register(const std::string &name) const {
    RegisterInterface *register_interface = nullptr;
    if (!dev_obj_->finalized()) {
        SIM_LOG_ERROR(dev_obj_->obj(), 0,
                        "Look up register should be called after finalize"
                        " phase");
        return register_interface;
    }
    if (!is_valid_hierarchical_name(name)) {
        SIM_LOG_ERROR_STR(dev_obj_->obj(), 0,
                            fmt::format("Invalid register name: {}", name));
        return register_interface;
    }

    auto register_name_level = level_of_hierarchical_name(name);
    if (register_name_level == 0) {
        register_interface = dev_obj_->get_iface<RegisterInterface>(
            std::string(bank_name()).append(1, SEPARATOR).append(name));
    } else if (register_name_level == 1) {
        register_interface = dev_obj_->get_iface<RegisterInterface>(name);
    } else {
        SIM_LOG_ERROR_STR(dev_obj_->obj(), 0,
                          fmt::format("Invalid register name: {}", name));
        return register_interface;
    }

    if (!register_interface) {
        SIM_LOG_ERROR_STR(dev_obj_->obj(), 0,
                            fmt::format("Lookup register failed: {}", name));
    }
    return register_interface;
}

BankInterface *HierarchicalObject::lookup_bank(const std::string &name) const {
    BankInterface *bank_interface = nullptr;
    if (!dev_obj_->finalized()) {
        SIM_LOG_ERROR(dev_obj_->obj(), 0,
                        "Look up bank should be called after finalize phase");
        return bank_interface;
    }
    if (!is_valid_hierarchical_name(name)) {
        SIM_LOG_ERROR_STR(dev_obj_->obj(), 0,
                            fmt::format("Invalid bank name: {}", name));
        return bank_interface;
    }

    auto bank_name_level = level_of_hierarchical_name(name);
    if (bank_name_level > static_cast<int>(Level::BANK)) {
        SIM_LOG_ERROR_STR(dev_obj_->obj(), 0,
                            fmt::format("Invalid bank name: {}", name));
        return bank_interface;
    }

    bank_interface = dev_obj_->get_iface<BankInterface>(name);
    if (!bank_interface) {
        SIM_LOG_ERROR_STR(dev_obj_->obj(), 0,
                            fmt::format("Lookup bank failed: {}", name));
    }
    return bank_interface;
}

bool HierarchicalObject::is_valid_hierarchical_name(std::string_view name) {
    if (name.empty()) {
        return false;
    }

    if (std::count(name.cbegin(), name.cend(), SEPARATOR) > 2) {
        return false;
    }

    // Split the hierarchical name into parts using the SEPARATOR (.)
    size_t start = 0;
    size_t end = name.find(SEPARATOR);

    // Validate each part of the hierarchical name
    while (end != std::string_view::npos) {
        std::string_view part = name.substr(start, end - start);
        try {
            detail::HierarchicalObjectName::validate_name(part);
        } catch (const std::invalid_argument&) {
            return false;
        }
        start = end + 1;
        end = name.find(SEPARATOR, start);
    }

    // Validate the last part after the last SEPARATOR
    std::string_view last_part = name.substr(start);
    try {
        detail::HierarchicalObjectName::validate_name(last_part);
    } catch (const std::invalid_argument&) {
        return false;
    }

    // All parts are valid
    return true;
}

std::string_view::size_type HierarchicalObject::level_of_hierarchical_name(
        std::string_view name) {
    auto level = static_cast<std::string_view::size_type>(
        std::count(name.cbegin(), name.cend(), SEPARATOR));
    if (level > 2) {
        throw std::invalid_argument {
            "Invalid hierarchical name string: " + std::string(name)
        };
    }
    return level;
}

void HierarchicalObject::init() {
    if (!is_valid_hierarchical_name(hierarchical_name_)) {
        std::string err = "Cannot set with invalid name string: " \
            + hierarchical_name_;
        SIM_LOG_ERROR_STR(dev_obj_->obj(), 0, err);
        throw std::invalid_argument { err };
    }

    level_ = static_cast<Level>(
            level_of_hierarchical_name(hierarchical_name_));

    std::string bank_name {hierarchical_name_};
    if (level_ != Level::BANK) {
        auto pos_first_separator = hierarchical_name_.find(SEPARATOR);
        assert(pos_first_separator != std::string::npos);
        bank_name = hierarchical_name_.substr(0, pos_first_separator);
    }

    ensureBankPortExists(bank_name);
}

void HierarchicalObject::ensureBankPortExists(const std::string &bank_name) {
    auto *bank_port = SIM_object_descendant(
            dev_obj_->obj(), ("bank." + bank_name).c_str());
    if (bank_port == nullptr) {
        throw std::invalid_argument {
            fmt::format("Unable to initialize the HierarchicalObject '{}'"
                        " instance. Register the BankPort '{}'"
                        " for logging purposes.", hierarchical_name_,
                        "bank." + bank_name)
        };
    }
    bank_obj_ref_ = bank_port;
}

}  // namespace simics

