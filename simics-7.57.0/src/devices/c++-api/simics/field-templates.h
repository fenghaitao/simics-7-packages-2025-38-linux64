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

#ifndef SIMICS_FIELD_TEMPLATES_H
#define SIMICS_FIELD_TEMPLATES_H

#include <fmt/fmt/format.h>

#include <limits>
#include <string>

#include "simics/field.h"
#include "simics/log.h"
#include "simics/register-interface.h"

namespace simics {

/*
 * Field with map information
 * This class creates a field object and add it to the <arg>reg_iface</arg>.
 * Customized fields such as ReadConstantField takes additional arguments.
 */
template <typename TField = Field, typename... Args>
class RegisterField : public TField {
    static_assert(std::is_base_of<Field, TField>::value,
                  "TField must be derived from Field");
  public:
    RegisterField(RegisterInterface *reg_iface, Name name, Description desc,
                  Offset offset, BitWidth size, Args... args)
        : TField([reg_iface]() -> MappableConfObject* {
            if (!reg_iface) {
                throw std::invalid_argument(
                    "RegisterField: reg_iface cannot be nullptr");
            }
            return reg_iface->dev_obj();
        }(),
        reg_iface->hierarchical_name() + SEPARATOR + std::string(name),
        args...) {
        reg_iface->add_field(name, desc, offset, size);
    }
};

// Templates
// Writes are ignored.
class IgnoreWriteField : public Field {
  public:
    using Field::Field;

    void write(uint64_t value, uint64_t enabled_bits) override {}
};

// Reads return 0. Writes are unaffected by this template.
class Read0Field : public Field {
  public:
    using Field::Field;

    uint64_t read(uint64_t enabled_bits) override {
        SIM_LOG_INFO_STR(4, bank_obj_ref(), 0,
                         fmt::format("Read from read-zero field {} -> 0x0.",
                                     name()));
        return 0;
    }
};

// Write only and reads return 0. Same as Read0Field thus derived from it.
class WriteOnlyField : public Read0Field {
  public:
    using Read0Field::Read0Field;

    uint64_t read(uint64_t enabled_bits) override {
        SIM_LOG_INFO_STR(4, bank_obj_ref(), 0,
                         fmt::format("Read from write-only field {} -> 0x0.",
                                     name()));
        return 0;
    }
};

// The object value is read-only for software, the object value
// can be modified by hardware.
class ReadOnlyField : public Field {
  public:
    using Field::Field;

    void write(uint64_t value, uint64_t enabled_bits) override {
        if ((value & enabled_bits) != (get() & enabled_bits)) {
            SIM_LOG_SPEC_VIOLATION_STR(logged_once_ ? 2 : 1, bank_obj_ref(), 0,
                fmt::format("Write to read-only field {} (value written"
                            " = {:#010x}, contents = {:#010x}).",
                            name(), value & enabled_bits, get()));
            logged_once_ = true;
        }
    }

  private:
    bool logged_once_ {false};
};

// Software can only clear bits. This feature is often used when
// hardware sets bits and software clears them to acknowledge.
// Software write 1's to clear bits. The new object value is a
// bitwise AND of the old object value and the bitwise complement
// of the value written by software.
class Write1ClearsField : public Field {
  public:
    using Field::Field;

    void write(uint64_t value, uint64_t enabled_bits) override {
        Field::write(~value, enabled_bits & value);
    }
};

// Software reads return the object value. The object value is
// then reset to 0 as a side-effect of the read.
class ClearOnReadField : public Field {
  public:
    using Field::Field;

    uint64_t read(uint64_t enabled_bits) override {
        uint64_t value = get();
        set(0);
        return value & enabled_bits;
    }
};

// Software can only set bits to 1. The new object value is
// the bitwise OR of the old object value and the value written
// by software.
class Write1OnlyField : public Field {
  public:
    using Field::Field;

    void write(uint64_t value, uint64_t enabled_bits) override {
        Field::write(get() | value, enabled_bits);
    }
};

// Software can only set bits to 0. The new object value is
// the bitwise AND of the old object value and the value
// written by software.
class Write0OnlyField : public Field {
  public:
    using Field::Field;

    void write(uint64_t value, uint64_t enabled_bits) override {
        Field::write(value & get(), enabled_bits);
    }
};

// Reads return a constant value
class ReadConstantField : public Field {
  public:
    ReadConstantField(MappableConfObject *obj, const std::string &name,
                      uint64_t read_val) :
        Field(obj, name),
        read_val_(read_val) {}

    uint64_t read(uint64_t enabled_bits) override {
        return read_val_ & enabled_bits;
    }

  private:
    uint64_t read_val_;
};

// Writes are forbidden and have no effect. TODO(xiuliang): no_reset?
class ConstantField : public Field {
  public:
    ConstantField(MappableConfObject *obj, const std::string &name,
                  uint64_t init_val) :
        Field(obj, name),
        init_val_(init_val) {}

    void write(uint64_t value, uint64_t enabled_bits) override {
        if ((value & enabled_bits) != (get() & enabled_bits)) {
            SIM_LOG_SPEC_VIOLATION_STR(logged_once_ ? 2 : 1, bank_obj_ref(), 0,
                fmt::format("Write to constant field {} (value written"
                            " = {:#010x}, contents = {:#010x}).", name(),
                            value & enabled_bits, get()));
            logged_once_ = true;
        }
    }

    void init(std::string_view desc, const bits_type &bits,
              int8_t offset) override {
        Field::init(desc, bits, offset);
        set(init_val_);
    }

  private:
    bool logged_once_ {false};
    uint64_t init_val_;
};

// The object value will remain constant. Writes are ignored
// and do not update the object value.
class SilentConstantField : public ConstantField {
  public:
    using ConstantField::ConstantField;

    void write(uint64_t value, uint64_t enabled_bits) override {}
};

// The object value is constant 0. Software writes are forbidden
// and do not update the object value.
class ZerosField : public ConstantField {
  public:
    ZerosField(MappableConfObject *obj, const std::string &name)
        : ConstantField(obj, name, 0) {}
};

// The object is constant all 1's. Software writes do not update
// the object value.
class OnesField : public ConstantField {
  public:
    OnesField(MappableConfObject *obj, const std::string &name)
        : ConstantField(obj, name,
                        (std::numeric_limits<uint64_t>::max)()) {}
};

// The object's functionality is unimportant. Reads return 0.
// Writes are ignored.
class IgnoreField : public IgnoreWriteField {
  public:
    using IgnoreWriteField::IgnoreWriteField;

    uint64_t read(uint64_t enabled_bits) override {
        return 0;
    }
};

// The object is marked reserved and should not be used by software.
// Writes update the object value. Reads return the object value.
class ReservedField : public Field {
  public:
    using Field::Field;

    void write(uint64_t value, uint64_t enabled_bits) override {
        if (!has_logged_ && (value & enabled_bits) != (get() & enabled_bits)) {
            SIM_LOG_SPEC_VIOLATION_STR(2, bank_obj_ref(), 0,
                fmt::format("Write to reserved field {} (value written"
                            " = {:#010x}, contents = {:#010x}), will not warn"
                            " again.", name(), value & enabled_bits, get()));
            has_logged_ = true;
        }
        Field::write(value, enabled_bits);
    }

  private:
    bool has_logged_ {false};
};

// The object functionality associated to a read access is
// unimplemented. Write access is using default implementation.
class ReadUnimplField : public Field {
  public:
    ReadUnimplField(MappableConfObject *obj, const std::string &name)
        : Field(obj, name) {
        set_description("Read access not implemented. " + description());
    }

    uint64_t read(uint64_t enabled_bits) override {
        return get() & enabled_bits;
    }
};

// The object functionality is unimplemented. Warn when software
// is using the object. Writes and reads are implemented as default
// writes and reads.
class UnimplField : public Field {
  public:
    UnimplField(MappableConfObject *obj, const std::string &name)
        : Field(obj, name) {
        set_description("Not implemented. " + description());
    }

    uint64_t read(uint64_t enabled_bits) override {
        return get() & enabled_bits;
    }

    void write(uint64_t value, uint64_t enabled_bits) override {
        if ((value & enabled_bits) != (get() & enabled_bits)) {
            SIM_LOG_UNIMPLEMENTED_STR(logged_once_ ? 3 : 1, bank_obj_ref(), 0,
                fmt::format("Write to unimplemented field {} (value written"
                            " = {:#010x}, contents = {:#010x}).",
                            name(), value & enabled_bits, get()));
            logged_once_ = true;
        }
        Field::write(value, enabled_bits);
    }

  private:
    bool logged_once_ {false};
};

// The object functionality associated to a write access is
// unimplemented. Read access is using default implementation.
class WriteUnimplField : public Field {
  public:
    WriteUnimplField(MappableConfObject *obj, const std::string &name)
        : Field(obj, name) {
        set_description("Write access not implemented. " + description());
    }

    void write(uint64_t value, uint64_t enabled_bits) override {
        if ((value & enabled_bits) != (get() & enabled_bits)) {
            SIM_LOG_UNIMPLEMENTED_STR(logged_once_ ? 3 : 1, bank_obj_ref(), 0,
                fmt::format("Write to unimplemented field {} (value written"
                            " = {:#010x}, contents = {:#010x}).",
                            name(), value & enabled_bits, get()));
            logged_once_ = true;
        }
        Field::write(value, enabled_bits);
    }

  private:
    bool logged_once_ {false};
};

// The object functionality is unimplemented, but do not print
// a lot of log-messages when reading or writing. Writes and
// reads are implemented as default writes and reads.
class SilentUnimplField : public Field {
  public:
    using Field::Field;

    uint64_t read(uint64_t enabled_bits) override {
        return get() & enabled_bits;
    }

    void write(uint64_t value, uint64_t enabled_bits) override {
        if ((value & enabled_bits) != (get() & enabled_bits)) {
            SIM_LOG_UNIMPLEMENTED_STR(logged_once_ ? 3 : 2, bank_obj_ref(), 0,
                fmt::format("Write to unimplemented field {} (value written"
                            " = {:#010x}, contents = {:#010x}).",
                            name(), value & enabled_bits, get()));
            logged_once_ = true;
        }
        Field::write(value, enabled_bits);
    }

  private:
    bool logged_once_ {false};
};

// The object functionality is undocumented or poorly documented.
// Writes and reads are implemented as default writes and reads.
class UndocumentedField : public Field {
  public:
    using Field::Field;

    uint64_t read(uint64_t enabled_bits) override {
        SIM_LOG_SPEC_VIOLATION_STR(logged_once_read_ ? 2 : 1, bank_obj_ref(), 0,
            fmt::format("Read from poorly or non-documented field {}"
                        " (contents = {:#010x}).",
                        name(), get() & enabled_bits));
        logged_once_read_ = true;
        return get() & enabled_bits;
    }

    void write(uint64_t value, uint64_t enabled_bits) override {
        SIM_LOG_SPEC_VIOLATION_STR(logged_once_read_ ? 2 : 1, bank_obj_ref(), 0,
            fmt::format("Write to poorly or non-documented field {} (value"
                        " written = {:#010x}, contents = {:#010x}).",
                        name(), value & enabled_bits, get()));
        logged_once_write_ = true;
        Field::write(value, enabled_bits);
    }

  private:
    bool logged_once_read_ {false};
    bool logged_once_write_ {false};
};

// The object's functionality is not in the model's scope and has been
// left unimplemented as a design decision. Software and hardware writes
// and reads are implemented as default writes and reads. Debug fields
// are a prime example of when to use this template. This is different from
// unimplemented which is intended to be implement (if required) but is a
// limitation in the current model.
class DesignLimitationField : public Field {
  public:
    DesignLimitationField(MappableConfObject *obj, const std::string &name)
        : Field(obj, name) {
        set_description(std::string("Not implemented (design limitation).")
                        + " This field is a dummy field with no side effects. "
                        + description());
    }
};

// The object value can be written only once
class WriteOnceField : public Field {
  public:
    using Field::Field;

    void write(uint64_t value, uint64_t enabled_bits) override {
        if (written_) {
            SIM_LOG_SPEC_VIOLATION_STR(1, bank_obj_ref(), 0,
                fmt::format("Write to write-once field {} (value written"
                            " = {:#010x}, contents = {:#010x})",
                            name(), value & enabled_bits, get()));
            return;
        }
        Field::write(value, enabled_bits);
        written_ = true;
    }

  private:
    bool written_ {false};
};

// Combinations of the basic templates
// Software reads return the object value. The object value is
// read-only for software then reset to 0 as a side-effect of the read.
class ReadOnlyClearOnReadField : public ReadOnlyField {
  public:
    using ReadOnlyField::ReadOnlyField;

    uint64_t read(uint64_t enabled_bits) override {
        uint64_t value = get();
        set(0);
        return value & enabled_bits;
    }
};

}  // namespace simics

#endif
