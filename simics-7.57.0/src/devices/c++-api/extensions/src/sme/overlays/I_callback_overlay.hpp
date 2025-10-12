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

#ifndef CPP_API_EXTENSIONS_SRC_SME_OVERLAYS_I_CALLBACK_OVERLAY_H
#define CPP_API_EXTENSIONS_SRC_SME_OVERLAYS_I_CALLBACK_OVERLAY_H

#include <stdarg.h>
#include <iostream>

#include "sme/aqpp/abstraction/compiler/_inline.h"

namespace sme
{

/**
 * @brief point of a register/field read or write a rule executes on
 * 
 */
struct stage {
    enum E {
        PRE_READ = 0,
        POST_READ,
        PRE_WRITE,
        POST_WRITE
    };
};

/**
 * @brief type of rule to be applied
 * 
 */
struct type {
    enum E {
        NOTIFY = 0,
        MASKED,
        PATTERN,
        RISING_BIT,
        FALLING_BIT,
        RISING,
        FALLING,
        USER_DEFINED,
        NOT_IMPLEMENTED
    };
};

/**
 * @brief interface for public methods of callback_overlay
 * 
 */
class I_callback_overlay {
public:
    virtual pattern_rule_container * get_rule_container( stage::E _stage) = 0;
    virtual void deactivate_rule( stage::E _stage, std::string _name) = 0;
    virtual void activate_rule( stage::E _stage, std::string _name) = 0;
    virtual void process_pre_read_rules( uint64_t _old_value, uint64_t _new_value) = 0;
    virtual void process_post_read_rules( uint64_t _old_value, uint64_t _new_value) = 0;
    virtual void process_pre_write_rules( uint64_t _old_value, uint64_t _new_value) = 0;
    virtual void process_post_write_rules( uint64_t _old_value, uint64_t _new_value) = 0;
    virtual I_pattern_rule * add_rule( std::function< void()> _func, stage::E _stage, type::E _type, std::string _name, ...) = 0;
    virtual I_pattern_rule * add_user_rule( std::function< void( uint64_t, uint64_t)> _func, stage::E _stage, std::string _name, ...)  = 0;
    virtual _keep_hot I_pattern_rule * __add_rule( std::function< void()> _func, stage::E _stage, type::E _type, std::string _name, std::vector<uint64_t> &_ordered_args) { return nullptr; };
    virtual _keep_hot I_pattern_rule * __add_rule( std::function< void( uint64_t, uint64_t)> _func, stage::E _stage, type::E _type, std::string _name, va_list & args) { return nullptr; };
};

}

#endif
