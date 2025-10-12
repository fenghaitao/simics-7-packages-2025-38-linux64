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

#ifndef FOUNDATION_CALLABLES_ACTION_HPP_
#define FOUNDATION_CALLABLES_ACTION_HPP_

#include <assert.h>
#include <iostream>

#include "sme/aqpp/abstraction/compiler/_inline.h"

namespace aqpp
{

class action_handler {
public:
    virtual ~action_handler() {;}
    _always_inline virtual void execute() = 0;
    _always_inline virtual bool is_bound() = 0;
};

template< class C>
class action : public action_handler
{
public:
    typedef void(C::*action_t)();

    action() : m_action_class_instance(0), m_action(0) {;}
    ~action() {;}

    _always_inline void bind( C * _action_class_instance, action_t _action)
    {
        m_action_class_instance = _action_class_instance;
        m_action = _action;
    }

    _always_inline void execute()
    {
        if (m_action_class_instance) {
            (m_action_class_instance->*m_action)();
        }
        else {
            std::cerr << "[ERROR]: Unbound action!" << std::endl;
        }
    }

    _always_inline bool is_bound() {
        return( m_action != 0);
    }

#ifdef TEST
    _always_inline C * get_class_instance() { return m_action_class_instance; }
    _always_inline action_t get_action() { return m_action; }
#endif

protected:
    C * m_action_class_instance;
    action_t m_action;
};

class c_action : public action_handler
{
public:
    typedef void(*action_t)();

    c_action() : m_action(0) {;}
    ~c_action() {;}

    _always_inline void bind( action_t _action)
    {
        m_action = _action;
    }

    _always_inline void execute()
    {
        (*m_action)();
    }

    _always_inline bool is_bound() {
        return( m_action != 0);
    }

#ifdef TEST
    _always_inline action_t get_action() { return m_action; }
#endif

protected:
    action_t m_action;
};

} // namespace aqpp


#endif /* FOUNDATION_CALLABLES_ACTION_HPP_ */
