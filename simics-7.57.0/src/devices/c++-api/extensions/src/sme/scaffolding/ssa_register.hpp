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

#ifndef SSA_REGISTER_HPP_
#define SSA_REGISTER_HPP_

#include "sme/scaffolding/features/features.hpp"
#include "sme/scaffolding/I_register.hpp"
#include "sme/scaffolding/I_field.hpp"
#include "sme/aqpp/print/sme_print.hpp"

namespace sme
{

/**
 * @brief pass through wrapper; adds parent, offset, bitwidth & notification rules to T
 *
 * @tparam T is a definition of Register or child of Register...
 */
template< typename T, uint8_t FEATURES = access_features::NONE >
class reg : public I_reg<FEATURES>, public T {
private:

    /**
     * @brief is register level transaction
     *
     */
    bool m_live_transaction;
    bool m_is_internal;

public:
    bool implemented = false;

    /**
     * @brief conditionally defined method for INTERNAL_ACCESS feature
     * 
     * @return access_type::E
     */
    template< uint8_t F = FEATURES, 
        std::enable_if_t< ct_features<F>::has_internal_access, bool> = 0>
    access_type::E get_one_shot_internal_indicator() {
        if (SIM_class_has_attribute(SIM_object_class(T::dev_obj()->obj().object()), "internal_access")) {
            auto internal = SIM_attr_boolean(SIM_get_attribute(T::dev_obj()->obj().object(), "internal_access"));
            SIM_LOG_INFO(4, T::dev_obj()->obj().object(), 0, "DEBUG::: internal=%d", internal);
            return internal ? access_type::E::FROM_ATTRIBUTE : access_type::E::NO;
        } else {
            return access_type::E::NO;
        }
    }

    /**
     * @brief Construct a new reg object for an UnmappedRegister template
     *
     * @param obj* pointer to the MappableConfObject
     * @param name generic string, e.g, "bankA.registerB"
     * @param byte_size simics::ByteSize number of bytes for this register
     * @param init_val simics::InitValue value for this register
     */
    reg( simics::MappableConfObject *obj, const std::string &name,
         simics::ByteSize byte_size, simics::InitValue init_val)
        : T(obj, name, byte_size, init_val)
        , m_live_transaction( false)
    {
    }

    /**
     * @brief Construct a new reg object for a BankRegister template
     *
     * @param obj* pointer to the MappableConfObject
     * @param name begins with the bank name, e.g, "bankA.registerB"
     */
    reg( simics::MappableConfObject *obj, const std::string &name)
        : T(obj, name)
        , m_live_transaction( false)
    {
    }

    /**
     * @brief Construct a new reg object
     *
     */
    reg(const reg&) = delete;

    /**
     * @brief
     *
     * @return reg&
     */
    reg& operator=(const reg&) = delete;

    /**
     * @brief Construct a new reg object
     *
     * @param rhs
     */
    reg(reg &&rhs) : T(rhs) {;}

    /**
     * @brief
     *
     * @param rhs
     * @return reg&
     */
    reg& operator=(reg&& rhs) {
        T::operator=(rhs);
        return *this;
    }

protected:
    /**
     * @brief read data from mask with a particular access type
     * 
     * @param enabled_bits represents mask (from 0 offset of this field)
     * @param _access_type represents access_type::E used to maintain access type state
     * @return uint64_t 
     */
    uint64_t do_read(uint64_t enabled_bits, access_type::E _access_type) {
        uint64_t value = T::get();
        uint64_t current_value = 0xdecafe23;

        if constexpr( ct_features<FEATURES>::has_internal_access) { 
            if( _access_type == access_type::E::FROM_internal_METHOD) {
                this->internal_indicator.establish(_access_type);
            } else {
                this->internal_indicator.establish(get_one_shot_internal_indicator());
            }
        }
        SIM_DEBUG( "register process_pre_read_rules for : " << __name() << ", value: " << value )
        this->process_pre_read_rules(value, value);
        // TODO: Check that pre-read rules did not change the value and print SME_DEBUG

        if (!implemented) {
            std::string msg = std::string("*** Read to Reg:  ") + static_cast<std::string>(T::name()) + " ***";
            SIM_LOG_UNIMPLEMENTED(2, T::bank_obj_ref(), 0, "%s", msg.c_str());
        }

        m_live_transaction = true;
        uint64_t read_value;

        if constexpr( ct_features<FEATURES>::has_internal_access) { 
            auto access = this->internal_indicator.is_internal() ? "Internal" : "Non-internal";
            SIM_LOG_INFO(4, T::bank_obj_ref(), 0, "DEBUG::: %s read", access);
        }

        read_value = T::read( enabled_bits);

        if constexpr( ct_features<FEATURES>::has_change_on_read) { // Feature for CHANGE-ON-READ
            current_value = T::get();  // Capture current field contents in case previous read had a side-effect
        }

        SIM_DEBUG( "register process_post_read_rules for : " << __name() << ", old_value: " << value << ", new_value: " << read_value )
        m_live_transaction = false;

        this->process_post_read_rules(value, read_value);

        if constexpr( ct_features<FEATURES>::has_change_on_read) { // Feature for CHANGE-ON-READ
            // for change-on-read, the value returned is pre-cleared value, but the side-effect of
            // clearing the enabled_bits is still sitting in the register, so use the fetched value
            // above and process any post-write rules for this register
            if (current_value != read_value) {
                SIM_LOG_INFO_STREAM(4, T::bank_obj_ref(), 0, "DEBUG::: change-on-read post-write rules read_value->current_value 0x" << std::hex << read_value << "->0x" << std::hex << current_value);
                this->process_post_write_rules( read_value, current_value);
            }
        }

        if constexpr( ct_features<FEATURES>::has_internal_access) { 
            this->internal_indicator.clear();
        }
        return read_value;
    }

    /**
     * @brief write data with mask with a particular access type
     *
     * @param value to write
     * @param enabled_bits represents mask (from 0 offset of this field)
     * @param _access_type represents access_type::E used to maintain access type state
     */
    void do_write(uint64_t value, uint64_t enabled_bits, access_type::E _access_type) {
        if constexpr( ct_features<FEATURES>::has_internal_access) { 
            if( _access_type == access_type::E::FROM_internal_METHOD) {
                this->internal_indicator.establish(_access_type);
            } else {
                this->internal_indicator.establish(get_one_shot_internal_indicator());
            }
        }
        uint64_t old_value = T::get();

        SIM_DEBUG( "register process_pre_write_rules for : " << __name() << ", old_value: " << old_value << ", new_value: " << value )
        this->process_pre_write_rules( old_value, value);

        if (!implemented) {
            std::string msg = std::string("*** Write to Reg:  ") + static_cast<std::string>(T::name()) + " ***";
            SIM_LOG_UNIMPLEMENTED(2, T::bank_obj_ref(), 0, "%s", msg.c_str());
        }

        m_live_transaction = true;
        if constexpr( ct_features<FEATURES>::has_internal_access) { 
            auto access = this->internal_indicator.is_internal() ? "Internal" : "Non-internal";
            SIM_LOG_INFO(4, T::bank_obj_ref(), 0, "DEBUG::: %s write", access); // <<- Debug ONLY
        }
        T::write(value, enabled_bits);
        SIM_DEBUG( "register process_post_write_rules for : " << __name() << ", old_value: " << old_value << ", new_value: " << value )
        m_live_transaction = false;

        this->process_post_write_rules( old_value, T::get());
        if constexpr( ct_features<FEATURES>::has_internal_access) { 
            this->internal_indicator.clear();
        }
    }

public:

    /**
     * @brief read data from mask
     *
     * @param enabled_bits represents mask
     * @return uint64_t
     */
    uint64_t read(uint64_t enabled_bits = -1ULL) override {
        uint64_t read_value = do_read( enabled_bits, access_type::E::NO);
        return read_value;
    }

    /**
     * @brief writes value with mask
     *
     * @param value to write
     * @param enabled_bits represents mask
     */
    void write(uint64_t value, uint64_t enabled_bits = -1ULL) override {
        do_write( value, enabled_bits, access_type::E::NO);
    }

    /**
     * @brief internal_read data from mask
     *
     * @param enabled_bits represents mask
     * @return uint64_t
     */
    uint64_t internal_read(uint64_t enabled_bits = -1ULL) {
        if constexpr( ct_features<FEATURES>::has_internal_access) { 
            uint64_t read_value = do_read( enabled_bits, access_type::FROM_internal_METHOD);
            return read_value;
        } else {
            SIM_LOG_UNIMPLEMENTED(2, T::bank_obj_ref(), 0, "DEBUG::: internal_read IS NOT AVAILABLE because access_features::INTERNAL_ACCESS is not enabled.");
            return 0;
        }
    }

    /**
     * @brief internal_write value with mask
     *
     * @param value to write
     * @param enabled_bits represents mask
     */
    void internal_write(uint64_t value, uint64_t enabled_bits = -1ULL) {
        if constexpr( ct_features<FEATURES>::has_internal_access) { 
            do_write( value, enabled_bits, access_type::FROM_internal_METHOD);
        } else {
            SIM_LOG_UNIMPLEMENTED(2, T::bank_obj_ref(), 0, "DEBUG::: internal_write IS NOT AVAILABLE because access_features::INTERNAL_ACCESS is not enabled.");
        }
    }

    /**
     * @brief Get if this register has been implemented by the user.
     *
     * @return true
     * @return false
     */
    bool get_implemented() {
        return implemented;
    }

    /**
     * @brief Set if the register has been implemented by the user.
     *
     */
    void set_implemented() {
        implemented = true;
    }

    /**
     * @brief returns if the transaction is initiated from a register or not (field).
     *
     * @return true
     * @return false
     */
    bool is_register_transaction() {
        return m_live_transaction;
    }

    /**
     * @brief returns if the transaction is initiated from a register or not (field).
     *
     * @return true
     * @return false
     */
    void set_register_transaction(bool value) {
        m_live_transaction = value;
    }

    /**
     * @brief api pass through: name() - returns name of field.
     *
     * @return std::string_view
     */
    std::string_view __name() {
        return this->name();
    }

    /**
     * @brief api pass through: get() - returns value of field.
     *
     * @return uint64_t
     */
    uint64_t __get() {
        return this->get();
    }

};

}

#endif
