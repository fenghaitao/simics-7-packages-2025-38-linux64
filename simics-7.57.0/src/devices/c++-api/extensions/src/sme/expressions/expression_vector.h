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

#ifndef CPP_API_EXTENSIONS_SRC_SME_EXPRESSIONS_EXPRESSION_VECTOR_H
#define CPP_API_EXTENSIONS_SRC_SME_EXPRESSIONS_EXPRESSION_VECTOR_H

#include <functional>
#include <map>
#include <string>

#include "sme/aqpp/abstraction/compiler/_inline.h"

namespace sme {

class expression;

/**
 * @brief vector of execution resulting from expression evaluation.
 * @details
 * There are many conditions which an expression can render execution based
 * on the evaluation of itself.  Rising, Falling, True->True, False->False, or Change (Rising or Falling).
 * Expressions may have callbacks for each of these execution vectors.
 */
class expression_vector {
public:

    /**
     * @brief holds sensitivity to other expressions
     *
     */
    std::map< std::string, std::function<void()> > m_actions;

    /**
     * @brief placeholder for lambda
     *
     */
    std::function<void()> m_lambda;

    /**
     * @brief has sensitivity targets (depends on size of map)
     *
     * @return true
     * @return false
     */
    _always_inline bool has_targets() { return( m_actions.size() > 0); }

    /**
     * @brief is the lambda defined/bound
     *
     * @return true
     * @return false
     */
    _always_inline bool is_bound() { return( m_lambda != nullptr); }

    /**
     * @brief define/bind the lambda (this will be executed)
     *
     * @param _func
     */
    _always_inline void execute( std::function< void()> _func) { m_lambda = _func; }

    /**
     * @brief processes (executes) sensitivities
     *
     */
    _keep_hot void process() {
        if( is_bound()) m_lambda();
        if( has_targets()) {
            std::map< std::string, std::function<void()> >::iterator mit;
            for( mit = m_actions.begin(); mit != m_actions.end(); mit++) {
                mit->second();
            }
        }
    }

protected:
    friend class sme::expression;
    
};

} // namespace sme

#endif
