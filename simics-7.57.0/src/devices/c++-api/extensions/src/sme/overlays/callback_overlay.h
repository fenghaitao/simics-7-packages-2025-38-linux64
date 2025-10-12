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

//-*- C++ -*-

#ifndef CPP_API_EXTENSIONS_SRC_SME_OVERLAYS_CALLBACK_OVERLAY_H
#define CPP_API_EXTENSIONS_SRC_SME_OVERLAYS_CALLBACK_OVERLAY_H

#include <stdarg.h>
#include <iostream>

#include "sme/aqpp/abstraction/compiler/_inline.h"

#include "sme/pattern_rules/I_pattern_rule.h"
#include "sme/pattern_rules/pattern_rule_container.h"

#include "sme/pattern_rules/notify.h"
#include "sme/pattern_rules/masked.h"
#include "sme/pattern_rules/pattern.h"
#include "sme/pattern_rules/rising_bit.h"
#include "sme/pattern_rules/falling_bit.h"
#include "sme/pattern_rules/rising.h"
#include "sme/pattern_rules/falling.h"
#include "sme/pattern_rules/user_defined.h"

#include "sme/overlays/I_bank_element.hpp"

namespace sme
{

/**
 * @brief class which houses all four rule containers, only allocated if utilized.
 * 
 */
class callback_overlay : public I_bank_element {
public:
    /**
     * @brief Construct a new callback overlay object.
     * 
     */
    callback_overlay()
        : m_pre_read( nullptr)
        , m_post_read( nullptr)
        , m_pre_write( nullptr)
        , m_post_write( nullptr)
    {;}

    /**
     * @brief Destroy the callback overlay object.
     * 
     */
    ~callback_overlay() {
        if (m_pre_read != nullptr) {
            // Delete the rules within the container
            delete_rules_from_container(m_pre_read);
            // Delete the rule container
            delete m_pre_read;
        }
        if (m_post_read != nullptr) {
            // Delete the rules within the container
            delete_rules_from_container(m_post_read);
            // Delete the rule container
            delete m_post_read;
        }
        if (m_pre_write != nullptr) {
            // Delete the rules within the container
            delete_rules_from_container(m_pre_write);
            // Delete the rule container
            delete m_pre_write;
        }
        if (m_post_write != nullptr) {
            // Delete the rules within the container
            delete_rules_from_container(m_post_write);
            // Delete the rule container
            delete m_post_write;
        }
    }
    
    /**
     * @brief Get the rule container object.
     * 
     * @param _stage determines which rule container
     * @return pattern_rule_container* 
     */
    pattern_rule_container * get_rule_container( stage::E _stage) {
        switch( _stage)	{
            case stage::PRE_READ:
                if( m_pre_read == nullptr) m_pre_read = new pattern_rule_container();
                return( m_pre_read);
                break;
            case stage::POST_READ:
                if( m_post_read == nullptr) m_post_read = new pattern_rule_container();
                return( m_post_read);
                break;
            case stage::PRE_WRITE:
                if( m_pre_write == nullptr) m_pre_write = new pattern_rule_container();
                return( m_pre_write);
                break;
            case stage::POST_WRITE:
                if( m_post_write == nullptr) m_post_write = new pattern_rule_container();
                return( m_post_write);
                break;
            default:
                std::cerr << "[ERROR][get_rule_container]: Invalid stage for rule container! (" << _stage << ")" << std::endl;
                break;
        }
        return( nullptr);
    }

    /**
     * @brief deactivates rule by name at stage.
     * 
     * @param _stage of processing
     * @param _name of rule
     */
    void deactivate_rule( stage::E _stage, std::string _name) {
        pattern_rule_container *container = get_rule_container(_stage);
        if (container) {
            container->deactivate_rule(_name);
        }
    }
    
    /**
     * @brief activates rule by name at stage.
     * 
     * @param _stage of processing
     * @param _name of rule
     */
    void activate_rule( stage::E _stage, std::string _name) {
        pattern_rule_container *container = get_rule_container(_stage);
        if (container) {
            container->activate_rule(_name);
        }
    }

    /**
     * @brief processes pre_read_rules.
     * 
     * @param _old_value value of the register/field
     * @param _new_value always the same as the old value
     */
    void process_pre_read_rules( uint64_t _old_value, uint64_t _new_value) {
        if( this->m_pre_read != nullptr) {
            this->m_pre_read->process_active_rules( _old_value, _new_value);
        }
    }
    
    /**
     * @brief processes post_read_rules.
     * 
     * @param _old_value value of the register/field
     * @param _new_value could be a modified new value, usually same as old
     */
    void process_post_read_rules( uint64_t _old_value, uint64_t _new_value) {
        if( this->m_post_read != nullptr) {
            this->m_post_read->process_active_rules( _old_value, _new_value);
        }
    }
    
    /**
     * @brief processes pre_write_rules.
     * 
     * @param _old_value value of the register/field
     * @param _new_value new value of the register/field (from bus)
     */
    void process_pre_write_rules( uint64_t _old_value, uint64_t _new_value) {
        if( this->m_pre_write != nullptr) {
            this->m_pre_write->process_active_rules( _old_value, _new_value);
        }
    }
    
    /**
     * @brief processes post_write_rules.
     * 
     * @param _old_value value of the register/field
     * @param _new_value new value of the register/field (from bus)
     */
    void process_post_write_rules( uint64_t _old_value, uint64_t _new_value) {
        if( this->m_post_write != nullptr) {
            this->m_post_write->process_active_rules( _old_value, _new_value);
        }
    }

    /**
     * @brief add a rule to this entity.
     * 
     * @param _func is a lambda definition of what should occur.  For scoping reasons the lambda is typically declared as:
                    [this]() -> void {
                        do_something_interesting();
                    });
     * @param _stage of processing
     * @param _type of rule
     * @param _name of rule
     * @param ... :: variadic parameters for rule creation, please see notify.h, masked.h, pattern.h, rising_bit.h, falling_bit.h
     * @return I_pattern_rule* new rule or nullptr if failed to allocate
     */
    I_pattern_rule * add_rule( std::function< void()> _func, stage::E _stage, type::E _type, std::string _name, ...) {
        va_list args;
        std::vector<uint64_t> ordered_arguments;
        va_start(args, _name);
        // 3 is the max, va_args will just put junk if we go beyond what is filled out by the user
        for (int i = 0; i < 3; ++i) {
            ordered_arguments.push_back(va_arg(args, uint64_t));
        }
        va_end(args);
        I_pattern_rule * retval = this->__add_rule( _func, _stage, _type, _name, ordered_arguments);
        return( retval);
    }

    I_pattern_rule * add_user_rule( std::function< void( uint64_t, uint64_t)> _func, stage::E _stage, std::string _name, ...) {
        va_list args;
        va_start( args, _name);
        I_pattern_rule * retval = this->__add_rule( _func, _stage, type::E::USER_DEFINED, _name, args);
        va_end( args);
        return( retval);
    }

protected:
    /**
     * @brief real implementation of add a rule to this entity (decompressed va_list). For pre-defined rules.
     * 
     * @param _func is a lambda definition of what should occur.
     * @param _stage of processing
     * @param _type of rule
     * @param _name of rule
     * @param args va_list of args for rule creation
     * @return I_pattern_rule* new rule or nullptr if failed to allocate
     */
    _keep_hot I_pattern_rule * __add_rule( std::function< void()> _func, stage::E _stage, type::E _type, std::string _name, std::vector<uint64_t> &_ordered_args) {
        I_pattern_rule *rule = nullptr;
        pattern_rule_container *rules = get_rule_container( _stage);

        switch( _type)
        {
            case type::NOTIFY:
                rule = new sme::rules::notify();
                break;
            case type::MASKED:
                rule = new sme::rules::masked(_ordered_args[0]);
                break;
            case type::PATTERN:
                rule = new sme::rules::pattern(_ordered_args[0],  _ordered_args[1],  _ordered_args[2]);
                break;
            case type::RISING_BIT:
                rule = new sme::rules::rising_bit(uint8_t(_ordered_args[0]));
                break;
            case type::FALLING_BIT:
                rule = new sme::rules::falling_bit(uint8_t(_ordered_args[0]));
                break;
            case type::RISING:
                rule = new sme::rules::rising();
                break;
            case type::FALLING:
                rule = new sme::rules::falling();
                break;
            case type::USER_DEFINED:
                std::cerr << "[ERROR][add_rule]: User defined rules must use add_user_rule and prototype 'void func( uint64_t & _old, uint64_t & _new)'" << std::endl;
                break;
            default:
                std::cerr << "[ERROR][add_rule]: Invalid stage for rule container! (" << _stage << ")" << std::endl;
                break;
        }

        if (rules != nullptr && rule != nullptr) {
            rules->add_rule( _name, rule);
            rule->action( _func);
        }
        else if (rules == nullptr) {
            // If the container is invalid we can't have a valid rule
            if (rule) {
                delete(rule);
                rule = nullptr;
            }
        }

        return(rule);
    }

    /**
     * @brief real implementation of add a rule to this entity (decompressed va_list). For user defined rules.
     * 
     * @param _func is a lambda definition of what should occur.
     * @param _stage of processing
     * @param _type of rule
     * @param _name of rule
     * @param args va_list of args for rule creation
     * @return I_pattern_rule* new rule or nullptr if failed to allocate
     */
    _keep_hot I_pattern_rule * __add_rule( std::function< void( uint64_t, uint64_t)> _func, stage::E _stage, type::E _type, std::string _name, va_list & args) {

        I_pattern_rule *rule = nullptr;
        pattern_rule_container *rules = get_rule_container( _stage);

        switch( _type)
        {
            case type::NOTIFY:
            case type::MASKED:
            case type::PATTERN:
            case type::RISING_BIT:
            case type::FALLING_BIT:
            case type::RISING:
            case type::FALLING:
                std::cerr << "[ERROR][add_rule]: Non user defined rules must use add rule and prototype 'void func()'" << std::endl;
                break;
            case type::USER_DEFINED:
                rule = new sme::rules::user_defined();
                break;
            default:
                std::cerr << "[ERROR][__add_rule]: Invalid stage for rule container! (" << _stage << ")" << std::endl;
                break;
        }

        if (rules != nullptr && rule != nullptr) {
            rules->add_rule( _name, rule);
            rule->action( _func);
        }
        else if (rules == nullptr) {
            // If the container is invalid we can't have a valid rule
            if (rule) {
                delete(rule);
                rule = nullptr;
            }
        }

        return(rule);
    }

    /**
     * @brief Free the memory from the rules within the rule container
     * 
     * @param _rule_container is a container to clean the rule memory from.
     */
    void delete_rules_from_container(pattern_rule_container *_rule_container) {
        // Delete the rules within the container
        std::map< std::string, I_pattern_rule *> rule_map = _rule_container->get_active_rules();
        std::map< std::string, I_pattern_rule *>::iterator it;
        for(it = rule_map.begin(); it != rule_map.end(); ++it) {
            delete(it->second);
        }
        rule_map = _rule_container->get_inactive_rules();
        for(it = rule_map.begin(); it != rule_map.end(); ++it) {
            delete(it->second);
        }
    }


    /**
     * @brief pre_read rule container (ptr).
     * 
     */
    pattern_rule_container * m_pre_read;

    /**
     * @brief post_read rule container (ptr).
     * 
     */
    pattern_rule_container * m_post_read;

    /**
     * @brief pre_write rule container (ptr).
     * 
     */
    pattern_rule_container * m_pre_write;

    /**
     * @brief post_write rule container (ptr).
     * 
     */
    pattern_rule_container * m_post_write;

};

}

#endif
