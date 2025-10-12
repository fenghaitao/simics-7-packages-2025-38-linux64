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

#ifndef SSA_FIELD_HPP_
#define SSA_FIELD_HPP_

#include "sme/scaffolding/features/features.hpp"
#include "sme/scaffolding/I_register.hpp"
#include "sme/scaffolding/I_field.hpp"
#include "sme/aqpp/print/sme_print.hpp"

#include <simics/cc-modeling-api.h>

#include <iostream>
#include <type_traits>

namespace sme
{

// TODO: 1) Add Field / Register only Feature Control...

/**
 * @brief pass through wrapper; adds parent, offset, bitwidth & notification rules to T
 * 
 * @tparam T is a definition of Field or child of Field...
 */
template< typename T, uint8_t FEATURES = access_features::NONE >
class field : public I_field, public T {
public:

    /**
     * @brief Construct a new field object
     *
     * @param obj* pointer to the MappableConfObject
     * @param name begins with the bank name, e.g, "bankA.registerB.fieldC"
     */
    field( simics::MappableConfObject *obj, const std::string &name)
        : T(obj, name)
    {}

    /**
     * @brief Construct a new field object
     * 
     */
    field(const field&) = delete;

    /**
     * @brief 
     * 
     * @return field& 
     */
    field& operator=(const field&) = delete;

    /**
     * @brief Construct a new field object
     *
     * @param rhs
     */
    field(field &&rhs) : T(rhs) {;}

    /**
     * @brief
     *
     * @param rhs
     * @return field&
     */
    field& operator=(field&& rhs) {
        T::operator=(rhs);
        return *this;
    }

    /**
     * @brief conditionally defined method for INTERNAL_ACCESS feature
     * 
     * @return access_type::E
     */
    template< uint8_t F = FEATURES, 
        std::enable_if_t< ct_features<F>::has_internal_access, bool> = 0>
    access_type::E get_one_shot_internal_indicator()
    {
        if (SIM_class_has_attribute(SIM_object_class(T::dev_obj()->obj().object()), "internal_access")) {
            auto internal = SIM_attr_boolean(SIM_get_attribute(T::dev_obj()->obj().object(), "internal_access"));
            SIM_LOG_INFO(4, T::dev_obj()->obj().object(), 0, "DEBUG::: internal=%d", internal);
            return internal ? access_type::E::FROM_ATTRIBUTE : access_type::E::NO;
        } else {
            return access_type::E::NO;
        }
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
        uint64_t old_data = 0xdecafe22;
        uint64_t new_data = 0xdecafe22;
        uint64_t current_value = 0xdecafe23;
        uint64_t mask = ((1ULL << T::number_of_bits()) - 1ULL) << T::offset();

        I_reg<FEATURES> * mp_parent = dynamic_cast< I_reg<FEATURES> *>( T::parent());

        // At this point, we are committed to either a field-only or a register transaction
        // To prevent callbacks that are accessing their own fields from thinking that they
        // are register transactions, clear the indication now.
        bool register_transaction = mp_parent && mp_parent->is_register_transaction();
        if (register_transaction) {
            mp_parent->set_register_transaction(false);
        }

        // process parent rules if field only transaction
        if(mp_parent && !register_transaction) {
            if constexpr( ct_features<FEATURES>::has_internal_access) { 
                if( _access_type == access_type::E::FROM_internal_METHOD) {
                    mp_parent->internal_indicator.establish( _access_type); 
                } else {
                    mp_parent->internal_indicator.establish(get_one_shot_internal_indicator()); 
                }
            }
            old_data = mp_parent->__get();
            new_data = value & enabled_bits;
            new_data = (new_data << T::offset()) & mask;
            new_data = (old_data & ~mask) | new_data;
            SIM_DEBUG( "register process_pre_read_rules for : " << __name() << ", old_value: " << old_data << ", new_value: " << new_data )
            mp_parent->process_pre_read_rules( old_data, new_data);
        }
        
        SIM_DEBUG( "field process_pre_read_rules for : " << __name() << ", old_value: " << value << ", new_value: " << value )
        this->process_pre_read_rules( value, value);
        uint64_t read_value;

        if constexpr( ct_features<FEATURES>::has_internal_access) { 
            if (mp_parent && mp_parent->internal_indicator.is_internal()) {
                SIM_LOG_INFO(4, T::bank_obj_ref(), 0, "DEBUG::: Internal field read %s.%s", mp_parent->__name().data(), T::name().data());
                read_value = T::get() & enabled_bits;
                SIM_DEBUG( "field process_post_read_rules for : " << __name() << ", old_value: " << value << ", new_value: " << read_value )
	        } else {
                SIM_LOG_INFO(4, T::bank_obj_ref(), 0, "DEBUG::: Non-internal field read %s.%s", (mp_parent) ? mp_parent->__name().data() : "", T::name().data());
                read_value = T::read( enabled_bits);
                SIM_DEBUG( "field process_post_read_rules for : " << __name() << ", old_value: " << value << ", new_value: " << read_value )
            }
        } else {
            SIM_LOG_INFO(4, T::bank_obj_ref(), 0, "DEBUG::: Non-internal field read %s.%s", (mp_parent) ? mp_parent->__name().data() : "", T::name().data());
            read_value = T::read( enabled_bits);
            SIM_DEBUG( "field process_post_read_rules for : " << __name() << ", old_value: " << value << ", new_value: " << read_value )
        }

        if constexpr( ct_features<FEATURES>::has_change_on_read) { // Feature for CHANGE-ON-READ
            current_value = T::get();  // Capture current field contents in case previous read had a side-effect
        }

        this->process_post_read_rules( value, read_value);

        if constexpr( ct_features<FEATURES>::has_change_on_read) { // Feature for CHANGE-ON-READ
            // for change-on-read, the value returned is pre-cleared value, but the side-effect of
            // clearing the enabled_bits is still sitting in the register, so use the fetched value
            // above and process any post-write rules for this field (and its parent if this is a
            // single field access)
            if (current_value != read_value) {  // Handle change cause by read side-effect
                SIM_LOG_INFO_STREAM(4, T::bank_obj_ref(), 0, "DEBUG::: change-on-read field read_value->current_value 0x" << std::hex << read_value << "->0x" << std::hex << current_value);
                this->process_post_write_rules( read_value, current_value);
            }
        }

        // process parent rules if field-only transaction
        if(mp_parent && !register_transaction) {
            SIM_DEBUG( "register process_post_read_rules for : " << __name() << ", old_value: " << old_data << ", new_value: " << new_data )
            mp_parent->process_post_read_rules( old_data, new_data);


            if constexpr( ct_features<FEATURES>::has_change_on_read) { // TODO: Possible Feature for CHANGE-ON-READ
                // see above regarding change-on-read
                if (current_value != read_value) {  // Handle change caused by read side-effect
                    new_data = mp_parent->__get(); // this is the current_value for the register
                    old_data = read_value & enabled_bits;
                    old_data = (old_data << T::offset()) & mask;
                    old_data = (new_data & ~mask) | old_data;
                    SIM_LOG_INFO_STREAM(4, T::bank_obj_ref(), 0, "DEBUG::: parent change-on-read field read_value->current_value 0x" << std::hex << old_data << "->0x" << std::hex << new_data);
                    
                    // compare register value after pre-read rule with side effect of the read
                    mp_parent->process_post_write_rules( old_data, new_data);
                }
            }

            if constexpr( ct_features<FEATURES>::has_internal_access) { 
                mp_parent->internal_indicator.clear();
            }
        }

        // Now we need to restore the register transaction indication for the next field
        if (register_transaction) {
            mp_parent->set_register_transaction(true);
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
        uint64_t old_value = T::get();
        uint64_t old_data = 0xdecafe22;
        uint64_t new_data = 0xdecafe22;
        uint64_t mask = ((1ULL << T::number_of_bits()) - 1ULL) << T::offset();

        I_reg<FEATURES> * mp_parent = dynamic_cast< I_reg<FEATURES> *>( T::parent());

        // At this point, we are committed to either a field-only or a register transaction
        // To prevent callbacks that are accessing their own fields from thinking that they
        // are register transactions, clear the indication now.
        bool register_transaction = mp_parent && mp_parent->is_register_transaction();
        if (register_transaction) {
            mp_parent->set_register_transaction(false);
        }

        // process parent rules if field only transaction
        if(mp_parent && !register_transaction) {
            if constexpr( ct_features<FEATURES>::has_internal_access) { 
                if( _access_type == access_type::E::FROM_internal_METHOD) {
                    mp_parent->internal_indicator.establish( _access_type); 
                } else {
                    mp_parent->internal_indicator.establish(get_one_shot_internal_indicator());
                }
            }
            old_data = mp_parent->__get();
            new_data = value & enabled_bits;
            new_data = (new_data << T::offset()) & mask;
            new_data = (old_data & ~mask) | new_data;
            SIM_DEBUG( "register process_pre_write_rules for : " << __name() << ", old_value: " << old_data << ", new_value: " << new_data )
            mp_parent->process_pre_write_rules( old_data, new_data);
        }

        SIM_DEBUG( "field process_pre_write_rules for : " << __name() << ", old_value: " << old_value << ", new_value: " << value )
        this->process_pre_write_rules( old_value, value);

        if constexpr( ct_features<FEATURES>::has_internal_access) { 
// TODO: 1) mp_parent != nullptr is a quick-fix for TODO 1
            if( mp_parent && mp_parent->internal_indicator.is_internal()) {
                SIM_LOG_INFO_STREAM( 4, T::bank_obj_ref(), 0, 
                    "DEBUG::: Internal field write " << T::name().data() << "=0x" << std::hex << value);
                T::set((old_value & ~enabled_bits) | (value & enabled_bits));
                SIM_DEBUG( "field process_post_write_rules for : " << __name() << ", old_value: " << old_value << ", new_value: " << value )
            } else {
                SIM_LOG_INFO_STREAM( 4, T::bank_obj_ref(), 0, 
                    "DEBUG::: Non-internal field write " << T::name().data() << "=0x" << std::hex << value);
                T::write(value, enabled_bits);
                SIM_DEBUG( "field process_post_write_rules for : " << __name() << ", old_value: " << old_value << ", new_value: " << value )
            }
        } else {
            T::write( value, enabled_bits);
            SIM_DEBUG( "field process_post_write_rules for : " << __name() << ", old_value: " << old_value << ", new_value: " << value )
        }

        this->process_post_write_rules( old_value, T::get());

        // process parent rules if field only transaction
        if(mp_parent && !register_transaction) {
            new_data = T::get() & enabled_bits;
            new_data = (new_data << T::offset()) & mask;
            new_data = (old_data & ~mask) | new_data;
            mp_parent->process_post_write_rules( old_data, new_data);
            if constexpr( ct_features<FEATURES>::has_internal_access) { 
                mp_parent->internal_indicator.clear();
            }
        }

        // Now we need to restore the register transaction indication for the next field
        if (register_transaction) {
            mp_parent->set_register_transaction(true);
        }
    }

public:

    /**
     * @brief Set the data and do not trigger any side effects
     *  API passthrough to allow user to customize
     * 
     * @param value The new value to set the field data to
     */
    void set(uint64_t value) override {
        T::set(value);
    }
    /**
     * @brief Get the data and do not trigger any side effects
     *  API passthrough to allow user to customize
     * 
     * @return uint64_t 
     */
    uint64_t get() const override {
        return T::get();
    }

    /**
     * @brief read data from mask
     * 
     * @param enabled_bits represents mask (from 0 offset of this field)
     * @return uint64_t 
     */
    uint64_t read(uint64_t enabled_bits = -1ULL) override {
        return( do_read( enabled_bits, access_type::E::NO));
    }

    /**
     * @brief write data with mask
     *
     * @param value to write
     * @param enabled_bits represents mask (from 0 offset of this field)
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
            return( do_read( enabled_bits, access_type::E::FROM_internal_METHOD));
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
            do_write( value, enabled_bits, access_type::E::FROM_internal_METHOD);
        } else {
            SIM_LOG_UNIMPLEMENTED(2, T::bank_obj_ref(), 0, "DEBUG::: internal_write IS NOT AVAILABLE because access_features::INTERNAL_ACCESS is not enabled.");
        }
    }

    /**
     * @brief api pass through: name() - returns name of field.
     * 
     * @return std::string_view
     */
    std::string_view __name() {
        return this->name();
    }

};

}

#endif
