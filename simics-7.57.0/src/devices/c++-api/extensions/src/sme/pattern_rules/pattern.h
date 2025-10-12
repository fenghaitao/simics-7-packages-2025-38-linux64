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

#ifndef CPP_API_EXTENSIONS_SRC_SME_PATTERN_RULES_PATTERN_H
#define CPP_API_EXTENSIONS_SRC_SME_PATTERN_RULES_PATTERN_H

#include "sme/pattern_rules/I_pattern_rule.h"
#include "sme/aqpp/print/sme_print.hpp"
#include <iostream>
#include <ios>
namespace sme {

    namespace rules {
    
    /**
     * @brief rule executes if the masked pattern matches the start (old) and end (new) values.
     * 
     */
        class pattern : public I_no_params_pattern_rule
        {
        public:

            /**
             * @brief mask to apply for rule evaluation.
             * 
             */
            uint64_t m_mask;

            /**
             * @brief initial value to match with mask.
             * 
             */
            uint64_t m_start;
            
            /**
             * @brief new value to match with mask.
             * 
             */
            uint64_t m_end;

            /**
             * @brief Construct a new pattern object.
             * 
             * @param _mask to be applied on the target (Register or Field)
             * @param _start value which _old_data should match 
             * @param _end value which _new_data should match
             */
            pattern( uint64_t _mask, uint64_t _start, uint64_t _end) 
                : I_no_params_pattern_rule()
                , m_mask( _mask)
                , m_start( _start)
                , m_end( _end)
            {
            }

            /**
             * @brief Destroy the pattern object.
             * 
             */
            virtual ~pattern()	{;}
            
            /**
             * @brief process rule evaluation between old and new values.
             * 
             * @param _old_value value of content prior to read or write
             * @param _new_value value of content post read or write
             */
            virtual void process_rule( uint64_t _old_value, uint64_t & _new_value) {
                if( is_active() && is_bound() && ( ( _old_value & m_mask) == m_start) && ( ( _new_value & m_mask) == m_end) ) {
                    SIM_DEBUG_END( "true");
                    m_lambda();
                } else {
                    SIM_DEBUG_END( "false");
                }
            }
        };

    }

}

#endif /*NOTIFICATION_RULE_PATTERN_H_*/
