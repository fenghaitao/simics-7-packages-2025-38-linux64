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

#ifndef CPP_API_EXTENSIONS_SRC_SME_PATTERN_RULES_PATTERN_RULE_CONTAINER_H
#define CPP_API_EXTENSIONS_SRC_SME_PATTERN_RULES_PATTERN_RULE_CONTAINER_H

#include <string>
#include <map>

//#ifdef __GNUC__
    #include <cstdint>
//#endif

#include "sme/aqpp/foundation/callables/action.hpp"
#include "sme/pattern_rules/I_pattern_rule.h"
#include "sme/aqpp/print/sme_print.hpp"

namespace sme
{

/**
 * @brief tracks all rules of a single type for a particular target.
 * 
 */
class pattern_rule_container
{
public:

    /**
     * @brief Construct a new pattern rule container object.
     * 
     */
    pattern_rule_container()
    {;}

    /**
     * @brief Destroy the pattern rule container object.
     * 
     */
    virtual ~pattern_rule_container()
    {;}

    /**
     * @brief Adds a descendant of I_pattern_rule by name to this container.
     * 
     * @param _name of rule
     * @param _rule pointer to new rule object
     * @param _active enables or disables rule (true by default)
     * @return true if success
     * @return false if failure
     */
    bool add_rule( std::string _name, I_pattern_rule * _rule, bool _active = true)
    {
        if( find_rule( _name) == NULL)
        {
            _rule->m_is_active = _active;
            if( _active) {
                SIM_DEBUG( "Adding active rule '" << _name << "'");
                m_active_rules[ _name] = _rule;
            } else {
                SIM_DEBUG( "Adding inactive rule '" << _name << "'");
                m_inactive_rules[ _name] = _rule;
            }
            return( true);
        }
        SIM_ERROR( "Rule already exists with name '" << _name << "'");
        return( false);
    }
    
    /**
     * @brief deactivate rule by name.
     * 
     * @param _name of rule to deactivate
     */
    void deactivate_rule( std::string _name)
    {
        if( find_inactive_rule( _name) == NULL)
        {
            std::map< std::string, I_pattern_rule *>::iterator mit = m_active_rules.find( _name);
            if( mit != m_active_rules.end())
            {
                I_pattern_rule * rule = mit->second;
                rule->m_is_active = false;
                m_inactive_rules[ _name] = rule;
                m_active_rules.erase( _name);
            }
        }	
    }
    
    /**
     * @brief activate rule by name.
     * 
     * @param _name of rule to activate
     */
    void activate_rule( std::string _name)
    {
        if( find_active_rule( _name) == NULL)
        {
            std::map< std::string, I_pattern_rule *>::iterator mit = m_inactive_rules.find( _name);
            if( mit != m_inactive_rules.end())
            {
                I_pattern_rule * rule = mit->second;
                rule->m_is_active = true;
                m_inactive_rules.erase( _name);
                m_active_rules[ _name] = rule;
            }
        }	
    }
    
    /**
     * @brief processes all active rules.
     * 
     * @param _old_value of associated object
     * @param _new_value of associated object
     */
    void process_active_rules( uint64_t _old_value, uint64_t _new_value)
    {
        std::map< std::string, I_pattern_rule *>::iterator it;
        for( it = m_active_rules.begin(); it != m_active_rules.end(); it++)
        {
            SIM_DEBUG_NO_NEWLINE( "rule " << it->first);
            it->second->process_rule( _old_value, _new_value);
        }
    }

    /**
     * @brief find rule in active or inactive list by name.
     * 
     * @param _name of rule
     * @return I_pattern_rule* 
     */
    I_pattern_rule * find_rule( std::string _name)
    {
        I_pattern_rule * rule = find_active_rule( _name);
        if( rule != NULL)
            return( rule);
        return( find_inactive_rule( _name));
    }
    
    /**
     * @brief find rule in active list by name.
     * 
     * @param _name of rule
     * @return I_pattern_rule* 
     */
    I_pattern_rule * find_active_rule( std::string _name)
    {
        std::map< std::string, I_pattern_rule *>::iterator mit = m_active_rules.find( _name);
        if( mit != m_active_rules.end())
            return( mit->second);
        return( NULL);
    }
    
    /**
     * @brief find rule in inactive list by name.
     * 
     * @param _name of rule
     * @return I_pattern_rule* 
     */
    I_pattern_rule * find_inactive_rule( std::string _name)
    {
        std::map< std::string, I_pattern_rule *>::iterator mit = m_inactive_rules.find( _name);
        if( mit != m_inactive_rules.end())
            return( mit->second);
        return( NULL);
    }

    /**
     * @brief return const reference to 'active' string map of pattern rules.
     * 
     * @return const std::map< std::string, I_pattern_rule *> &
     */
    const std::map< std::string, I_pattern_rule *> & get_active_rules() const {
        return( m_active_rules);
    }

    /**
     * @brief return const reference to 'inactive' string map of pattern rules.
     * 
     * @return const std::map< std::string, I_pattern_rule *> &
     */
    const std::map< std::string, I_pattern_rule *> & get_inactive_rules() const {
        return( m_inactive_rules);
    }

protected:
    /**
     * @brief map of string to active rules.
     * 
     */
    std::map< std::string, I_pattern_rule *> m_active_rules;

    /**
     * @brief map of string to inactive rules.
     * 
     */
    std::map< std::string, I_pattern_rule *> m_inactive_rules;
};

}

#endif /*PATTERN_RULE_CONTAINER_H_*/
