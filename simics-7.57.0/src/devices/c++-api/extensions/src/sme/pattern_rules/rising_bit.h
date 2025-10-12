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

#ifndef CPP_API_EXTENSIONS_SRC_SME_PATTERN_RULES_RISING_BIT_H
#define CPP_API_EXTENSIONS_SRC_SME_PATTERN_RULES_RISING_BIT_H

#include "sme/pattern_rules/I_pattern_rule.h"
#include "sme/aqpp/print/sme_print.hpp"
#include <iostream>
#include <ios>
namespace sme {

    namespace rules {
    
        /**
         * @brief rule specifically to monitor a single bit for rising edge.
         * 
         */
        class rising_bit : public I_no_params_pattern_rule
        {
        public:
            /**
             * @brief The bit which is to change state.
             * 
             */
            uint8_t m_bit;

            /**
             * @brief Construct a new rising bit object.
             * 
             * @param _bit to monitor (0 base relative to target (register or field))
             */
            rising_bit( uint8_t _bit)
                : I_no_params_pattern_rule()
                , m_bit( _bit)
            {
            }

            /**
             * @brief Destroy the rising bit object.
             * 
             */
            virtual ~rising_bit()	{;}
            
            /**
             * @brief process rule evaluation between old and new values.
             * 
             * @param _old_value value of content prior to read or write
             * @param _new_value value of content post read or write
             */
            virtual void process_rule( uint64_t _old_value, uint64_t & _new_value) {
                if( is_active() && is_bound() && ((!(_old_value & (1ULL << m_bit))) && ((_new_value & (1ULL << m_bit)))) ) {
                    SIM_DEBUG_END( "true");
                    m_lambda();
                } else {
                    SIM_DEBUG_END( "false");
                }
            }
        };

    }

}

#endif /*NOTIFICATION_RULE_RISING_BIT_H_*/
