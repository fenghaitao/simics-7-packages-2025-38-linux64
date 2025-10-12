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

#ifndef SIMICS_BANK_PORT_H
#define SIMICS_BANK_PORT_H

#include <simics/base/attr-value.h>
#include <simics/base/memory.h>  // exception_type_t
#include <simics/base/notifier.h>  // SIM_register_notifier
#include <simics/simulator-api.h>  // SIM_hap_XXX
#include <simics/c++/model-iface/bank-instrumentation.h>
#include <simics/c++/model-iface/register-view.h>
#include <simics/c++/model-iface/register-view-read-only.h>
#include <simics/c++/model-iface/transaction.h>

#include <initializer_list>
#include <memory>
#include <stdexcept>  // invalid_argument
#include <string>
#include <string_view>
#include <tuple>  // tie
#include <type_traits>  // is_base_of
#include <utility>
#include <vector>

#include "simics/attribute-traits.h"  // checkSizeOverflowSimicsAttribute
#include "simics/bank.h"
#include "simics/bank-instrumentation-subscribe-connection.h"
#include "simics/bank-interface.h"
#include "simics/bank-port-interface.h"
#include "simics/conf-class.h"
#include "simics/conf-object.h"
#include "simics/detail/conf-object-util.h"  // get_interface
#include "simics/mappable-conf-object.h"
#include "simics/port.h"
#include "simics/type/bank-type.h"

namespace simics {

class RegisterInterface;

/**
 * @brief Extends Port with bank required interfaces
 *
 * Each bank resides inside a port object. Each port object contains exactly
 * one bank, the name of the bank is determined by the CTOR parameter o. The
 * instance of this class must have a valid bank interface to direct the
 * received Simics interface calls.
 *
 * @tparam TParent the parent class of the port object, see @Port
 */
template <typename TParent>
class BankPort : public Port<TParent>,
                 public BankPortInterface,
                 public BankInstrumentationSubscribeConnection,
                 public iface::RegisterViewInterface,
                 public iface::RegisterViewReadOnlyInterface,
                 public iface::RegisterViewCatalogInterface,
                 public iface::TransactionInterface {
    static_assert(
            std::is_base_of<MappableConfObject, TParent>::value,
            "BankPort requires the parent class be a MappableConfObject");

  public:
    /*
     * CTOR used for the "by code" modeling option
     * "by code" option is used when the bank is created and initialized
     * explicitly by code as a class member variable of a bank port.
     */
    explicit BankPort(ConfObjectRef o): Port<TParent>(o) {
        set_bank_name_from_port_name(o.name());
        SIM_hap_add_callback_obj(
                "Core_Conf_Object_Created", o.object(), 0,
                reinterpret_cast<obj_hap_func_t>(object_created), nullptr);
    }

    /*
     * CTOR used for the "by data" modeling option
     * "by data" option is used when the bank is created and initialized
     * implicitly by the data provided in the constructor.
     */
    BankPort(ConfObjectRef o, const bank_t *bank): BankPort(o) {
        if (bank == nullptr) {
            throw std::invalid_argument("Bank pointer cannot be nullptr");
        }
        set_bank(*bank);
    }

    // non-copyable
    BankPort(const BankPort &) = delete;
    BankPort& operator=(const BankPort &) = delete;

    virtual ~BankPort() {
        SIM_hap_delete_callback_obj(
                "Core_Conf_Object_Created", Port<TParent>::obj().object(),
                reinterpret_cast<obj_hap_func_t>(object_created), nullptr);
    }

    /// Adds bank properties to the given class
    static void addBankProperties(ConfClass *cls) {
        cls->add(iface::TransactionInterface::Info());
        cls->add(iface::RegisterViewInterface::Info());
        cls->add(iface::RegisterViewReadOnlyInterface::Info());
        cls->add(iface::RegisterViewCatalogInterface::Info());
        cls->add(iface::BankInstrumentationSubscribeInterface::Info());
        cls->add(iface::InstrumentationOrderInterface::Info());
        cls->add(LogGroups{"Register_Read", "Register_Write",
                           "Register_Read_Exception",
                           "Register_Write_Exception"});
        SIM_register_notifier(*cls, Sim_Notify_Bank_Register_Value_Change,
                              NULL /* default description works well */);
    }

    // BankPortInterface
    std::string_view bank_name() const override {
        return bank_name_;
    }

    const BankInterface *bank_iface() const override {
        return bank_iface_;
    }

    MappableConfObject *dev_obj() const override {
        return Port<TParent>::parent();
    };

    void set_bank(const bank_t &bank) override {
        if (bank_iface_) {
            SIM_LOG_ERROR(Port<TParent>::obj(), 0,
                          "bank iface can only be set once");
            return;
        }

        bank_iface_ = dev_obj()->template get_iface<BankInterface>(bank_name_);
        if (bank_iface_) {
            SIM_LOG_INFO(3, Port<TParent>::obj(), 0,
                         "Used user defined bank for %s",
                         bank_name_.c_str());
        } else {
            allocated_bank_.reset(new Bank(dev_obj(), bank_name_));
            bank_iface_ = allocated_bank_.get();
            SIM_LOG_INFO(3, Port<TParent>::obj(), 0,
                         "Created a new default bank for %s",
                         bank_name_.c_str());
        }
        auto &[name, desc, registers] = bank;
        bank_iface_->set_description(desc);
        bank_iface_->set_callbacks(this);
        for (const auto &reg : registers) {
            bank_iface_->add_register(reg);
        }
    }

    // iface::TransactionInterface
    exception_type_t issue(transaction_t *t, uint64 addr) override {
        if (!validate_bank_iface()) {
            return Sim_PE_IO_Not_Taken;
        }
        return bank_iface_->transaction_access(t, addr);
    }

    // iface::RegisterViewInterface
    const char *description() override {
        if (!validate_bank_iface()) {
            return nullptr;
        }
        return bank_iface_->description().data();
    }
    bool big_endian_bitorder() override {
        return Port<TParent>::parent()->big_endian_bitorder();
    }
    unsigned number_of_registers() override {
        return regs_offsets_.size();
    }
    attr_value_t register_info(unsigned reg) override {
        auto [reg_offset, reg_iface] = register_at_index(reg);
        if (reg_iface) {
            return register_info(reg_offset,
                                 bank_iface_->get_byte_order(),
                                 reg_iface);
        }
        return SIM_make_attr_nil();
    }
    uint64 get_register_value(unsigned reg) override {
        RegisterInterface *iface = nullptr;
        std::tie(std::ignore, iface) = register_at_index(reg);
        if (iface) {
            return iface->get();
        }
        return 0;
    }
    void set_register_value(unsigned reg, uint64 val) override {
        RegisterInterface *iface = nullptr;
        std::tie(std::ignore, iface) = register_at_index(reg);
        if (iface) {
            iface->set(val);
        }
    }

    // iface::RegisterViewReadOnlyInterface
    bool is_read_only(unsigned reg) override {
        RegisterInterface *iface = nullptr;
        std::tie(std::ignore, iface) = register_at_index(reg);
        return iface ? iface->is_read_only() : false;
    }

    // iface::RegisterViewCatalogInterface
    attr_value_t register_names() override {
        auto number_of_regs = number_of_registers();
        attr_value_t ret = SIM_alloc_attr_list(number_of_regs);
        RegisterInterface *iface = nullptr;
        for (unsigned i = 0; i < number_of_regs; ++i) {
            std::tie(std::ignore, iface) = register_at_index(i);
            if (iface == nullptr) {
                SIM_LOG_ERROR(Port<TParent>::obj(), 0,
                              "Invalid register index %d", i);
                SIM_attr_list_set_item(&ret, i, SIM_make_attr_nil());
                continue;
            }
            SIM_attr_list_set_item(&ret, i,
                                   SIM_make_attr_string(iface->name().data()));
        }
        return ret;
    }

    attr_value_t register_offsets() override {
        return std_to_attr(regs_offsets_);
    }

  private:
    bool validate_bank_iface() const override {
#if __cplusplus >= 202002L || (defined(_MSVC_LANG) && _MSVC_LANG >= 202002L)
        if (bank_iface_ == nullptr) { [[unlikely]]  // NOLINT(whitespace/newline,whitespace/line_length)
#else
        if (bank_iface_ == nullptr) {
#endif
            SIM_LOG_ERROR(Port<TParent>::obj(), 0,
                          "BankPort should have one bank");
            return false;
        }
        return true;
    }

    // Initialize the register offsets for better performance
    // when using the register_view interface
    void init_register_offsets() {
        const auto &mapped_regs = bank_iface_->mapped_registers();
        regs_offsets_.clear();
        regs_offsets_.reserve(mapped_regs.size());
        for (const auto& pair : mapped_regs) {
            regs_offsets_.push_back(pair.first);
        }
    }

    /// Function get called when the object is created and finalized
    static void object_created(lang_void *, conf_object_t *obj) {
        auto *iface = detail::get_interface<BankPort<TParent>>(obj);
        if (iface->validate_bank_iface()) {
            // Register can't be added after the bank port is finalized,
            // so it is safe to initialize the register offsets now
            iface->init_register_offsets();
        }
    }

    static attr_value_t register_info(size_t address, ByteOrder bo,
                                      const RegisterInterface *i) {
        attr_value_t info = SIM_alloc_attr_list(6);
        SIM_attr_list_set_item(&info, 0,
                               SIM_make_attr_string(i->name().data()));
        SIM_attr_list_set_item(&info, 1,
                               SIM_make_attr_string(i->description().c_str()));
        SIM_attr_list_set_item(&info, 2,
                               SIM_make_attr_uint64(i->number_of_bytes()));
        SIM_attr_list_set_item(&info, 3, SIM_make_attr_uint64(address));

        auto fields_info = i->fields_info();
        auto number_of_fields = fields_info.size();
        // The forth attr in info is a list fields
        checkSizeOverflowSimicsAttribute(number_of_fields);
        attr_value_t fields = SIM_alloc_attr_list(
                static_cast<unsigned>(number_of_fields));
        unsigned index = 0;
        for (const auto &[name, desc, offset, width] : fields_info) {
            // Each attr in fields is another list field_info
            attr_value_t field_info = SIM_alloc_attr_list(4);
            SIM_attr_list_set_item(&field_info, 0,
                                   SIM_make_attr_string(name.data()));
            SIM_attr_list_set_item(&field_info, 1,
                                   SIM_make_attr_string(desc.data()));
            SIM_attr_list_set_item(&field_info, 2,
                                   SIM_make_attr_uint64(offset));
            SIM_attr_list_set_item(&field_info, 3,
                                   SIM_make_attr_uint64(offset + width - 1));
            SIM_attr_list_set_item(&fields, index++, field_info);
        }
        SIM_attr_list_set_item(&info, 4, fields);
        SIM_attr_list_set_item(&info, 5,
                               SIM_make_attr_boolean(bo == ByteOrder::BE));
        return info;
    }

    /// Set the bank name from the port name with the assumption that
    /// the bank name is the last part of the port name after '.bank.'
    void set_bank_name_from_port_name(const std::string &port_name) {
        auto pos = port_name.rfind(".bank.");
        if (pos == std::string::npos) {
            throw std::invalid_argument(
                    "Invalid bank port name (" + port_name + ")");
        }
        bank_name_ = port_name.substr(pos + 6);
    }

    std::pair<size_t, RegisterInterface *> register_at_index(unsigned index) {
        size_t reg_offset {0};
        RegisterInterface *reg_iface {nullptr};
        try {
            reg_offset = regs_offsets_.at(index);
        } catch (const std::out_of_range &) {
            SIM_LOG_ERROR(Port<TParent>::obj(), 0,
                          "Invalid register index %d", index);
            return {reg_offset, reg_iface};
        }
        if (validate_bank_iface()) {
            reg_iface = bank_iface_->mapped_registers().at(reg_offset);
        }
        return {reg_offset, reg_iface};
    }

    // Points to the actual bank interface
    BankInterface *bank_iface_ { nullptr };
    // Name of the bank
    std::string bank_name_;
    // @internal: record the heap allocated Bank
    std::unique_ptr<BankInterface> allocated_bank_;
    // @internal: list of all register offsets by ascending order
    std::vector<size_t> regs_offsets_;
};

// This class defines a SimpleBankPort, which is a specialized bank port object.
// It contains a public member 'b' of type TBank, representing a bank.
template<typename TPortBank, typename... Args>
class SimpleBankPort : public BankPort<MappableConfObject> {
  public:
    explicit SimpleBankPort(ConfObjectRef o, Args... args)
        : BankPort<MappableConfObject>(o),
          b(this, "A bank created through the SimicsBankPort utility class",
            args...) {}

    TPortBank b;
};

/**
 * Creates a bank port configuration class with specified attributes.
 *
 * This template function provides two overloads for instantiating a configuration
 * class for a bank port, using the provided name and description. It leverages the
 * `make_class` function to create the class and then adds bank-specific properties
 * to it. The function supports optional additional arguments for enhanced flexibility.
 *
 * - @tparam TBankPort The type of the bank port to be created.
 * - @tparam TArg (Overload 2) The type of the additional argument passed to the bank port creation process.
 *
 * Overload 1:
 * - Parameters:
 *   - @param name The name of the bank port configuration class.
 *   - @param desc The description of the bank port configuration class.
 * - Usage:
 *   - Use this overload when you need to create a bank port configuration class without additional arguments.
 *
 * Overload 2:
 * - Parameters:
 *   - @param name The name of the bank port configuration class.
 *   - @param desc The description of the bank port configuration class.
 *   - @param arg A pointer to an additional argument used in the bank port creation process.
 * - Usage:
 *   - Use this overload when you need to create a bank port configuration class with an additional argument, such as a pointer to bank data.
 *
 * Return Value:
 * - @return A pointer to the created configuration class (`ConfClassPtr`).
 */
template <typename TBankPort> ConfClassPtr
make_bank_port(const std::string &name, const std::string &desc) {
    static_assert(std::is_base_of<BankPort<typename TBankPort::ParentType>,
                                  TBankPort>::value,
                  "TBankPort must be derived from BankPort");
    auto port = make_class<TBankPort>(name, "", desc);
    TBankPort::addBankProperties(port.get());
    return port;
}
template <typename TBankPort, typename TArg> ConfClassPtr
make_bank_port(const std::string &name, const std::string &desc, TArg *arg) {
    static_assert(std::is_base_of<BankPort<typename TBankPort::ParentType>,
                                  TBankPort>::value,
                  "TBankPort must be derived from BankPort");
    auto port = make_class<TBankPort>(name, "", desc, arg);
    TBankPort::addBankProperties(port.get());
    return port;
}

/**
 * Registers bank data as port objects within a configuration class hierarchy.
 *
 * This function facilitates the registration of bank data as port objects,
 * using the provided configuration class (`ConfClass`) and bank information
 * (`bank_t`).
 * It supports two overloads: one for a single bank and another for multiple
 * banks using an `std::initializer_list`.
 *
 * @tparam TParent The parent type used in the bank port creation process.
 * @param cls The configuration class where the bank ports are registered.
 * @param bank The bank data containing name, description, and registers.
 *             The caller must ensure that the `bank` parameter is not a
 *             temporary object (e.g., not an rvalue or a local variable that
 *             goes out of scope). The address of the `bank` object will be
 *             stored and used after the function call, so it must remain valid
 *             for the lifetime of the simulation.
 */
template <typename TParent>
void create_hierarchy_from_register_data(ConfClass *cls, const bank_t &bank) {
    const auto &[name, desc, registers] = bank;
    cls->add(make_bank_port<BankPort<TParent>, const bank_t>(
                     cls->name() + SEPARATOR + std::string(name.base_name()),
                     desc.data(), &bank),
             std::string("bank.") + name.data());
}
// When passing initializer_list by value, only the wrapper (which contains
// pointers to the elements) is copied, not the elements themselves.
template <typename TParent>
void create_hierarchy_from_register_data(
        ConfClass *cls, std::initializer_list<bank_t> register_data) {
    for (const auto &bank : register_data) {
        create_hierarchy_from_register_data<TParent>(cls, bank);
    }
}

}  // namespace simics

#endif
