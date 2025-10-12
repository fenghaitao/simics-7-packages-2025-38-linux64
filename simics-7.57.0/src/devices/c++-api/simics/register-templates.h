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

#ifndef SIMICS_REGISTER_TEMPLATES_H
#define SIMICS_REGISTER_TEMPLATES_H

#include <fmt/fmt/format.h>

#include <array>
#include <limits>
#include <numeric>  // iota
#include <string>
#include <vector>

#include "simics/bank-interface.h"
#include "simics/log.h"
#include "simics/register.h"
#include "simics/type/register-type.h"  // register_t

namespace simics {

// Templates

/*
 * Register with map information
 * This class creates a register object and add it to the <arg>bank_iface</arg>.
 * Optional <arg>fields</arg> is used to create a field object and add it
 * to the register.
 * Customized registers such as ReadConstantRegister takes additional arguments.
 */
template <typename TRegister = Register, typename... Args>
class BankRegister : public TRegister {
    static_assert(std::is_base_of<Register, TRegister>::value,
                  "TRegister must be derived from Register");
  public:
    BankRegister(BankInterface *bank_iface,
                 Name reg_name, Description desc, Offset offset, ByteSize size,
                 InitValue value, std::initializer_list<field_t> fields = {},
                 Args... args)
        : TRegister([bank_iface]() -> MappableConfObject* {
            if (!bank_iface) {
                throw std::invalid_argument(
                    "BankRegister: bank_iface cannot be nullptr");
            }
            return bank_iface->dev_obj();
        }(),
        std::string(bank_iface->name()) + SEPARATOR + std::string(reg_name),
        args...) {
        bank_iface->add_register(reg_name, desc, offset, size, value, fields);
    }
};

// Writes are ignored.
class IgnoreWriteRegister : public Register {
  public:
    using Register::Register;

    void write(uint64_t value, uint64_t enabled_bits) override {}
};

// Reads return 0. Writes are unaffected by this template.
class Read0Register : public Register {
  public:
    using Register::Register;

    uint64_t read(uint64_t enabled_bits) override {
        SIM_LOG_INFO_STR(4, bank_obj_ref(), 0,
                         fmt::format("Read from read-zero register {} -> 0x0",
                                     name()));
        return 0;
    }
};

// The object value is read-only for software, the object value
// can be modified by hardware.
class ReadOnlyRegister : public Register {
  public:
    using Register::Register;

    bool is_read_only() const override {
        return true;
    }

    void write(uint64_t value, uint64_t enabled_bits) override {
        // SIM_LOG_XXX_ONCE does not work within a class
        // must use a member variable
        SIM_LOG_SPEC_VIOLATION_STR(logged_once_ ? 2 : 1, bank_obj_ref(), 0,
                                   fmt::format("Write to read-only register {}"
                                               " (value written = {:#010x},"
                                               " contents = {:#010x})", name(),
                                               value & enabled_bits, get()));
        logged_once_ = true;
    }

  private:
    bool logged_once_ {false};
};

// The register value can be modified by software but can't be
// read back, reads return 0.
class WriteOnlyRegister : public Register {
  public:
    using Register::Register;

    uint64_t read(uint64_t enabled_bits) override {
        SIM_LOG_SPEC_VIOLATION_STR(logged_once_ ? 2 : 1, bank_obj_ref(), 0,
                                   fmt::format("Read from write-only register"
                                               " {} (returning 0)", name()));
        logged_once_ = true;
        return 0;
    }

  private:
    bool logged_once_ {false};
};

// Software can only clear bits. This feature is often used when
// hardware sets bits and software clears them to acknowledge.
// Software write 1's to clear bits. The new object value is a
// bitwise AND of the old object value and the bitwise complement
// of the value written by software.
class Write1ClearsRegister : public Register {
  public:
    using Register::Register;

    void write(uint64_t value, uint64_t enabled_bits) override {
        Register::write(~value, enabled_bits & value);
    }
};

// Software reads return the object value. The object value is
// then reset to 0 as a side-effect of the read.
class ClearOnReadRegister : public Register {
  public:
    using Register::Register;

    uint64_t read(uint64_t enabled_bits) override {
        uint64_t value = get();
        set(0);
        return value & enabled_bits;
    }
};

// Software can only set bits to 1. The new object value is
// the bitwise OR of the old object value and the value written
// by software.
class Write1OnlyRegister : public Register {
  public:
    using Register::Register;

    void write(uint64_t value, uint64_t enabled_bits) override {
        Register::write(get() | value, enabled_bits);
    }
};

// Software can only set bits to 0. The new object value is
// the bitwise AND of the old object value and the value
// written by software.
class Write0OnlyRegister : public Register {
  public:
    using Register::Register;

    void write(uint64_t value, uint64_t enabled_bits) override {
        Register::write(value & get(), enabled_bits);
    }
};

// Reads return a constant value
class ReadConstantRegister : public Register {
  public:
    ReadConstantRegister(MappableConfObject *dev_obj,
                         const std::string &name,
                         uint64_t read_val = 0) :
        Register(dev_obj, name),
        read_val_(read_val) {}

    uint64_t read(uint64_t enabled_bits) override {
        return read_val_ & enabled_bits;
    }

  protected:
    uint64_t read_val_;
};

// Writes are forbidden and have no effect. TODO(xiuliang): no_reset?
class ConstantRegister : public Register {
  public:
    using Register::Register;

    void write(uint64_t value, uint64_t enabled_bits) override {
        SIM_LOG_SPEC_VIOLATION_STR(logged_once_ ? 2 : 1, bank_obj_ref(), 0,
                                   fmt::format("Write to constant register {}"
                                               " (value written = {:#010x},"
                                               " contents = {:#010x})", name(),
                                               value & enabled_bits, get()));
        logged_once_ = true;
    }

  private:
    bool logged_once_ {false};
};

// The object value will remain constant. Writes are ignored
// and do not update the object value.
class SilentConstantRegister : public Register {
  public:
    using Register::Register;

    void write(uint64_t value, uint64_t enabled_bits) override {}
};

// The object value is constant 0. Software writes are forbidden
// and do not update the object value.
class ZerosRegister : public ConstantRegister {
  public:
    using ConstantRegister::ConstantRegister;

    void init(std::string_view desc, unsigned number_of_bytes,
              uint64_t init_val) override {
        if (init_val != 0) {
            SIM_LOG_SPEC_VIOLATION(
                    logged_once_ ? 2 : 1, bank_obj_ref(), 0,
                    "Invalid non-zeros init_val for ZerosRegister");
            logged_once_ = true;
        }
        ConstantRegister::init(desc, number_of_bytes, 0);
    }

  private:
    bool logged_once_ {false};
};

// The object is constant all 1's. Software writes do not update
// the object value.
class OnesRegister : public ConstantRegister {
  public:
    using ConstantRegister::ConstantRegister;

    void init(std::string_view desc, unsigned number_of_bytes,
              uint64_t init_val) override {
        uint64_t all_ones = (std::numeric_limits<uint64_t>::max)();
        if (number_of_bytes != 8) {
            all_ones >>= (8 - number_of_bytes) * 8;
        }
        if (init_val != all_ones) {
            SIM_LOG_SPEC_VIOLATION(
                    logged_once_ ? 2 : 1, bank_obj_ref(), 0,
                    "Invalid non-ones init_val for OnesRegister");
            logged_once_ = true;
        }
        ConstantRegister::init(desc, number_of_bytes, all_ones);
    }

  private:
    bool logged_once_ {false};
};

// The object's functionality is unimportant. Reads return 0.
// Writes are ignored.
class IgnoreRegister : public IgnoreWriteRegister {
  public:
    using IgnoreWriteRegister::IgnoreWriteRegister;

    uint64_t read(uint64_t enabled_bits) override {
        return 0;
    }
};

// The object is marked reserved and should not be used by software.
// Writes update the object value. Reads return the object value.
class ReservedRegister : public Register {
  public:
    using Register::Register;

    void write(uint64_t value, uint64_t enabled_bits) override {
        if (!has_logged_) {
            SIM_LOG_SPEC_VIOLATION_STR(2, bank_obj_ref(), 0,
                fmt::format("Write to reserved register {} (value written ="
                            " {:#010x}, contents = {:#010x}), will not warn"
                            " again.", name(), value & enabled_bits, get()));
            has_logged_ = true;
        }
    }

  private:
    bool has_logged_ {false};
};

// The object functionality associated to a read access is
// unimplemented. Write access is using default implementation.
class ReadUnimplRegister : public Register {
  public:
    ReadUnimplRegister(MappableConfObject *obj, const std::string &name)
        : Register(obj, name) {
        set_description("Read access not implemented. " + description());
    }

    uint64_t read(uint64_t enabled_bits) override {
        SIM_LOG_UNIMPLEMENTED_STR(logged_once_ ? 3 : 1, bank_obj_ref(), 0,
            fmt::format("Read from unimplemented register {}"
                        " (contents = {:#010x}).", name(),
                        get() & enabled_bits));
        logged_once_ = true;
        return get() & enabled_bits;
    }

  private:
    bool logged_once_ {false};
};

// The object functionality is unimplemented. Warn when software
// is using the object. Writes and reads are implemented as default
// writes and reads.
class UnimplRegister : public Register {
  public:
    UnimplRegister(MappableConfObject *obj, const std::string &name)
        : Register(obj, name) {
        set_description("Not implemented. " + description());
    }

    uint64_t read(uint64_t enabled_bits) override {
        SIM_LOG_UNIMPLEMENTED_STR(logged_once_read_ ? 3 : 1, bank_obj_ref(), 0,
            fmt::format("Read from unimplemented register {}"
                        " (contents = {:#010x}).", name(),
                        get() & enabled_bits));
        logged_once_read_ = true;
        return get() & enabled_bits;
    }

    void write(uint64_t value, uint64_t enabled_bits) override {
        SIM_LOG_UNIMPLEMENTED_STR(logged_once_write_ ? 3 : 1, bank_obj_ref(), 0,
            fmt::format("Write to unimplemented register {} (value"
                        " written = {:#010x}, contents = {:#010x}).",
                        name(), value & enabled_bits, get()));
        logged_once_write_ = true;
        Register::write(value, enabled_bits);
    }

  private:
    bool logged_once_read_ {false};
    bool logged_once_write_ {false};
};

// The object functionality associated to a write access is
// unimplemented. Read access is using default implementation.
class WriteUnimplRegister : public Register {
  public:
    WriteUnimplRegister(MappableConfObject *obj, const std::string &name)
        : Register(obj, name) {
        set_description("Write access not implemented. " + description());
    }

    void write(uint64_t value, uint64_t enabled_bits) override {
        SIM_LOG_UNIMPLEMENTED_STR(logged_once_ ? 3 : 1, bank_obj_ref(), 0,
            fmt::format("Write to unimplemented register {} (value"
                        " written = {:#010x}, contents = {:#010x}).",
                        name(), value & enabled_bits, get()));
        logged_once_ = true;
        Register::write(value, enabled_bits);
    }

  private:
    bool logged_once_ {false};
};

// The object functionality is unimplemented, but do not print
// a lot of log-messages when reading or writing. Writes and
// reads are implemented as default writes and reads.
class SilentUnimplRegister : public Register {
  public:
    using Register::Register;

    uint64_t read(uint64_t enabled_bits) override {
        SIM_LOG_UNIMPLEMENTED_STR(logged_once_read_ ? 3 : 2, bank_obj_ref(), 0,
            fmt::format("Read from unimplemented register {}"
                        " (contents = {:#010x}).", name(),
                        get() & enabled_bits));
        logged_once_read_ = true;
        return get() & enabled_bits;
    }

    void write(uint64_t value, uint64_t enabled_bits) override {
        SIM_LOG_UNIMPLEMENTED_STR(logged_once_write_ ? 3 : 2, bank_obj_ref(), 0,
            fmt::format("Write to unimplemented register {} (value"
                        " written = {:#010x}, contents = {:#010x}).",
                        name(), value & enabled_bits, get()));
        logged_once_write_ = true;
        Register::write(value, enabled_bits);
    }

  private:
    bool logged_once_read_ {false};
    bool logged_once_write_ {false};
};

// The object functionality is undocumented or poorly documented.
// Writes and reads are implemented as default writes and reads.
class UndocumentedRegister : public Register {
  public:
    using Register::Register;

    uint64_t read(uint64_t enabled_bits) override {
        SIM_LOG_SPEC_VIOLATION_STR(logged_once_read_ ? 2 : 1, bank_obj_ref(), 0,
            fmt::format("Read from poorly or non-documented"
                        " register {} (contents = {:#010x}).",
                        name(), get() & enabled_bits));
        logged_once_read_ = true;
        return get() & enabled_bits;
    }

    void write(uint64_t value, uint64_t enabled_bits) override {
        SIM_LOG_SPEC_VIOLATION_STR(
                logged_once_write_ ? 2 : 1, bank_obj_ref(), 0,
                fmt::format("Write to poorly or non-documented register {}"
                            " (value written = {:#010x}, contents = {:#010x}).",
                            name(), value & enabled_bits, get()));
        logged_once_write_ = true;
        Register::write(value, enabled_bits);
    }

  private:
    bool logged_once_read_ {false};
    bool logged_once_write_ {false};
};

// The register is excluded from the address space of the containing bank.
class UnmappedRegister : public Register {
  public:
    UnmappedRegister(MappableConfObject *obj, const std::string &name,
                     size_t number_of_bytes = 4, uint64_t init_value = 0)
        : Register(obj, name) {
        create_unmapped_register(number_of_bytes, init_value);
    }

    bool is_mapped() const override {
        return false;
    }

  private:
    void create_unmapped_register(size_t number_of_bytes,
                                  uint64_t init_value) {
        if (number_of_bytes > 8 || number_of_bytes == 0) {
            SIM_LOG_ERROR(bank_obj_ref(), 0,
                          "The supported register size is [1-8] bytes");
            return;
        }
        register_memory_t bytePointers(number_of_bytes);
        std::iota(bytePointers.begin(), bytePointers.end(),
                  register_memory_.data());
        set_byte_pointers(bytePointers);
        init("Unmapped. ", number_of_bytes, init_value);
    }

    std::array<uint8_t, 8> register_memory_;
};

// The object's functionality is not in the model's scope and has been
// left unimplemented as a design decision. Software and hardware writes
// and reads are implemented as default writes and reads. Debug registers
// are a prime example of when to use this template. This is different from
// unimplemented which is intended to be implement (if required) but is a
// limitation in the current model.
class DesignLimitationRegister : public Register {
  public:
    DesignLimitationRegister(MappableConfObject *obj, const std::string &name)
        : Register(obj, name) {
        set_description(std::string("Not implemented (design limitation). This")
                        + " register is a dummy register with no side effects. "
                        + description());
    }
};

// The register is an alias for another register. All operations are forwarded
// to the other register.
class AliasRegister : public Register {
  public:
    AliasRegister(MappableConfObject *obj, const std::string &name,
                  const std::string &alias_name)
        : Register(obj, name),
          alias_name_(alias_name) {
        init_alias();
    }

    bool is_read_only() const override {
        return alias_->is_read_only();
    }

    bool is_mapped() const override {
        return alias_->is_mapped();
    }

    uint64_t get() const override {
        return alias_->get();
    }

    void set(uint64_t value) override {
        alias_->set(value);
    }

    uint64_t read(uint64_t enabled_bits) override {
        return alias_->read(enabled_bits);
    }

    void write(uint64_t value, uint64_t enabled_bits) override {
        alias_->write(value, enabled_bits);
    }

    std::vector<field_t> fields_info() const override {
        return alias_->fields_info();
    }

  private:
    void init_alias() {
        if (!HierarchicalObject::is_valid_hierarchical_name(alias_name_)
            || HierarchicalObject::level_of_hierarchical_name(
                    alias_name_) != static_cast<int>(Level::REGISTER)) {
            std::string err = "Ignored invalid register name (" \
                + alias_name_ + ")";
            SIM_LOG_ERROR_STR(bank_obj_ref(), 0, err);
            throw std::invalid_argument { err };
        }
        set_description("Alias register for register " + alias_name_ + ". "
                        + description());

        alias_ = dev_obj()->get_iface<RegisterInterface>(alias_name_);
        if (!alias_) {
            // A limitation that depends on the register define order
            std::string err = "The aliased register " + alias_name_ \
                + " not found. Alter the register define order to make sure " \
                + "it is defined before this register.";
            SIM_LOG_ERROR_STR(bank_obj_ref(), 0, err);
            throw std::invalid_argument { err };
        }
    }

    std::string alias_name_;
    RegisterInterface *alias_ {nullptr};
};

// The object value can be written only once
class WriteOnceRegister : public Register {
  public:
    using Register::Register;

    void write(uint64_t value, uint64_t enabled_bits) override {
        if (written_) {
            SIM_LOG_SPEC_VIOLATION_STR(1, bank_obj_ref(), 0,
                fmt::format("Write to write-once register {} (value"
                            " written = {:#010x}, contents = {:#010x})",
                            name(), value & enabled_bits, get()));
            return;
        }
        Register::write(value, enabled_bits);
        written_ = true;
    }

  private:
    bool written_ {false};
};

// Combinations of the basic templates
// Software reads return the object value. The object value is
// read-only for software then reset to 0 as a side-effect of the read.
class ReadOnlyClearOnReadRegister : public ReadOnlyRegister {
  public:
    using ReadOnlyRegister::ReadOnlyRegister;

    uint64_t read(uint64_t enabled_bits) override {
        uint64_t value = get();
        set(0);
        return value & enabled_bits;
    }
};

// Trait to extend a Register class with offset member
template <typename TRegister>
class ExtendRegisterWithOffset : public TRegister {
    static_assert(std::is_base_of<Register, TRegister>::value,
                  "TRegister must be derived from Register");

  public:
    using TRegister::TRegister;

    std::size_t offset() {
        if (offset_ == std::numeric_limits<std::size_t>::max()) {
            offset_ = Register::offset(this);
        }
        return offset_;
    }

  private:
    std::size_t offset_ {std::numeric_limits<std::size_t>::max()};
};

}  // namespace simics

#endif
