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

// -*- C++ -*-

#ifndef CPP_API_EXTENSIONS_SRC_SME_PATTERN_RULES_I_PATTERN_RULE_H
#define CPP_API_EXTENSIONS_SRC_SME_PATTERN_RULES_I_PATTERN_RULE_H

#include <cstdint>
#include <functional>
#include "sme/aqpp/abstraction/compiler/_inline.h"

namespace sme
{
class pattern_rule_container;

/**
 * @brief Interface and base class for all notification rule types.
 * 
 */
class I_pattern_rule
{
protected:
    /**
     * @brief stores is active
     * 
     */
    bool m_is_active;

public:
    /**
     * @brief Interface parent constructor for a new i pattern rule object.
     */
    I_pattern_rule() : m_is_active( false)	{;}

    /**
     * @brief Destroy the i pattern rule object
     * 
     */
    virtual ~I_pattern_rule() {;}

    /**
     * @brief process rule evaluation between old and new values.
     * 
     * @param _old_value value of content prior to read or write
     * @param _new_value value of content post read or write
     */
    virtual void process_rule( std::uint64_t _old_value, std::uint64_t & _new_value) = 0;

    /**
     * @brief Binds a void(void) lambda as the callback action to this rule
     * 
     * @param _action 
     */
    virtual void action( std::function<void()> _action) = 0;
    virtual void action( std::function<void(uint64_t , uint64_t )> _action) = 0;

    /**
     * @brief reports if rule is active for processing.
     * 
     * @return bool
     */
    _always_inline bool is_active()	{ return m_is_active; }

    /**
     * @brief has the lambda callback been bound.
     * 
     * @return _always_inline 
     */
    virtual _always_inline bool is_bound()	= 0;

    friend class pattern_rule_container;
};

class I_no_params_pattern_rule : public I_pattern_rule
{
protected:
    std::function<void()> m_lambda;
public:
    I_no_params_pattern_rule() {;}
    virtual ~I_no_params_pattern_rule() {;}
    virtual void action( std::function<void()> _action) { 
        m_lambda = _action; 
        m_is_active = true;
    }
    virtual void action( std::function<void(uint64_t , uint64_t )> _action) {
        m_is_active = false;
    }
    virtual _always_inline bool is_bound()	{ return( m_lambda != nullptr); }
};

class I_params_pattern_rule : public I_pattern_rule
{
protected:
    std::function<void( uint64_t _old, uint64_t _new)> m_lambda;
public:
    I_params_pattern_rule() {;}
    virtual ~I_params_pattern_rule() {;}
    virtual void action( std::function<void()> _action) {
        m_is_active = false;
    }
    virtual void action( std::function<void(uint64_t , uint64_t )> _action) {
        m_lambda = _action;
        m_is_active = true;
    }
    virtual _always_inline bool is_bound()	{ return( m_lambda != nullptr); }
};

}

#endif /* I_PATTERN_RULE_H */
