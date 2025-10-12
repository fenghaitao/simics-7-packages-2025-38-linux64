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

#ifndef FOUNDATION_CALL_ABLES_EXPRESSION_HPP_
#define FOUNDATION_CALL_ABLES_EXPRESSION_HPP_

#include <functional>
#include <map>

#include "sme/aqpp/abstraction/compiler/_inline.h"

#include "sme/expressions/expression_vector.h"
#include "sme/overlays/callback_overlay.h"

namespace sme {
    
    /**
     * @brief describes a compound logic expression to execute other functionality
     * 
     */
    class expression {
    public:

        /**
         * @brief Construct a new expression object
         * 
         * @param _name of expression
         * @param _init_state initial state (default false)
         * @param _enabled if expression is enabled (to be processed) (default true)
         */
        expression( std::string _name, bool _init_state = false, bool _enabled = true)
            : m_name( _name)
            , m_last_state( _init_state)
            , m_enabled( _enabled)
        {;}

        /**
         * @brief sensitive_to a notification event
         * 
         * @param _overlay register or field to be sensitive to
         * @param _stage of processing to be sensitive to
         */
        void sensitive_to( callback_overlay & _overlay, const stage::E _stage) {
            _overlay.add_rule( [this]()->void { on_sensitivity(); }, _stage, sme::type::NOTIFY, m_name);
        }
        
        /**
         * @brief sensitive_to a masked change event
         * 
         * @param _overlay register or field to be sensitive to
         * @param _stage of processing to be sensitive to
         * @param _mask to monitor
         */
        void sensitive_to( callback_overlay & _overlay, const stage::E _stage, const uint64_t _mask) {
            _overlay.add_rule( [this]()->void { on_sensitivity(); }, _stage, sme::type::MASKED, m_name, _mask);
        }
        
        /**
         * @brief sensitive_to a pattern change event
         * 
         * @param _overlay register or field to be sensitive to
         * @param _stage of processing to be sensitive to
         * @param _mask to monitor
         * @param _start value
         * @param _end value
         */
        void sensitive_to( callback_overlay & _overlay, const stage::E _stage, const uint64_t _mask, const uint64_t _start, const uint64_t _end) {
            _overlay.add_rule( [this]()->void { on_sensitivity(); }, _stage, sme::type::PATTERN, m_name, _mask, _start, _end);
        }
        
        /**
         * @brief sensitive_to another expression
         * 
         * @param _expression to be sensitive to
         */
        void sensitive_to( sme::expression_vector & _expression_vector) {
            _expression_vector.m_actions[m_name] = [this]()-> void { on_sensitivity(); };
        }

        /**
         * @brief logic expression to evaluate (described as a lambda)
         * 
         * @param _func lambda to bind
         */
        void logic( std::function<bool()> _func) {
            m_logic = _func;
        }

        /**
         * @brief evaluates expression without firing events.
         * 
         * @return true 
         * @return false 
         */
        _keep_hot bool evaluate( bool _store_state_eval = false) {
            if( has_logic()) {
                if( m_logic()) {
                    if( _store_state_eval) m_last_state = true;
                    return true;
                }
            }
            if( _store_state_eval) m_last_state = false;
            return false;
        }

        /**
         * @brief schedules a future evaluation in simics time.
         * 
         */
//        _keep_hot void process( SIMICS types for time delay...);

        /**
         * @brief has a logic expression been defined
         * 
         * @return true 
         * @return false 
         */
        _always_inline bool has_logic()         { return( m_logic != nullptr); }

        /**
         * @brief disables expression (when sensitivity is fired expression will not be evaluated).
         * 
         */
        _always_inline void disable()           { m_enabled = false; }
        
        /**
         * @brief enables expression (when sensitivity is fired expression will be evaluated).
         * 
         */
        _always_inline void enable()            { m_enabled = true; }
        
        /**
         * @brief will the expression evaluate and fire events if sensitivity is fired?
         * 
         * @return true 
         * @return false 
         */
        _always_inline bool is_enabled()        { return( m_enabled); }
        
        /**
         * @brief what is the last known state (evaluation) of the expression?
         * 
         * @return true 
         * @return false 
         */
        _always_inline bool last_state()        { return( m_last_state); }

        /**
         * @brief callback for processing the execution of content on sensitivity firing.
         * 
         */
        _keep_hot void on_sensitivity() {
            if( has_logic() && m_enabled) {
                if( m_logic()) {
                    if( m_last_state ) {
                        eval_true.process();
                    } else {
                        eval_true.process();
                        m_last_state = true;
                        change.process();
                        rising.process();
                    }
                } else { // false
                    if( m_last_state) {
                        eval_false.process();
                        m_last_state = false;
                        change.process();
                        falling.process();
                    } else {
                        eval_false.process();
                    }
                }
                // TO THINK ABOUT
                // after the processing has executed, it is necessary to re-evaluate
                // the condition so that m_last_state is set correctly IF there was
                // a variable reset...

                // this re-evaluation SHOULD NOT cause an event to be fired! <-- important
                // evaluate( true);
            }
        }

    public:
        /**
         * @brief rising execution vector.
         * 
         */
        sme::expression_vector rising;

        /**
         * @brief falling execution vector.
         * 
         */
        sme::expression_vector falling;

        /**
         * @brief change execution vector (rising or falling).
         * 
         */
        sme::expression_vector change;

        /**
         * @brief true execution vector (fires even if true on previous evaluation).
         * 
         */
        sme::expression_vector eval_true;

        /**
         * @brief false execution vector (fires even if false on previous evaluation).
         * 
         */
        sme::expression_vector eval_false;

    private:

        /**
         * @brief lambda representing the expression logic to evaluate
         * 
         */
        std::function<bool()> m_logic;

        /**
         * @brief name of this expression
         * 
         */
        std::string m_name;

    public:
    
        /**
         * @brief last state of expression evaluation
         * 
         */
        bool m_last_state;

        /**
         * @brief is expression enabled
         * 
         */
        bool m_enabled;
    };

} // namespace sme

#endif /* FOUNDATION_CALL_ABLES_EXPRESSION_HPP_ */
