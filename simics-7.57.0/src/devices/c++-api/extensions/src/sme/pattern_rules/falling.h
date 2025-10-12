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

#ifndef CPP_API_EXTENSIONS_SRC_SME_PATTERN_RULES_FALLING_H
#define CPP_API_EXTENSIONS_SRC_SME_PATTERN_RULES_FALLING_H

#include "sme/pattern_rules/I_pattern_rule.h"
#include "sme/aqpp/print/sme_print.hpp"
#include <iostream>
#include <ios>

namespace sme {

    namespace rules {

        /**
         * @brief rule specifically to monitor the edge when all bits in the register have fallen.
         *
         */
        class falling : public I_no_params_pattern_rule
        {
        public:
            /**
             * @brief Construct a new "all fall" object.
             *
             */
            falling() : I_no_params_pattern_rule() {;}

            /**
             * @brief Destroy the "all fall" object.
             *
             */
            virtual ~falling()	{;}

            /**
             * @brief process rule evaluation between old and new values.
             *
             * @param _old_value value of content prior to read or write
             * @param _new_value value of content post read or write
             */
            virtual void process_rule( uint64_t _old_value, uint64_t & _new_value) {
                if( is_active() && is_bound() && (_old_value && !_new_value) ) {
                    SIM_DEBUG_END( "true");
                    m_lambda();
                } else {
                    SIM_DEBUG_END( "false");
                }
            }
        };

    }

}

#endif /*CPP_API_EXTENSIONS_SRC_SME_PATTERN_RULES_FALLING_H*/
