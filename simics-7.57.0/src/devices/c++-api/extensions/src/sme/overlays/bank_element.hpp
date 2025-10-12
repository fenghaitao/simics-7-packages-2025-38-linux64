/*
  © 2024 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef VIRTUAL_BANK_ELEMENT_HPP_
#define VIRTUAL_BANK_ELEMENT_HPP_

#include "callback_overlay.h"
#include "simics/iface/value-accessor-interface.h"
#include "simics/iface/value-mutator-interface.h"
#include "sme/overlays/I_bank_element.hpp"

#define SME_CREATE_BANK_ELEMENT( name, object) sme::bank_element name( & object, & object, & object)
#define SME_SET_BANK_ELEMENT( name, object) name.set_interface(  & object, & object, & object)
#define SME_BANK_ELEMENT( object) sme::bank_element( & object, & object, & object)

namespace sme {

/**
 * @brief Provides a mechanism to abstract common methods from registers or fields to be used in aggragate algorithms.
 * 
 */
class bank_element
    : public simics::ValueAccessorInterface
    , public simics::ValueMutatorInterface
    , public sme::I_bank_element
{
private:

    struct RequiredInterfaces {
        simics::ValueAccessorInterface * accessor_if;
        simics::ValueMutatorInterface * mutator_if;
        sme::I_bank_element * bank_element_if;
    };

    RequiredInterfaces interfaces;
public:

    bank_element() {
        interfaces.accessor_if = nullptr;
        interfaces.mutator_if = nullptr;
        interfaces.bank_element_if = nullptr;
    }

    bank_element( simics::ValueAccessorInterface * _accessor, simics::ValueMutatorInterface * _mutator, sme::I_bank_element * _overlay) {
        set_interface( _accessor, _mutator, _overlay);
    }

    void set_interface( simics::ValueAccessorInterface * _accessor, simics::ValueMutatorInterface * _mutator, sme::I_bank_element * _overlay) {
        interfaces.accessor_if = _accessor;
        interfaces.mutator_if = _mutator;
        interfaces.bank_element_if = _overlay;
    }
    
    virtual uint64_t get() const {
        return( interfaces.accessor_if->get());     
    }

    virtual uint64_t read(uint64_t enabled_bits = -1ULL) {
        return( interfaces.accessor_if->read( enabled_bits));     
    }

    virtual void set(uint64_t value) {
        interfaces.mutator_if->set( value);
    }

    virtual void write(uint64_t value, uint64_t enabled_bits = -1ULL) {
        interfaces.mutator_if->write( value, enabled_bits);
    }

    virtual pattern_rule_container * get_rule_container( stage::E _stage) {
        return( interfaces.bank_element_if->get_rule_container( _stage));
    }

    virtual void deactivate_rule( stage::E _stage, std::string _name) {
        interfaces.bank_element_if->deactivate_rule( _stage, _name);
    }

    virtual void activate_rule( stage::E _stage, std::string _name) {
        interfaces.bank_element_if->activate_rule( _stage, _name);
    }

    virtual void process_pre_read_rules( uint64_t _old_value, uint64_t _new_value) {
        interfaces.bank_element_if->process_pre_read_rules( _old_value, _new_value);
    }

    virtual void process_post_read_rules( uint64_t _old_value, uint64_t _new_value) {
        interfaces.bank_element_if->process_post_read_rules( _old_value, _new_value);
    }

    virtual void process_pre_write_rules( uint64_t _old_value, uint64_t _new_value) {
        interfaces.bank_element_if->process_pre_write_rules( _old_value, _new_value);
    }

    virtual void process_post_write_rules( uint64_t _old_value, uint64_t _new_value) {
        interfaces.bank_element_if->process_post_write_rules( _old_value, _new_value);
    }

    virtual I_pattern_rule * add_rule( std::function< void()> _func, stage::E _stage, type::E _type, std::string _name, ...) {
        va_list args;
        va_start( args, _name);

        std::vector<uint64_t> ordered_arguments;
        // 3 is the max, va_args will just put junk if we go beyond what is filled out by the user
        for (int i = 0; i < 3; ++i) {
            ordered_arguments.push_back(va_arg(args, uint64_t));
        }

        I_pattern_rule * retval = interfaces.bank_element_if->__add_rule( _func, _stage, _type, _name, ordered_arguments);
        va_end( args);
        return( retval);
    }

    I_pattern_rule * add_user_rule( std::function< void( uint64_t, uint64_t) > _func, stage::E _stage, std::string _name, ...) {
        va_list args;
        va_start( args, _name);
        I_pattern_rule * retval = interfaces.bank_element_if->__add_rule( _func, _stage, type::E::USER_DEFINED, _name, args);
        va_end( args);
        return( retval);
    }

    virtual uint64_t internal_read(uint64_t enabled_bits = -1ULL) {
        return( interfaces.bank_element_if->internal_read( enabled_bits));
    }

    virtual void internal_write(uint64_t value, uint64_t enabled_bits = -1ULL) {
        interfaces.bank_element_if->internal_write( value, enabled_bits);
    }
};

}

#endif
